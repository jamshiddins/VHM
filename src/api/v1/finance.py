# src/api/v1/finance.py

from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.schemas import (
    FinanceAccountCreate, FinanceAccountResponse,
    FinanceTransactionCreate, FinanceTransactionResponse,
    CashCollectionCreate, CashCollectionResponse,
    CashDenominationCreate
)
from ...services import FinanceService, CashCollectionService
from ...core.auth import get_current_user
from ...core.permissions import require_permissions
from ...db.models import User
from ...utils.storage import StorageService

router = APIRouter(tags=["finance"])


# Finance Account endpoints

@router.get("/accounts", response_model=List[FinanceAccountResponse])
@require_permissions(["finance.view_accounts"])
async def get_accounts(
    account_type: Optional[str] = Query(None),
    is_active: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список счетов"""
    service = FinanceService()
    
    filters = {'is_active': is_active}
    if account_type:
        filters['account_type'] = account_type
    
    accounts = await service.get_accounts(db, filters=filters)
    return accounts


@router.post("/accounts", response_model=FinanceAccountResponse)
@require_permissions(["finance.create_account"])
async def create_account(
    account_data: FinanceAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать новый счет"""
    service = FinanceService()
    account = await service.create_account(
        db=db,
        account_data=account_data,
        current_user=current_user
    )
    return account


@router.get("/accounts/{account_id}/balance")
@require_permissions(["finance.view_accounts"])
async def get_account_balance(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить баланс счета"""
    service = FinanceService()
    balance = await service.get_account_balance(db, account_id)
    return {"account_id": account_id, "balance": balance}


# Transaction endpoints

@router.get("/transactions", response_model=List[FinanceTransactionResponse])
@require_permissions(["finance.view_transactions"])
async def get_transactions(
    account_id: Optional[int] = Query(None),
    transaction_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список транзакций"""
    service = FinanceService()
    transactions = await service.get_transactions(
        db=db,
        account_id=account_id,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit
    )
    return transactions


@router.post("/transactions", response_model=FinanceTransactionResponse)
@require_permissions(["finance.create_transaction"])
async def create_transaction(
    transaction_data: FinanceTransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Создать транзакцию"""
    service = FinanceService()
    transaction = await service.create_transaction(
        db=db,
        transaction_data=transaction_data,
        current_user=current_user
    )
    return transaction


@router.post("/transactions/transfer")
@require_permissions(["finance.create_transfer"])
async def create_transfer(
    from_account_id: int,
    to_account_id: int,
    amount: Decimal,
    description: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Перевод между счетами"""
    service = FinanceService()
    transactions = await service.create_transfer(
        db=db,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount=amount,
        description=description,
        current_user=current_user
    )
    return {
        "message": "Перевод выполнен успешно",
        "debit_transaction": transactions[0],
        "credit_transaction": transactions[1]
    }


@router.get("/reports/cash-flow")
@require_permissions(["finance.view_reports"])
async def get_cash_flow_report(
    date_from: datetime,
    date_to: datetime,
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отчет о движении денежных средств"""
    service = FinanceService()
    report = await service.get_cash_flow_report(
        db=db,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id
    )
    return report


@router.get("/reports/balance-sheet")
@require_permissions(["finance.view_reports"])
async def get_balance_sheet(
    date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Балансовый отчет"""
    service = FinanceService()
    report = await service.get_balance_sheet(
        db=db,
        as_of_date=date or datetime.now()
    )
    return report


# Cash Collection endpoints

@router.post("/cash-collection/start", response_model=CashCollectionResponse)
async def start_cash_collection(
    machine_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends()
):
    """Начать инкассацию"""
    # Загрузка фото до инкассации
    before_photo_url = await storage.upload_file(
        file=file,
        folder=f"cash_collection/{machine_id}/before"
    )
    
    service = CashCollectionService()
    collection = await service.start_collection(
        db=db,
        machine_id=machine_id,
        operator_id=current_user.id,
        before_photo_url=before_photo_url
    )
    return collection


@router.post("/cash-collection/{collection_id}/denominations")
async def add_cash_denominations(
    collection_id: int,
    denominations: List[CashDenominationCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Добавить купюры по номиналам"""
    service = CashCollectionService()
    collection = await service.add_denominations(
        db=db,
        collection_id=collection_id,
        denominations=denominations,
        operator_id=current_user.id
    )
    return collection


@router.post("/cash-collection/{collection_id}/complete")
async def complete_cash_collection(
    collection_id: int,
    file: UploadFile = File(...),
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends()
):
    """Завершить инкассацию"""
    # Загрузка фото после инкассации
    after_photo_url = await storage.upload_file(
        file=file,
        folder=f"cash_collection/{collection_id}/after"
    )
    
    service = CashCollectionService()
    collection = await service.complete_collection(
        db=db,
        collection_id=collection_id,
        operator_id=current_user.id,
        after_photo_url=after_photo_url,
        notes=notes
    )
    return collection


@router.post("/cash-collection/{collection_id}/verify")
@require_permissions(["finance.verify_collection"])
async def verify_cash_collection(
    collection_id: int,
    is_approved: bool,
    verification_notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Проверить инкассацию"""
    service = CashCollectionService()
    collection = await service.verify_collection(
        db=db,
        collection_id=collection_id,
        verifier_id=current_user.id,
        is_approved=is_approved,
        verification_notes=verification_notes
    )
    return collection


@router.get("/cash-collection/machine/{machine_id}")
@require_permissions(["finance.view_collections"])
async def get_machine_collections(
    machine_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """История инкассаций автомата"""
    service = CashCollectionService()
    collections = await service.get_machine_collections(
        db=db,
        machine_id=machine_id,
        limit=limit
    )
    return collections


@router.get("/cash-collection/operator/{operator_id}")
async def get_operator_collections(
    operator_id: int,
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Инкассации оператора"""
    # Проверка прав
    if 'operator' in [r.name for r in current_user.roles] and \
       operator_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Нет доступа к инкассациям другого оператора"
        )
    
    service = CashCollectionService()
    collections = await service.get_operator_collections(
        db=db,
        operator_id=operator_id,
        status=status,
        date_from=date_from
    )
    return collections


@router.get("/cash-collection/pending")
@require_permissions(["finance.verify_collection"])
async def get_pending_collections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Инкассации, ожидающие проверки"""
    service = CashCollectionService()
    collections = await service.get_pending_verifications(db)
    return collections


@router.get("/cash-collection/statistics")
@require_permissions(["finance.view_statistics"])
async def get_collection_statistics(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Статистика инкассаций"""
    service = CashCollectionService()
    stats = await service.get_collection_statistics(
        db=db,
        date_from=date_from,
        date_to=date_to
    )
    return stats