import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional


def smtp_is_configured() -> bool:
    return all(
        os.getenv(key, "").strip()
        for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "MAIL_FROM")
    )


def send_email(subject: str, recipient: str, text_body: str, html_body: Optional[str] = None) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("MAIL_FROM", "").strip()
    use_ssl = os.getenv("SMTP_USE_SSL", "false").strip().lower() == "true"

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
