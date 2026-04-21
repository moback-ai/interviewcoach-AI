import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from common.runtime_config import load_runtime_config, optional_env, require_env

load_runtime_config()


def smtp_is_configured() -> bool:
    try:
        return all(
            require_env(key)
            for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM")
        )
    except Exception:
        return False


def send_email(subject: str, recipient: str, text_body: str, html_body: Optional[str] = None) -> None:
    host = require_env("SMTP_HOST")
    port = int(require_env("SMTP_PORT"))
    user = require_env("SMTP_USER")
    password = require_env("SMTP_PASSWORD")
    sender = require_env("MAIL_FROM")
    use_ssl = optional_env("SMTP_USE_SSL", "false").lower() == "true"

    if not host or not user or not password or not sender:
        raise RuntimeError("SMTP is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and MAIL_FROM.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as server:
            server.login(user, password)
            server.send_message(message)
        return

    with smtplib.SMTP(host, port) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(user, password)
        server.send_message(message)
