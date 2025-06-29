from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models.route import MachineTask, TaskItem, TaskPhoto, TaskProblem, TaskStatus, TaskType, ProblemType
from src.core.exceptions import TaskNotFound, TaskAlreadyCompleted


class TaskService:
    """Сервис для работы с задачами"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_user_active_tasks(self, user_id: int) -> List[MachineTask]:
        """Получение активных задач пользователя"""
        query = select(MachineTask).options(
            selectinload(MachineTask.machine),
            selectinload(MachineTask.items).selectinload(TaskItem.ingredient)
        ).where(
            and_(
                MachineTask.assigned_to_id == user_id,
                MachineTask.status.in_([TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS])
            )
        ).order_by(MachineTask.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_task_details(self, task_id: int) -> Optional[MachineTask]:
        """Получение детальной информации о задаче"""
        query = select(MachineTask).options(
            selectinload(MachineTask.machine),
            selectinload(MachineTask.items).selectinload(TaskItem.ingredient),
            selectinload(MachineTask.photos),
            selectinload(MachineTask.problems)
        ).where(MachineTask.id == task_id)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def complete_task(self, task_id: int) -> MachineTask:
        """Завершение задачи"""
        task = await self.get_task_details(task_id)
        if not task:
            raise TaskNotFound("Задача не найдена")
        
        if task.status == TaskStatus.COMPLETED:
            raise TaskAlreadyCompleted("Задача уже выполнена")
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        
        await self.session.commit()
        return task
    
    async def add_task_photo(
        self, 
        task_id: int, 
        photo_type: str, 
        telegram_file_id: str,
        caption: Optional[str] = None
    ) -> TaskPhoto:
        """Добавление фото к задаче"""
        photo = TaskPhoto(
            task_id=task_id,
            photo_type=photo_type,
            file_path=f"telegram/{telegram_file_id}",
            telegram_file_id=telegram_file_id,
            caption=caption
        )
        
        self.session.add(photo)
        await self.session.commit()
        return photo
    
    async def add_task_comment(self, task_id: int, comment: str) -> MachineTask:
        """Добавление комментария к задаче"""
        task = await self.get_task_details(task_id)
        if not task:
            raise TaskNotFound("Задача не найдена")
        
        # Добавляем комментарий в result_data
        if not task.result_data:
            task.result_data = {}
        
        if "comments" not in task.result_data:
            task.result_data["comments"] = []
        
        task.result_data["comments"].append({
            "text": comment,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        await self.session.commit()
        return task
    
    async def report_problem(
        self, 
        task_id: int, 
        problem_type: str, 
        description: str,
        is_critical: bool = False
    ) -> TaskProblem:
        """Регистрация проблемы"""
        problem = TaskProblem(
            task_id=task_id,
            problem_type=ProblemType(problem_type),
            description=description,
            is_critical=is_critical
        )
        
        self.session.add(problem)
        await self.session.commit()
        return problem
