from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional

from app.database import get_db
from app.models import Client, AdAccount
from app.auth.dependencies import get_current_user, require_admin
from app.clients.schemas import ClientCreate, ClientUpdate, ClientOut, ClientStats

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientOut])
async def list_clients(
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Client)
    if q:
        stmt = stmt.where(or_(Client.name.ilike(f"%{q}%"), Client.company.ilike(f"%{q}%"), Client.email.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(Client.status == status)
    if plan:
        stmt = stmt.where(Client.plan == plan)
    stmt = stmt.order_by(Client.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/stats", response_model=ClientStats)
async def client_stats(user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Client.id)))).scalar() or 0
    active = (await db.execute(select(func.count(Client.id)).where(Client.status == "active"))).scalar() or 0
    accts = (await db.execute(select(func.count(AdAccount.id)))).scalar() or 0
    spend = (await db.execute(select(func.coalesce(func.sum(AdAccount.total_spend), 0)))).scalar()
    return ClientStats(total_clients=total, active_clients=active, total_accounts=accts, total_spend=spend)


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(client_id: UUID, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # S2: Clients can only access their own data
    if user.get("user_type") == "client" and user.get("client_id") and str(user["client_id"]) != str(client_id):
        raise HTTPException(status_code=403, detail="Access denied")
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("", response_model=ClientOut, status_code=201)
async def create_client(data: ClientCreate, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    client = Client(**data.model_dump())
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client


@router.put("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: UUID, data: ClientUpdate,
    user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(client, k, v)
    await db.flush()
    await db.refresh(client)
    return client


@router.delete("/{client_id}")
async def delete_client(client_id: UUID, user: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    await db.delete(client)
    return {"detail": "Client deleted"}
