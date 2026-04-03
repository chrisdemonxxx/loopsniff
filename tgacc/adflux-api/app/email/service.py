"""Email service using SendGrid for transactional emails."""

import logging
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_client() -> Optional[SendGridAPIClient]:
    settings = get_settings()
    if not settings.SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not configured — emails will be logged only")
        return None
    return SendGridAPIClient(settings.SENDGRID_API_KEY)


async def send_verification_email(to_email: str, token: str, username: str = "") -> bool:
    """Send email verification link. Returns True on success."""
    settings = get_settings()
    verify_url = f"{settings.FRONTEND_URL}/verify?token={token}"
    subject = "Verify your AdFlux account"
    html = f"""
    <h2>Welcome to AdFlux{f', {username}' if username else ''}!</h2>
    <p>Please verify your email address by clicking the link below:</p>
    <p><a href="{verify_url}" style="background:#2563eb;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;">Verify Email</a></p>
    <p>Or copy this link: {verify_url}</p>
    <p>This link expires in 24 hours.</p>
    """
    return await _send_email(to_email, subject, html)


async def send_password_reset_email(to_email: str, token: str) -> bool:
    """Send password reset link. Returns True on success."""
    settings = get_settings()
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    subject = "Reset your AdFlux password"
    html = f"""
    <h2>Password Reset Request</h2>
    <p>Click the link below to reset your password:</p>
    <p><a href="{reset_url}" style="background:#2563eb;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;">Reset Password</a></p>
    <p>Or copy this link: {reset_url}</p>
    <p>This link expires in 1 hour. If you didn't request this, ignore this email.</p>
    """
    return await _send_email(to_email, subject, html)


async def send_admin_invite_email(to_email: str, invite_token: str, inviter_name: str = "") -> bool:
    """Send admin invitation email."""
    settings = get_settings()
    invite_url = f"{settings.ADMIN_URL}/accept-invite?token={invite_token}"
    subject = "You've been invited to AdFlux Admin"
    html = f"""
    <h2>Admin Invitation</h2>
    <p>{f'{inviter_name} has invited' if inviter_name else 'You have been invited'} you to join AdFlux as an administrator.</p>
    <p><a href="{invite_url}" style="background:#2563eb;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;">Accept Invitation</a></p>
    <p>This invitation expires in 48 hours.</p>
    """
    return await _send_email(to_email, subject, html)


async def _send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Internal: send an email via SendGrid. Falls back to logging if not configured."""
    client = _get_client()
    if not client:
        logger.info(f"[EMAIL-LOG] To: {to_email} | Subject: {subject}")
        return True  # Graceful degradation — log but don't block

    settings = get_settings()
    try:
        from_email = Email(settings.SENDGRID_FROM_EMAIL)
        message = Mail(
            from_email=from_email,
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content),
        )
        response = client.send(message)
        if response.status_code in (200, 201, 202):
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        else:
            logger.error(f"SendGrid returned {response.status_code} for {to_email}")
            return False
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
