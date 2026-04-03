from uuid import UUID
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.models import Ticket, TicketMessage
from app.tickets.schemas import (
    TicketCreate,
    TicketUpdate,
    TicketMessageCreate,
    TicketMessageOut,
    TicketOut,
    TicketListOut,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


# ── Stats (must be before /{ticket_id} to avoid route conflict) ──

@router.get("/stats")
async def ticket_stats(
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    status_q = await db.execute(
        select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
    )
    priority_q = await db.execute(
        select(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority)
    )
    category_q = await db.execute(
        select(Ticket.category, func.count(Ticket.id)).group_by(Ticket.category)
    )
    return {
        "by_status": dict(status_q.all()),
        "by_priority": dict(priority_q.all()),
        "by_category": dict(category_q.all()),
    }


# ── List tickets ──

@router.get("", response_model=list[TicketListOut])
async def list_tickets(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Ticket)

    if user["user_type"] == "client":
        query = query.where(Ticket.client_id == user["client_id"])

    if status_filter:
        query = query.where(Ticket.status == status_filter)
    if priority:
        query = query.where(Ticket.priority == priority)
    if category:
        query = query.where(Ticket.category == category)
    if q:
        query = query.where(Ticket.subject.ilike(f"%{q}%"))

    query = query.order_by(Ticket.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tickets = result.scalars().all()

    out = []
    for t in tickets:
        count_result = await db.execute(
            select(func.count(TicketMessage.id)).where(TicketMessage.ticket_id == t.id)
        )
        msg_count = count_result.scalar() or 0
        out.append(
            TicketListOut(
                id=t.id,
                client_id=t.client_id,
                subject=t.subject,
                category=t.category,
                priority=t.priority,
                status=t.status,
                assigned_admin=t.assigned_admin,
                created_by_type=t.created_by_type,
                message_count=msg_count,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )
    return out


# ── Get single ticket ──

@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(
    ticket_id: UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.messages))
        .where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if user["user_type"] == "client" and ticket.client_id != user["client_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if user["user_type"] == "client":
        ticket.messages = [m for m in ticket.messages if not m.is_internal]

    return ticket


# ── Create ticket ──

@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user["user_type"] == "client":
        client_id = user["client_id"]
        created_by_type = "client"
        sender_type = "client"
        sender_id = user["id"]
    else:
        client_id = None
        created_by_type = "admin"
        sender_type = "admin"
        sender_id = user["id"]

    ticket = Ticket(
        client_id=client_id,
        subject=body.subject,
        category=body.category,
        priority=body.priority,
        status="open",
        created_by_type=created_by_type,
    )
    db.add(ticket)
    await db.flush()
    await db.commit()

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_type=sender_type,
        sender_id=sender_id,
        text=body.message,
        is_internal=False,
    )
    db.add(message)
    await db.flush()
    await db.commit()

    # Reload with messages
    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.messages))
        .where(Ticket.id == ticket.id)
    )
    return result.scalar_one()


# ── Update ticket ──

@router.put("/{ticket_id}", response_model=TicketOut)
async def update_ticket(
    ticket_id: UUID,
    body: TicketUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.messages))
        .where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if user["user_type"] == "client":
        if ticket.client_id != user["client_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        # Clients can only close their own tickets
        if body.status and body.status != "closed":
            raise HTTPException(status_code=403, detail="Clients can only close tickets")
        if body.priority or body.assigned_admin or body.category:
            raise HTTPException(status_code=403, detail="Only admins can update these fields")
        if body.status == "closed":
            ticket.status = "closed"
    else:
        if body.status is not None:
            ticket.status = body.status
        if body.priority is not None:
            ticket.priority = body.priority
        if body.assigned_admin is not None:
            ticket.assigned_admin = body.assigned_admin
        if body.category is not None:
            ticket.category = body.category

    if ticket.status == "resolved" and ticket.resolved_at is None:
        ticket.resolved_at = datetime.utcnow()

    ticket.updated_at = datetime.utcnow()
    await db.flush()
    await db.commit()

    if user["user_type"] == "client":
        ticket.messages = [m for m in ticket.messages if not m.is_internal]

    return ticket


# ── Add message ──

@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    ticket_id: UUID,
    body: TicketMessageCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if user["user_type"] == "client":
        if ticket.client_id != user["client_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        if body.is_internal:
            raise HTTPException(status_code=403, detail="Clients cannot create internal notes")
        sender_type = "client"
    else:
        sender_type = "admin"

    message = TicketMessage(
        ticket_id=ticket_id,
        sender_type=sender_type,
        sender_id=user["id"],
        text=body.text,
        is_internal=body.is_internal if user["user_type"] == "admin" else False,
    )
    db.add(message)

    ticket.updated_at = datetime.utcnow()
    await db.flush()
    await db.commit()

    return message
