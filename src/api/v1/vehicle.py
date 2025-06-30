# src/api/v1/vehicle.py

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.schemas import (
    VehicleLogCreate, VehicleLogResponse,
    ReportRequest, ReportResponse
)
from ...services import VehicleService, ReportService
from ...core.auth import get_current_user
from ...core.permissions import require_permissions
from ...db.models import User
from ...utils.storage import StorageService

router = APIRouter(tags=["vehicle_reports"])


# Vehicle endpoints

@router.post("/vehicles/{vehicle_id}/mileage")
async def add_mileage_log(
    vehicle_id: int,
    log_data: VehicleLogCreate,
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends()
):
    """Добавить запись о пробеге"""
    odometer_photo = None
    if file:
        odometer_photo = await storage.upload_file(
            file=file,
            folder=f"vehicles/{vehicle_id}/odometer"
        )
    
    service = VehicleService()
    log = await service.add_mileage_log(
        db=db,
        vehicle_id=vehicle_id,
        log_data=log_data,
        driver_id=current_user.id,
        odometer_photo=odometer_photo
    )
    return log


@router.post("/vehicles/{vehicle_id}/fuel")
async def add_fuel_log(
    vehicle_id: int,
    log_data: VehicleLogCreate,
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends()
):
    """Добавить запись о заправке"""
    receipt_photo = None
    if file:
        receipt_photo = await storage.upload_file(
            file=file,
            folder=f"vehicles/{vehicle_id}/receipts"
        )
    
    service = VehicleService()
    log = await service.add_fuel_log(
        db=db,
        vehicle_id=vehicle_id,
        log_data=log_data,
        driver_id=current_user.id,
        receipt_photo=receipt_photo
    )
    return log


@router.get("/vehicles/{vehicle_id}/logs", response_model=List[VehicleLogResponse])
async def get_vehicle_logs(
    vehicle_id: int,
    log_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить журнал транспорта"""
    service = VehicleService()
    logs = await service.get_vehicle_logs(
        db=db,
        vehicle_id=vehicle_id,
        log_type=log_type,
        date_from=date_from,
        date_to=date_to
    )
    return logs


@router.get("/vehicles/driver/{driver_id}/logs")
async def get_driver_logs(
    driver_id: int,
    date_from: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить записи водителя"""
    # Проверка прав
    if 'operator' in [r.name for r in current_user.roles] and \
       driver_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Нет доступа к записям другого водителя"
        )
    
    service = VehicleService()
    logs = await service.get_driver_logs(
        db=db,
        driver_id=driver_id,
        date_from=date_from
    )
    return logs


@router.get("/vehicles/{vehicle_id}/fuel-consumption")
@require_permissions(["vehicles.view_statistics"])
async def calculate_fuel_consumption(
    vehicle_id: int,
    period_days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Расчет расхода топлива"""
    service = VehicleService()
    consumption = await service.calculate_fuel_consumption(
        db=db,
        vehicle_id=vehicle_id,
        period_days=period_days
    )
    return consumption


@router.get("/vehicles/statistics")
@require_permissions(["vehicles.view_statistics"])
async def get_vehicle_statistics(
    vehicle_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Статистика по транспорту"""
    service = VehicleService()
    stats = await service.get_vehicle_statistics(
        db=db,
        vehicle_id=vehicle_id
    )
    return stats


@router.get("/vehicles/{vehicle_id}/maintenance-check")
@require_permissions(["vehicles.view"])
async def check_maintenance_needed(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Проверка необходимости ТО транспорта"""
    service = VehicleService()
    check = await service.check_maintenance_needed(db, vehicle_id)
    return check


# Reports endpoints

@router.get("/reports/sales")
@require_permissions(["reports.view"])
async def get_sales_report(
    date_from: datetime,
    date_to: datetime,
    machine_id: Optional[int] = Query(None),
    product_id: Optional[int] = Query(None),
    group_by: str = Query("day", regex="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отчет по продажам"""
    service = ReportService()
    report = await service.generate_sales_report(
        db=db,
        date_from=date_from,
        date_to=date_to,
        machine_id=machine_id,
        product_id=product_id,
        group_by=group_by
    )
    return report


@router.get("/reports/inventory")
@require_permissions(["reports.view"])
async def get_inventory_report(
    location_type: Optional[str] = Query(None),
    location_id: Optional[int] = Query(None),
    ingredient_id: Optional[int] = Query(None),
    include_movements: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отчет по остаткам"""
    service = ReportService()
    report = await service.generate_inventory_report(
        db=db,
        location_type=location_type,
        location_id=location_id,
        ingredient_id=ingredient_id,
        include_movements=include_movements
    )
    return report


@router.get("/reports/operator-performance")
@require_permissions(["reports.view_performance"])
async def get_operator_performance_report(
    date_from: datetime,
    date_to: datetime,
    operator_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отчет по эффективности операторов"""
    service = ReportService()
    report = await service.generate_operator_performance_report(
        db=db,
        date_from=date_from,
        date_to=date_to,
        operator_id=operator_id
    )
    return report


@router.get("/reports/machine-efficiency")
@require_permissions(["reports.view"])
async def get_machine_efficiency_report(
    date_from: datetime,
    date_to: datetime,
    machine_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отчет по эффективности автоматов"""
    service = ReportService()
    report = await service.generate_machine_efficiency_report(
        db=db,
        date_from=date_from,
        date_to=date_to,
        machine_id=machine_id
    )
    return report


@router.get("/reports/financial-summary")
@require_permissions(["reports.view_financial"])
async def get_financial_summary_report(
    date_from: datetime,
    date_to: datetime,
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Финансовый сводный отчет"""
    service = ReportService()
    report = await service.generate_financial_summary_report(
        db=db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id
    )
    return report


@router.get("/reports/investment-portfolio/{investor_id}")
@require_permissions(["reports.view_investment"])
async def get_investment_portfolio_report(
    investor_id: int,
    date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отчет по инвестиционному портфелю"""
    # Проверка прав доступа
    if 'investor' in [r.name for r in current_user.roles] and \
       investor_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Нет доступа к портфелю другого инвестора"
        )
    
    service = ReportService()
    report = await service.generate_investment_portfolio_report(
        db=db,
        investor_id=investor_id,
        as_of_date=date or datetime.now()
    )
    return report


@router.post("/reports/export/{report_type}")
@require_permissions(["reports.export"])
async def export_report(
    report_type: str,
    report_params: ReportRequest,
    format: str = Query("xlsx", regex="^(xlsx|pdf|csv)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Экспорт отчета в файл"""
    service = ReportService()
    
    # Генерация отчета
    if report_type == "sales":
        data = await service.generate_sales_report(
            db=db,
            **report_params.dict()
        )
    elif report_type == "inventory":
        data = await service.generate_inventory_report(
            db=db,
            **report_params.dict()
        )
    elif report_type == "operator_performance":
        data = await service.generate_operator_performance_report(
            db=db,
            **report_params.dict()
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный тип отчета: {report_type}"
        )
    
    # Экспорт в файл
    file_url = await service.export_report(
        report_data=data,
        report_type=report_type,
        format=format,
        user=current_user
    )
    
    return {"file_url": file_url, "format": format}


@router.get("/reports/dashboard/summary")
@require_permissions(["reports.view_dashboard"])
async def get_dashboard_summary(
    period: str = Query("today", regex="^(today|week|month|year)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Сводка для дашборда"""
    service = ReportService()
    summary = await service.generate_dashboard_summary(
        db=db,
        period=period,
        user=current_user
    )
    return summary