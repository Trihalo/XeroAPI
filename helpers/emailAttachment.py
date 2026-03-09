import os
import logging
import smtplib
import mimetypes
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

load_dotenv()

SMTP_PROVIDERS = {
    "GMAIL": ("smtp.gmail.com", 587),
    "OUTLOOK": ("smtp.office365.com", 587),
}


def sendEmail(
    recipients,
    subject,
    body_text,
    provider,
    body_html=None,
    attachments=None,
    cc=None,
):
    """
    Send an email with optional HTML body and multiple attachments.

    Args:
        recipients (str | list[str]): To addresses.
        subject (str): Email subject.
        body_text (str): Plain-text fallback body.
        provider (str): "GMAIL" or "OUTLOOK".
        body_html (str | None): HTML body. If provided, sends multipart/alternative.
        attachments (str | list[str] | None): File path(s) to attach.
        cc (str | list[str] | None): CC addresses.

    Raises:
        ValueError: If provider is unsupported or credentials are missing.
        smtplib.SMTPException: On SMTP-level failures.
    """
    provider = provider.upper()
    if provider not in SMTP_PROVIDERS:
        raise ValueError(f"Unsupported provider '{provider}'. Use one of: {list(SMTP_PROVIDERS)}")

    sender_email = os.getenv(f"EMAIL_SENDER_{provider}")
    sender_password = os.getenv(f"EMAIL_PASSWORD_{provider}")
    if not sender_email or not sender_password:
        raise ValueError(
            f"Missing credentials. Set EMAIL_SENDER_{provider} and EMAIL_PASSWORD_{provider}."
        )

    if isinstance(recipients, str):
        recipients = [recipients]
    if isinstance(cc, str):
        cc = [cc]
    if isinstance(attachments, str):
        attachments = [attachments]
    attachments = [a for a in (attachments or []) if a and os.path.exists(a)]

    # Build message
    msg = MIMEMultipart("mixed")
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)

    # Body: multipart/alternative for plain+html, or plain only
    if body_html:
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text, "plain"))
        alt.attach(MIMEText(body_html, "html"))
        msg.attach(alt)
    else:
        msg.attach(MIMEText(body_text, "plain"))

    # Attachments
    for file_path in attachments:
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"
        maintype, subtype = mime_type.split("/", 1)

        with open(file_path, "rb") as f:
            data = f.read()

        part = MIMEBase(maintype, subtype)
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=os.path.basename(file_path))
        msg.attach(part)

    smtp_host, smtp_port = SMTP_PROVIDERS[provider]
    all_recipients = recipients + (cc or [])

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, all_recipients, msg.as_string())

    logging.info(f"Email '{subject}' sent to {', '.join(all_recipients)}")


# ---------------------------------------------------------------------------
# Back-compat shim — keeps existing callers working without changes
# ---------------------------------------------------------------------------
def sendEmailWithAttachment(recipients, subject, body, provider, file_path=None):
    sendEmail(
        recipients=recipients,
        subject=subject,
        body_text=body,
        provider=provider,
        attachments=[file_path] if file_path else None,
    )
