from typing import Optional, List
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.user import User, Role
from src.db.schemas.user import UserCreate, UserUpdate, UserFilter
from src.core.exceptions import UserNotFound, UserAlreadyExists
from src.services.auth import AuthService


class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.auth_service = AuthService(session)
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        query = select(User).options(
            selectinload(User.roles).selectinload(Role.permissions)
        ).where(User.id == user_id)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получение пользователя по Telegram ID"""
        query = select(User).options(
            selectinload(User.roles)
        ).where(User.telegram_id == telegram_id)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_with_stats(self, telegram_id: int) -> Optional[User]:
        """Получение пользователя со статистикой"""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        # Подсчет статистики
        from src.db.models.machine import Machine
        from src.db.models.route import MachineTask, TaskStatus
        from src.db.models.investment import MachineInvestor
        
        # Количество управляемых машин
        machines_query = select(func.count(Machine.id)).where(
            Machine.responsible_user_id == user.id,
            Machine.deleted_at.is_(None)
        )
        machines_result = await self.session.execute(machines_query)
        user.managed_machines_count = machines_result.scalar() or 0
        
        # Количество активных задач
        active_tasks_query = select(func.count(MachineTask.id)).where(
            MachineTask.assigned_to_id == user.id,
            MachineTask.status.in_([TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS])
        )
        active_tasks_result = await self.session.execute(active_tasks_query)
        user.active_tasks_count = active_tasks_result.scalar() or 0
        
        # Количество выполненных задач
        completed_tasks_query = select(func.count(MachineTask.id)).where(
            MachineTask.assigned_to_id == user.id,
            MachineTask.status == TaskStatus.COMPLETED
        )
        completed_tasks_result = await self.session.execute(completed_tasks_query)
        user.completed_tasks_count = completed_tasks_result.scalar() or 0
        
        # Сумма инвестиций
        investments_query = select(func.sum(MachineInvestor.investment_amount)).where(
            MachineInvestor.user_id == user.id,
            MachineInvestor.is_active == True
        )
        investments_result = await self.session.execute(investments_query)
        user.total_investment = float(investments_result.scalar() or 0)
        
        return user
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Создание нового пользователя"""
        # Проверка уникальности
        existing_query = select(User).where(
            or_(
                User.username == user_data.username if user_data.username else False,
                User.email == user_data.email if user_data.email else False,
                User.phone == user_data.phone if user_data.phone else False,
                User.telegram_id == user_data.telegram_id if user_data.telegram_id else False
            )
        )
        existing = await self.session.execute(existing_query)
        if existing.scalar_one_or_none():
            raise UserAlreadyExists("Пользователь с такими данными уже существует")
        
        # Создание пользователя
        user = User(
            telegram_id=user_data.telegram_id,
            phone=user_data.phone,
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            password_hash=self.auth_service.get_password_hash(user_data.password) if user_data.password else None
        )
        
        # Назначение ролей
        if user_data.role_names:
            roles_query = select(Role).where(Role.name.in_(user_data.role_names))
            roles_result = await self.session.execute(roles_query)
            user.roles = list(roles_result.scalars().all())
        
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        
        return user
    
    async def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        """Обновление пользователя"""
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFound("Пользователь не найден")
        
        # Обновление полей
        update_data = user_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        await self.session.commit()
        await self.session.refresh(user)
        
        return user
    
    async def delete_user(self, user_id: int, soft: bool = True) -> bool:
        """Удаление пользователя"""
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFound("Пользователь не найден")
        
        if soft:
            user.soft_delete()
        else:
            await self.session.delete(user)
        
        await self.session.commit()
        return True
    
    async def assign_roles(self, user_id: int, role_names: List[str]) -> User:
        """Назначение ролей пользователю"""
        user = await self.get_by_id(user_id)
        if not user:
            raise UserNotFound("Пользователь не найден")
        
        # Получаем роли
        roles_query = select(Role).where(Role.name.in_(role_names))
        roles_result = await self.session.execute(roles_query)
        roles = list(roles_result.scalars().all())
        
        # Назначаем роли
        user.roles = roles
        
        await self.session.commit()
        await self.session.refresh(user)
        
        return user
    
    async def get_users_list(self, filters: UserFilter) -> tuple[List[User], int]:
        """Получение списка пользователей с фильтрацией"""
        query = select(User).options(selectinload(User.roles))
        
        # Фильтрация
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.where(
                or_(
                    User.full_name.ilike(search_term),
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.phone.ilike(search_term)
                )
            )
        
        if filters.role:
            query = query.join(User.roles).where(Role.name == filters.role)
        
        if filters.is_active is not None:
            query = query.where(User.is_active == filters.is_active)
        
        if filters.is_verified is not None:
            query = query.where(User.is_verified == filters.is_verified)
        
        if filters.has_telegram is not None:
            if filters.has_telegram:
                query = query.where(User.telegram_id.isnot(None))
            else:
                query = query.where(User.telegram_id.is_(None))
        
        if filters.created_from:
            query = query.where(User.created_at >= filters.created_from)
        
        if filters.created_to:
            query = query.where(User.created_at <= filters.created_to)
        
        # Подсчет общего количества
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Применение пагинации
        query = query.offset(filters.offset).limit(filters.limit)
        
        # Выполнение запроса
        result = await self.session.execute(query)
        users = list(result.scalars().all())
        
        return users, total