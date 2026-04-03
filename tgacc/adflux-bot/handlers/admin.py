import asyncio
from datetime import date, datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from config import ADMIN_CHAT_ID
from middlewares.i18n import t
from handlers.start import stats as user_stats
from handlers.order_flow import leads, leads_today
from db.conversations import (
    get_recent_conversations,
    get_user_history,
    get_user_by_username,
    get_all_user_ids,
    get_user_count,
    log_message,
)

router = Router()


def _is_admin(uid: int) -> bool:
    return uid == ADMIN_CHAT_ID


def _ts_fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%m/%d %H:%M")


# ── /admin ────────────────────────────────────────────────────────────────


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    uid = message.from_user.id
    if not _is_admin(uid):
        await message.answer(t(uid, "admin_not_authorized"), parse_mode=ParseMode.HTML)
        return

    today = str(date.today())
    total_users = len(user_stats["users"])
    total_leads = len(leads)
    today_users = len(user_stats["today_users"].get(today, set()))
    today_leads_count = leads_today.get(today, 0)
    db_users = await get_user_count()

    if leads:
        recent = leads[-5:]
        recent_lines = []
        for i, lead in enumerate(reversed(recent), 1):
            recent_lines.append(
                f"{i}. {lead['user_name']} — {lead['platform']} / {lead['niche']} / {lead['budget']}"
            )
        recent_text = "\n".join(recent_lines)
    else:
        recent_text = t(uid, "admin_no_leads")

    text = t(
        uid,
        "admin_panel",
        total_users=total_users,
        total_leads=total_leads,
        today_users=today_users,
        today_leads=today_leads_count,
        recent_leads=recent_text,
    )
    text += f"\n\n📊 <b>DB Users:</b> {db_users}"
    text += "\n\n<b>Commands:</b>"
    text += "\n/conversations — Recent chats"
    text += "\n/conversation @user — View user chat"
    text += "\n/broadcast &lt;msg&gt; — Send to all users"
    text += "\n/broadcast_preview &lt;msg&gt; — Preview first"

    await message.answer(text, parse_mode=ParseMode.HTML)


# ── /conversations ────────────────────────────────────────────────────────


@router.message(Command("conversations"))
async def cmd_conversations(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    convos = await get_recent_conversations(20)
    if not convos:
        await message.answer("📭 No conversations yet.")
        return

    lines = ["<b>💬 Recent Conversations</b>\n"]
    buttons = []
    for c in convos:
        name = f"@{c['username']}" if c["username"] else c.get("first_name", "Unknown")
        time_str = _ts_fmt(c["last_seen"])
        last = (c.get("last_msg") or "")[:40]
        lines.append(f"• <b>{name}</b> ({c['msg_count']} msgs, {time_str})\n  └ {last}")
        buttons.append(
            [InlineKeyboardButton(
                text=f"👁 {name}", callback_data=f"conv:{c['user_id']}:0"
            )]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons[:10])
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)


# ── /conversation @username ───────────────────────────────────────────────


@router.message(Command("conversation"))
async def cmd_conversation_user(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /conversation @username")
        return

    username = parts[1].lstrip("@")
    user = await get_user_by_username(username)
    if not user:
        await message.answer(f"❌ No conversations found for @{username}")
        return

    await _send_history(message, user["user_id"], username, 0)


# ── Conversation view callback ────────────────────────────────────────────


@router.callback_query(F.data.startswith("conv:"))
async def cb_view_conversation(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("⛔ Admin only")
        return

    parts = callback.data.split(":")
    user_id = int(parts[1])
    offset = int(parts[2]) if len(parts) > 2 else 0

    msgs = await get_user_history(user_id, limit=20, offset=offset)
    if not msgs:
        await callback.answer("No messages found")
        return

    user = None
    if msgs:
        user = msgs[0].get("username", str(user_id))

    lines = [f"<b>💬 Chat with {user or user_id}</b>\n"]
    for m in reversed(msgs):
        arrow = "➡️" if m["direction"] == "out" else "⬅️"
        time_str = _ts_fmt(m["ts"])
        text = (m.get("text") or "")[:100]
        lines.append(f"{arrow} <i>{time_str}</i> {text}")

    nav_buttons = []
    if offset > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Newer", callback_data=f"conv:{user_id}:{max(0, offset - 20)}")
        )
    if len(msgs) == 20:
        nav_buttons.append(
            InlineKeyboardButton(text="Older ➡️", callback_data=f"conv:{user_id}:{offset + 20}")
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[nav_buttons] if nav_buttons else [])

    try:
        await callback.message.edit_text(
            "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb
        )
    except Exception:
        await callback.message.answer(
            "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb
        )
    await callback.answer()


async def _send_history(message: Message, user_id: int, username: str, offset: int) -> None:
    msgs = await get_user_history(user_id, limit=20, offset=offset)
    if not msgs:
        await message.answer("📭 No messages.")
        return

    lines = [f"<b>💬 Chat with @{username}</b>\n"]
    for m in reversed(msgs):
        arrow = "➡️" if m["direction"] == "out" else "⬅️"
        time_str = _ts_fmt(m["ts"])
        text = (m.get("text") or "")[:100]
        lines.append(f"{arrow} <i>{time_str}</i> {text}")

    nav_buttons = []
    if offset > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Newer", callback_data=f"conv:{user_id}:{max(0, offset - 20)}")
        )
    if len(msgs) == 20:
        nav_buttons.append(
            InlineKeyboardButton(text="Older ➡️", callback_data=f"conv:{user_id}:{offset + 20}")
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[nav_buttons] if nav_buttons else [])
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)


# ── /broadcast ────────────────────────────────────────────────────────────


@router.message(Command("broadcast_preview"))
async def cmd_broadcast_preview(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        await message.answer("Usage: /broadcast_preview &lt;message&gt;", parse_mode=ParseMode.HTML)
        return

    content = text[1]
    await message.answer(f"📋 <b>Preview:</b>\n\n{content}", parse_mode=ParseMode.HTML)
    await message.answer("✅ Looks good? Use /broadcast to send to all users.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        await message.answer("Usage: /broadcast &lt;message&gt;", parse_mode=ParseMode.HTML)
        return

    content = text[1]
    user_ids = await get_all_user_ids()

    if not user_ids:
        await message.answer("❌ No users in database yet.")
        return

    status_msg = await message.answer(f"📤 Sending to {len(user_ids)} users...")
    sent = 0
    failed = 0
    blocked = 0

    for i, uid in enumerate(user_ids):
        if uid == ADMIN_CHAT_ID:
            continue
        try:
            await message.bot.send_message(uid, content, parse_mode=ParseMode.HTML)
            await log_message(uid, None, None, "out", content)
            sent += 1
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err:
                blocked += 1
            else:
                failed += 1

        # Rate limit: 25 msgs/sec
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)
            # Update progress every 50
            if (i + 1) % 50 == 0:
                try:
                    await status_msg.edit_text(
                        f"📤 Progress: {i + 1}/{len(user_ids)} (✅ {sent} | ❌ {failed} | 🚫 {blocked})"
                    )
                except Exception:
                    pass

    await status_msg.edit_text(
        f"✅ <b>Broadcast complete!</b>\n\n"
        f"📨 Sent: {sent}\n"
        f"🚫 Blocked/Deactivated: {blocked}\n"
        f"❌ Failed: {failed}\n"
        f"📊 Total: {len(user_ids)}",
        parse_mode=ParseMode.HTML,
    )
