from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

from flask import current_app


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def get_email_settings() -> dict[str, Any]:
    """
    SMTP settings are read directly from environment variables / .env.

    Works with:
    - normal SMTP mailbox
    - SendGrid SMTP Relay
    - Mailgun SMTP
    - any provider with SMTP credentials
    """
    host = os.getenv("SMTP_HOST", "").strip()
    port = _int_env("SMTP_PORT", 587)
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()

    use_tls = _bool_env("SMTP_USE_TLS", True)
    use_ssl = _bool_env("SMTP_USE_SSL", False)

    mail_from = os.getenv("MAIL_FROM", username or "office@austria-express.eu").strip()
    mail_from_name = os.getenv("MAIL_FROM_NAME", "Austria Express Website").strip()
    notification_to = os.getenv("NOTIFICATION_TO", "office@austria-express.eu").strip()

    enabled = _bool_env("EMAIL_NOTIFICATIONS_ENABLED", False)

    ready = bool(enabled and host and port and mail_from and notification_to)
    # Username/password are optional because some internal SMTP relays do not require auth.
    auth_configured = bool(username and password)

    return {
        "enabled": enabled,
        "ready": ready,
        "host": host,
        "port": port,
        "username": username,
        "password_set": bool(password),
        "auth_configured": auth_configured,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "mail_from": mail_from,
        "mail_from_name": mail_from_name,
        "notification_to": notification_to,
    }


def _format_from(settings: dict[str, Any]) -> str:
    name = settings.get("mail_from_name") or "Austria Express Website"
    email = settings.get("mail_from") or "office@austria-express.eu"
    return f"{name} <{email}>"


def send_email(subject: str, body: str, *, reply_to: str | None = None, to_email: str | None = None) -> tuple[bool, str]:
    settings = get_email_settings()

    if not settings["enabled"]:
        return False, "EMAIL_NOTIFICATIONS_ENABLED is not true"

    if not settings["host"]:
        return False, "SMTP_HOST is missing"

    recipient = to_email or settings["notification_to"]
    if not recipient:
        return False, "NOTIFICATION_TO is missing"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _format_from(settings)
    msg["To"] = recipient

    if reply_to:
        msg["Reply-To"] = reply_to

    msg.set_content(body)

    try:
        if settings["use_ssl"]:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings["host"], settings["port"], context=context, timeout=20) as smtp:
                if settings["username"] and settings["password_set"]:
                    smtp.login(settings["username"], os.getenv("SMTP_PASSWORD", ""))
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as smtp:
                smtp.ehlo()
                if settings["use_tls"]:
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                if settings["username"] and settings["password_set"]:
                    smtp.login(settings["username"], os.getenv("SMTP_PASSWORD", ""))
                smtp.send_message(msg)

        return True, "sent"

    except Exception as exc:
        current_app.logger.exception("Email notification failed")
        return False, str(exc)


def notify_contact_request(contact_request) -> tuple[bool, str]:
    subject = f"Neue Kontaktanfrage #{contact_request.id} – Austria Express"

    body = f"""Neue Kontaktanfrage über die Website

ID:
{contact_request.id}

Name:
{contact_request.name}

Organisation:
{contact_request.organisation or "-"}

E-Mail:
{contact_request.email}

Telefon:
{contact_request.phone or "-"}

Anfrageart:
{contact_request.request_type or "-"}

Bevorzugter Kontakt:
{contact_request.preferred_contact or "-"}

Betreff:
{contact_request.subject or "-"}

Nachricht:
{contact_request.message}

Admin:
Bitte im Adminbereich öffnen und bearbeiten:
{_admin_hint("/admin/contact-requests/" + str(contact_request.id))}
"""

    return send_email(subject, body, reply_to=contact_request.email)


def notify_bus_rental_request(inquiry) -> tuple[bool, str]:
    subject = f"Neue Bus Rental Anfrage #{inquiry.id} – {inquiry.departure_place} → {inquiry.destination}"

    requirements = []
    if getattr(inquiry, "req_wc", False):
        requirements.append("WC")
    if getattr(inquiry, "req_usb", False):
        requirements.append("USB")
    if getattr(inquiry, "req_power", False):
        requirements.append("220V")
    if getattr(inquiry, "req_wifi", False):
        requirements.append("WLAN")
    if getattr(inquiry, "req_doubledecker", False):
        requirements.append("Doppeldecker")
    if getattr(inquiry, "req_kitchen", False):
        requirements.append("Bordküche")

    body = f"""Neue Bus Rental Anfrage über die Website

ID:
{inquiry.id}

Kontakt:
{inquiry.contact_name}
{inquiry.organisation or "-"}

E-Mail:
{inquiry.email}

Telefon:
{inquiry.phone or "-"}

Kundentyp:
{inquiry.customer_type or "-"}

Reisetyp:
{inquiry.trip_type or "-"}

Route:
{inquiry.departure_place} → {inquiry.destination}

Datum:
{inquiry.date_start or "-"} {("bis " + str(inquiry.date_end)) if inquiry.date_end else ""}

Zeit:
{inquiry.time_departure or "-"} {(" / Rückfahrt " + str(inquiry.time_return)) if inquiry.time_return else ""}

Tage:
{inquiry.days or "-"}

Passagiere:
{inquiry.passengers or "-"}

Bus:
{inquiry.bus_size or "-"} / Anzahl Busse: {inquiry.bus_count or "-"}

Anforderungen:
{", ".join(requirements) if requirements else "-"}

Route / Programm:
{inquiry.route_description or "-"}

Gruppenhinweise:
{inquiry.group_notes or "-"}

Besonderheiten:
{inquiry.special_needs or "-"}

Admin:
Bitte im Adminbereich öffnen und kalkulieren:
{_admin_hint("/admin/bus-rental-requests/" + str(inquiry.id))}
"""

    return send_email(subject, body, reply_to=inquiry.email)


def send_test_notification() -> tuple[bool, str]:
    subject = "Test E-Mail – Austria Express Website"
    body = """Dies ist eine Test-E-Mail aus dem Austria Express Adminbereich.

Wenn diese Nachricht angekommen ist, funktionieren die SMTP Einstellungen.

Automatische Benachrichtigungen können für folgende Ereignisse verwendet werden:
- neue Kontaktanfrage
- neue Bus Rental Anfrage
"""
    return send_email(subject, body)


def _admin_hint(path: str) -> str:
    base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base_url:
        return base_url + path
    return path
