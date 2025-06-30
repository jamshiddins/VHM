from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.route import (
   MachineTask, TaskStatus, TaskType, Route, TaskItem, 
   TaskPhoto, TaskProblem, ProblemType
)
from src.db.models.machine import Machine
from src.db.models.user import User
from src.core.exceptions import (
   TaskNotFound, TaskAlreadyCompleted, PermissionDenied,
   UserNotFound, MachineNotFound
)


class TaskService:
   """Сервис для работы с задачами"""
   
   def __init__(self, session: AsyncSession):
       self.session = session
   
   async def create_task(
       self,
       machine_id: int,
       task_type: TaskType,
       title: str,
       description: Optional[str] = None,
       assigned_to_id: Optional[int] = None,
       route_id: Optional[int] = None,
       items: Optional[List[Dict[str, Any]]] = None
   ) -> MachineTask:
       """Создание новой задачи"""
       # Проверяем существование машины
       machine = await self.session.get(Machine, machine_id)
       if not machine:
           raise MachineNotFound(f"Машина с ID {machine_id} не найдена")
       
       # Создаем задачу
       task = MachineTask(
           machine_id=machine_id,
           type=task_type,
           title=title,
           description=description,
           route_id=route_id,
           status=TaskStatus.PENDING
       )
       
       # Назначаем исполнителя
       if assigned_to_id:
           user = await self.session.get(User, assigned_to_id)
           if not user:
               raise UserNotFound(f"Пользователь с ID {assigned_to_id} не найден")
           
           task.assigned_to_id = assigned_to_id
           task.assigned_at = datetime.utcnow()
           task.status = TaskStatus.ASSIGNED
       
       self.session.add(task)
       
       # Добавляем элементы задачи (например, ингредиенты для пополнения)
       if items:
           for item_data in items:
               task_item = TaskItem(
                   task=task,
                   ingredient_id=item_data['ingredient_id'],
                   planned_quantity=item_data['quantity']
               )
               self.session.add(task_item)
       
       await self.session.commit()
       await self.session.refresh(task)
       
       return task
   
   async def get_task_by_id(self, task_id: int) -> Optional[MachineTask]:
       """Получение задачи по ID"""
       query = select(MachineTask).options(
           selectinload(MachineTask.machine),
           selectinload(MachineTask.assigned_to),
           selectinload(MachineTask.items).selectinload(TaskItem.ingredient),
           selectinload(MachineTask.photos),
           selectinload(MachineTask.problems)
       ).where(MachineTask.id == task_id)
       
       result = await self.session.execute(query)
       return result.scalar_one_or_none()
   
   async def get_task_details(self, task_id: int) -> Optional[MachineTask]:
       """Получение детальной информации о задаче"""
       return await self.get_task_by_id(task_id)
   
   async def get_user_active_tasks(self, user_id: int) -> List[MachineTask]:
       """Получение активных задач пользователя"""
       query = select(MachineTask).options(
           selectinload(MachineTask.machine)
       ).where(
           and_(
               MachineTask.assigned_to_id == user_id,
               MachineTask.status.in_([TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS])
           )
       ).order_by(MachineTask.created_at)
       
       result = await self.session.execute(query)
       return list(result.scalars().all())
   
   async def assign_task(self, task_id: int, user_id: int) -> MachineTask:
       """Назначение задачи пользователю"""
       task = await self.get_task_by_id(task_id)
       if not task:
           raise TaskNotFound(f"Задача с ID {task_id} не найдена")
       
       if task.status == TaskStatus.COMPLETED:
           raise TaskAlreadyCompleted("Задача уже выполнена")
       
       # Проверяем пользователя
       user = await self.session.get(User, user_id)
       if not user:
           raise UserNotFound(f"Пользователь с ID {user_id} не найден")
       
       # Назначаем
       task.assigned_to_id = user_id
       task.assigned_at = datetime.utcnow()
       task.status = TaskStatus.ASSIGNED
       
       await self.session.commit()
       await self.session.refresh(task)
       
       return task
   
   async def start_task(self, task_id: int, user_id: int) -> MachineTask:
       """Начало выполнения задачи"""
       task = await self.get_task_by_id(task_id)
       if not task:
           raise TaskNotFound(f"Задача с ID {task_id} не найдена")
       
       if task.assigned_to_id != user_id:
           raise PermissionDenied("Вы не можете начать эту задачу")
       
       if task.status == TaskStatus.COMPLETED:
           raise TaskAlreadyCompleted("Задача уже выполнена")
       
       task.status = TaskStatus.IN_PROGRESS
       task.started_at = datetime.utcnow()
       
       await self.session.commit()
       await self.session.refresh(task)
       
       return task
   
   async def complete_task(
       self,
       task_id: int,
       user_id: Optional[int] = None,
       actual_items: Optional[List[Dict[str, Any]]] = None
   ) -> MachineTask:
       """Завершение задачи"""
       task = await self.get_task_by_id(task_id)
       if not task:
           raise TaskNotFound(f"Задача с ID {task_id} не найдена")
       
       if user_id and task.assigned_to_id != user_id:
           raise PermissionDenied("Вы не можете завершить эту задачу")
       
       if task.status == TaskStatus.COMPLETED:
           raise TaskAlreadyCompleted("Задача уже выполнена")
       
       # Обновляем статус
       task.status = TaskStatus.COMPLETED
       task.completed_at = datetime.utcnow()
       
       # Обновляем фактические количества
       if actual_items:
           for item_data in actual_items:
               item_id = item_data['item_id']
               actual_qty = item_data['actual_quantity']
               returned_qty = item_data.get('returned_quantity', 0)
               
               # Находим элемент задачи
               for item in task.items:
                   if item.id == item_id:
                       item.actual_quantity = actual_qty
                       item.returned_quantity = returned_qty
                       break
       
       await self.session.commit()
       await self.session.refresh(task)
       
       # TODO: Обновить остатки в инвентаре
       
       return task
   
   async def add_task_photo(
       self,
       task_id: int,
       photo_type: str,
       telegram_file_id: str,
       caption: Optional[str] = None
   ) -> TaskPhoto:
       """Добавление фото к задаче"""
       task = await self.get_task_by_id(task_id)
       if not task:
           raise TaskNotFound(f"Задача с ID {task_id} не найдена")
       
       photo = TaskPhoto(
           task_id=task_id,
           photo_type=photo_type,
           file_path=f"telegram://{telegram_file_id}",  # Временный путь
           telegram_file_id=telegram_file_id,
           caption=caption
       )
       
       self.session.add(photo)
       await self.session.commit()
       
       return photo
   
   async def add_task_comment(self, task_id: int, comment: str) -> MachineTask:
       """Добавление комментария к задаче"""
       task = await self.get_task_by_id(task_id)
       if not task:
           raise TaskNotFound(f"Задача с ID {task_id} не найдена")
       
       # Добавляем комментарий в result_data
       if not task.result_data:
           task.result_data = {}
       
       if 'comments' not in task.result_data:
           task.result_data['comments'] = []
       
       task.result_data['comments'].append({
           'text': comment,
           'timestamp': datetime.utcnow().isoformat()
       })
       
       await self.session.commit()
       await self.session.refresh(task)
       
       return task
   
   async def report_problem(
       self,
       task_id: int,
       problem_type: str,
       description: str,
       is_critical: bool = False
   ) -> TaskProblem:
       """Сообщение о проблеме"""
       task = await self.get_task_by_id(task_id)
       if not task:
           raise TaskNotFound(f"Задача с ID {task_id} не найдена")
       
       problem = TaskProblem(
           task_id=task_id,
           problem_type=ProblemType(problem_type),
           description=description,
           is_critical=is_critical
       )
       
       self.session.add(problem)
       await self.session.commit()
       
       # TODO: Отправить уведомление менеджеру если критично
       
       return problem
   
   async def get_tasks_by_filters(
       self,
       machine_id: Optional[int] = None,
       route_id: Optional[int] = None,
       assigned_to_id: Optional[int] = None,
       task_type: Optional[TaskType] = None,
       status: Optional[TaskStatus] = None,
       date_from: Optional[date] = None,
       date_to: Optional[date] = None,
       limit: int = 100,
       offset: int = 0
   ) -> tuple[List[MachineTask], int]:
       """Получение задач с фильтрацией"""
       query = select(MachineTask).options(
           selectinload(MachineTask.machine),
           selectinload(MachineTask.assigned_to)
       )
       
       # Применяем фильтры
       conditions = []
       
       if machine_id:
           conditions.append(MachineTask.machine_id == machine_id)
       
       if route_id:
           conditions.append(MachineTask.route_id == route_id)
       
       if assigned_to_id:
           conditions.append(MachineTask.assigned_to_id == assigned_to_id)
       
       if task_type:
           conditions.append(MachineTask.type == task_type)
       
       if status:
           conditions.append(MachineTask.status == status)
       
       if date_from:
           conditions.append(MachineTask.created_at >= date_from)
       
       if date_to:
           conditions.append(MachineTask.created_at <= date_to)
       
       if conditions:
           query = query.where(and_(*conditions))
       
       # Подсчет общего количества
       count_query = select(func.count()).select_from(query.subquery())
       total_result = await self.session.execute(count_query)
       total = total_result.scalar() or 0
       
       # Применяем пагинацию и сортировку
       query = query.order_by(MachineTask.created_at.desc())
       query = query.offset(offset).limit(limit)
       
       result = await self.session.execute(query)
       tasks = list(result.scalars().all())
       
       return tasks, total
   
   async def get_task_statistics(
       self,
       user_id: Optional[int] = None,
       machine_id: Optional[int] = None,
       date_from: Optional[date] = None,
       date_to: Optional[date] = None
   ) -> Dict[str, Any]:
       """Получение статистики по задачам"""
       conditions = []
       
       if user_id:
           conditions.append(MachineTask.assigned_to_id == user_id)
       
       if machine_id:
           conditions.append(MachineTask.machine_id == machine_id)
       
       if date_from:
           conditions.append(MachineTask.created_at >= date_from)
       
       if date_to:
           conditions.append(MachineTask.created_at <= date_to)
       
       base_query = select(MachineTask)
       if conditions:
           base_query = base_query.where(and_(*conditions))
       
       # Общее количество задач
       total_query = select(func.count()).select_from(base_query.subquery())
       total_result = await self.session.execute(total_query)
       total = total_result.scalar() or 0
       
       # По статусам
       status_query = select(
           MachineTask.status,
           func.count(MachineTask.id)
       ).group_by(MachineTask.status)
       
       if conditions:
           status_query = status_query.where(and_(*conditions))
       
       status_result = await self.session.execute(status_query)
       status_stats = dict(status_result.all())
       
       # По типам
       type_query = select(
           MachineTask.type,
           func.count(MachineTask.id)
       ).group_by(MachineTask.type)
       
       if conditions:
           type_query = type_query.where(and_(*conditions))
       
       type_result = await self.session.execute(type_query)
       type_stats = dict(type_result.all())
       
       # Среднее время выполнения
       avg_time_query = select(
           func.avg(
               func.extract('epoch', MachineTask.completed_at - MachineTask.started_at)
           )
       ).where(
           and_(
               MachineTask.completed_at.isnot(None),
               MachineTask.started_at.isnot(None),
               *conditions
           )
       )
       
       avg_time_result = await self.session.execute(avg_time_query)
       avg_completion_time = avg_time_result.scalar() or 0
       
       return {
           'total': total,
           'by_status': {
               status.value: count 
               for status, count in status_stats.items()
           },
           'by_type': {
               task_type.value: count 
               for task_type, count in type_stats.items()
           },
           'avg_completion_time_seconds': float(avg_completion_time),
           'completion_rate': (
               status_stats.get(TaskStatus.COMPLETED, 0) / total * 100 
               if total > 0 else 0
           )
       }
