"""Async Telethon operations shared by MCP tools and in-process FunctionTools."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, List, Optional

from telethon.tl.functions.channels import CreateChannelRequest, EditAdminRequest, EditBannedRequest, EditTitleRequest, GetParticipantsRequest, InviteToChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.types import ChatAdminRights, ChatBannedRights, ChannelParticipantsRecent

log = logging.getLogger("mcp_telegram.ops")


def _admin_usernames() -> list[str]:
    raw = os.getenv("KLIQ_ADMIN_USERNAMES", "Bigbunnn,David_Bazzana")
    return [u.strip() for u in raw.split(",") if u.strip()]


def admin_ids_list() -> list[int]:
    raw = os.getenv("KLIQ_ADMIN_IDS", "6136131094,8756787507")
    out: list[int] = []
    for p in raw.split(","):
        p = p.strip()
        if p.isdigit():
            out.append(int(p))
    return out


async def resolve_admin_entities(client) -> list:
    entities = []
    for uname in _admin_usernames():
        try:
            entities.append(await client.get_input_entity(uname))
        except Exception as exc:
            log.warning("Could not resolve admin @%s: %s", uname, exc)
    if not entities:
        for uid in admin_ids_list():
            try:
                entities.append(await client.get_input_entity(uid))
            except Exception:
                pass
    return entities


async def create_deal_room(
    client,
    lead_username: str,
    lead_user_id: int,
    *,
    admin_entities: Optional[list] = None,
) -> dict | None:
    """Create private supergroup + invite admins + invite lead + generate invite link."""
    title = f"KliqBoost | @{lead_username}"
    about = "Private deal room — KliqBoost Media"
    try:
        result = await client(
            CreateChannelRequest(title=title, about=about, megagroup=True)
        )
        group = result.chats[0]
        group_id = group.id
        log.info("Created deal room: %s id=%s", title, group_id)

        # 1. Invite admins into the group FIRST (must be members before promoting)
        admins = admin_entities if admin_entities is not None else await resolve_admin_entities(client)
        for admin_entity in admins:
            try:
                await client(InviteToChannelRequest(channel=group, users=[admin_entity]))
            except Exception:
                pass  # May already be a member

        # 2. Promote admins
        admin_rights = ChatAdminRights(
            invite_users=True,
            ban_users=True,
            pin_messages=True,
            change_info=False,
            delete_messages=True,
            add_admins=False,
        )
        for admin_entity in admins:
            try:
                await client(
                    EditAdminRequest(
                        channel=group,
                        user_id=admin_entity,
                        admin_rights=admin_rights,
                        rank="Team",
                    )
                )
            except Exception as exc:
                log.warning("Could not promote admin: %s", exc)

        # 3. Invite the lead directly into the group
        lead_invited = False
        try:
            lead_entity = None
            try:
                lead_entity = await client.get_input_entity(lead_username)
            except Exception:
                try:
                    lead_entity = await client.get_input_entity(lead_user_id)
                except Exception:
                    pass
            if lead_entity:
                await client(InviteToChannelRequest(channel=group, users=[lead_entity]))
                lead_invited = True
                log.info("Invited lead @%s directly into deal room", lead_username)
        except Exception as exc:
            log.warning("Could not invite lead directly: %s", exc)

        # 4. Generate invite link as backup
        invite = await client(ExportChatInviteRequest(peer=group))
        return {
            "group_id": group_id,
            "lead_username": lead_username,
            "lead_user_id": lead_user_id,
            "invite_link": invite.link,
            "group_title": title,
            "created_at": time.time(),
            "lead_invited_directly": lead_invited,
        }
    except Exception as exc:
        log.error("create_deal_room failed: %s", exc)
        return None


async def send_dm(client, user_id: int, text: str) -> dict[str, Any]:
    await client.send_message(user_id, text)
    return {"ok": True, "user_id": user_id}


async def archive_deal_room_title(client, channel: Any, lead_username: str) -> dict[str, Any]:
    try:
        await client(EditTitleRequest(channel=channel, title=f"✅ KliqBoost | @{lead_username} (closed)"))
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:400]}


async def kick_non_admins(client, channel: Any, admin_ids: List[int], me_id: int) -> dict[str, Any]:
    kicked = 0
    try:
        participants = await client(
            GetParticipantsRequest(
                channel=channel,
                filter=ChannelParticipantsRecent(),
                offset=0,
                limit=100,
                hash=0,
            )
        )
        admin_set = set(admin_ids + [me_id])
        for p in participants.users:
            if p.id not in admin_set and not getattr(p, "bot", False):
                try:
                    await client(
                        EditBannedRequest(
                            channel=channel,
                            participant=p.id,
                            banned_rights=ChatBannedRights(until_date=0, view_messages=True),
                        )
                    )
                    await client(
                        EditBannedRequest(
                            channel=channel,
                            participant=p.id,
                            banned_rights=ChatBannedRights(until_date=0, view_messages=False),
                        )
                    )
                    kicked += 1
                except Exception:
                    pass
        return {"ok": True, "kicked": kicked}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:400], "kicked": kicked}
