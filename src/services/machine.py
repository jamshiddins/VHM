from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.machine import Machine, MachineType, MachineStatus
from src.db.models.user import User
from src.core.exceptions import (
   MachineNotFound, MachineAlreadyExists, UserNotFound
)


class MachineService:
   """Сервис для работы с автоматами"""
   
   def __init__(self, session: AsyncSession):
       self.session = session
   
   async def create_machine(
       self,
       code: str,
       name: str,
       machine_type: MachineType,
       model: Optional[str] = None,
       serial_number: Optional[str] = None,
       location_address: Optional[str] = None,
       location_lat: Optional[float] = None,
       location_lng: Optional[float] = None,
       responsible_user_id: Optional[int] = None
   ) -> Machine:
       """Создание нового автомата"""
       # Проверяем уникальность кода
       existing = await self.session.execute(
           select(Machine).where(Machine.code == code)
       )
       if existing.scalar_one_or_none():
           raise MachineAlreadyExists(f"Автомат с кодом {code} уже существует")
       
       # Проверяем ответственного
       if responsible_user_id:
           user = await self.session.get(User, responsible_user_id)
           if not user:
               raise UserNotFound(f"Пользователь с ID {responsible_user_id} не найден")
       
       # Создаем автомат
       machine = Machine(
           code=code,
           name=name,
           type=machine_type,
           model=model,
           serial_number=serial_number,
           location_address=location_address,
           location_lat=location_lat,
           location_lng=location_lng,
           responsible_user_id=responsible_user_id,
           installation_date=date.today()
       )
       
       self.session.add(machine)
       await self.session.commit()
       await self.session.refresh(machine)
       
       return machine
   
   async def get_machine_by_id(self, machine_id: int) -> Optional[Machine]:
       """Получение автомата по ID"""
       query = select(Machine).options(
           selectinload(Machine.responsible_user),
           selectinload(Machine.investors).selectinload('investor'),
           selectinload(Machine.tasks)
       ).where(
           and_(
               Machine.id == machine_id,
               Machine.deleted_at.is_(None)
           )
       )
       
       result = await self.session.execute(query)
       return result.scalar_one_or_none()
   
   async def get_machine_by_code(self, code: str) -> Optional[Machine]:
       """Получение автомата по коду"""
       query = select(Machine).where(
           and_(
               Machine.code == code,
               Machine.deleted_at.is_(None)
           )
       )
       
       result = await self.session.execute(query)
       return result.scalar_one_or_none()
   
   async def update_machine(
       self,
       machine_id: int,
       update_data: Dict[str, Any]
   ) -> Machine:
       """Обновление автомата"""
       machine = await self.get_machine_by_id(machine_id)
       if not machine:
           raise MachineNotFound(f"Автомат с ID {machine_id} не найден")
       
       # Обновляем поля
       allowed_fields = [
           'name', 'model', 'serial_number', 'status',
           'location_address', 'location_lat', 'location_lng',
           'responsible_user_id', 'settings', 'metadata'
       ]
       
       for field, value in update_data.items():
           if field in allowed_fields:
               setattr(machine, field, value)
       
       await self.session.commit()
       await self.session.refresh(machine)
       
       return machine
   
   async def update_machine_status(
       self,
       machine_id: int,
       status: MachineStatus
   ) -> Machine:
       """Обновление статуса автомата"""
       machine = await self.get_machine_by_id(machine_id)
       if not machine:
           raise MachineNotFound(f"Автомат с ID {machine_id} не найден")
       
       machine.status = status
       
       # Если автомат на обслуживании, обновляем дату
       if status == MachineStatus.MAINTENANCE:
           machine.last_service_date = date.today()
       
       await self.session.commit()
       await self.session.refresh(machine)
       
       return machine
   
   async def delete_machine(
       self,
       machine_id: int,
       soft: bool = True
   ) -> bool:
       """Удаление автомата"""
       machine = await self.get_machine_by_id(machine_id)
       if not machine:
           raise MachineNotFound(f"Автомат с ID {machine_id} не найден")
       
       if soft:
           machine.soft_delete()
       else:
           await self.session.delete(machine)
       
       await self.session.commit()
       return True
   
   async def get_machines_list(
       self,
       machine_type: Optional[MachineType] = None,
       status: Optional[MachineStatus] = None,
       responsible_user_id: Optional[int] = None,
       search: Optional[str] = None,
       has_issues: Optional[bool] = None,
       limit: int = 100,
       offset: int = 0
   ) -> tuple[List[Machine], int]:
       """Получение списка автоматов с фильтрацией"""
       query = select(Machine).options(
           selectinload(Machine.responsible_user)
       ).where(Machine.deleted_at.is_(None))
       
       # Применяем фильтры
       if machine_type:
           query = query.where(Machine.type == machine_type)
       
       if status:
           query = query.where(Machine.status == status)
       
       if responsible_user_id:
           query = query.where(Machine.responsible_user_id == responsible_user_id)
       
       if search:
           search_term = f"%{search}%"
           query = query.where(
               or_(
                   Machine.code.ilike(search_term),
                   Machine.name.ilike(search_term),
                   Machine.location_address.ilike(search_term)
               )
           )
       
       if has_issues is not None:
           # TODO: Добавить логику для фильтрации по проблемам
           pass
       
       # Подсчет общего количества
       count_query = select(func.count()).select_from(query.subquery())
       total_result = await self.session.execute(count_query)
       total = total_result.scalar() or 0
       
       # Применяем пагинацию и сортировку
       query = query.order_by(Machine.code)
       query = query.offset(offset).limit(limit)
       
       result = await self.session.execute(query)
       machines = list(result.scalars().all())
       
       return machines, total
   
   async def get_machine_statistics(
       self,
       machine_id: Optional[int] = None
   ) -> Dict[str, Any]:
       """Получение статистики по автоматам"""
       if machine_id:
           machine = await self.get_machine_by_id(machine_id)
           if not machine:
               raise MachineNotFound(f"Автомат с ID {machine_id} не найден")
           
           # Статистика по конкретному автомату
           from src.db.models.finance import Sale
           from src.db.models.route import MachineTask, TaskStatus
           
           # Продажи за последний месяц
           sales_query = select(
               func.count(Sale.id),
               func.sum(Sale.total_amount)
           ).where(
               and_(
                   Sale.machine_id == machine_id,
                   Sale.action_timestamp >= datetime.utcnow().replace(day=1)
               )
           )
           sales_result = await self.session.execute(sales_query)
           sales_count, sales_amount = sales_result.one()
           
           # Задачи
           tasks_query = select(
               MachineTask.status,
               func.count(MachineTask.id)
           ).where(
               MachineTask.machine_id == machine_id
           ).group_by(MachineTask.status)
           
           tasks_result = await self.session.execute(tasks_query)
           tasks_by_status = dict(tasks_result.all())
           
           return {
               'machine_id': machine_id,
               'machine_code': machine.code,
               'status': machine.status.value,
               'sales_this_month': {
                   'count': sales_count or 0,
                   'amount': float(sales_amount or 0)
               },
               'tasks': {
                   status.value: count 
                   for status, count in tasks_by_status.items()
               },
               'total_investment': machine.total_investment,
               'investor_count': len([inv for inv in machine.investors if inv.is_active])
           }
       else:
           # Общая статистика по всем автоматам
           total_query = select(func.count(Machine.id)).where(
               Machine.deleted_at.is_(None)
           )
           total_result = await self.session.execute(total_query)
           total = total_result.scalar() or 0
           
           # По статусам
           status_query = select(
               Machine.status,
               func.count(Machine.id)
           ).where(
               Machine.deleted_at.is_(None)
           ).group_by(Machine.status)
           
           status_result = await self.session.execute(status_query)
           by_status = dict(status_result.all())
           
           # По типам
           type_query = select(
               Machine.type,
               func.count(Machine.id)
           ).where(
               Machine.deleted_at.is_(None)
           ).group_by(Machine.type)
           
           type_result = await self.session.execute(type_query)
           by_type = dict(type_result.all())
           
           return {
               'total': total,
               'by_status': {
                   status.value: count 
                   for status, count in by_status.items()
               },
               'by_type': {
                   machine_type.value: count 
                   for machine_type, count in by_type.items()
               },
               'operational_rate': (
                   by_status.get(MachineStatus.ACTIVE, 0) / total * 100 
                   if total > 0 else 0
               )
           }
   
   async def get_machines_map_data(self) -> List[Dict[str, Any]]:
       """Получение данных для отображения на карте"""
       query = select(Machine).where(
           and_(
               Machine.deleted_at.is_(None),
               Machine.location_lat.isnot(None),
               Machine.location_lng.isnot(None)
           )
       )
       
       result = await self.session.execute(query)
       machines = result.scalars().all()
       
       map_data = []
       for machine in machines:
           map_data.append({
               'id': machine.id,
               'code': machine.code,
               'name': machine.name,
               'type': machine.type.value,
               'status': machine.status.value,
               'lat': float(machine.location_lat),
               'lng': float(machine.location_lng),
               'address': machine.location_address,
               'is_operational': machine.is_operational
           })
       
       return map_data
   
   async def get_nearby_machines(
       self,
       lat: float,
       lng: float,
       radius_km: float = 5.0
   ) -> List[Machine]:
       """Получение ближайших автоматов"""
       # Используем формулу Haversine для расчета расстояния
       # Это приблизительный расчет для небольших расстояний
       
       lat_diff = radius_km / 111.0  # ~111 км в одном градусе широты
       lng_diff = radius_km / (111.0 * abs(func.cos(func.radians(lat))))
       
       query = select(Machine).where(
           and_(
               Machine.deleted_at.is_(None),
               Machine.location_lat.between(lat - lat_diff, lat + lat_diff),
               Machine.location_lng.between(lng - lng_diff, lng + lng_diff)
           )
       )
       
       result = await self.session.execute(query)
       return list(result.scalars().all())
