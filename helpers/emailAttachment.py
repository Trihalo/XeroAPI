import os
import smtplib
from email.message import EmailMessage
import mimetypes


def sendEmailWithAttachment(recipients, subject, body, file_path):
    """Sends an email with an attachment to multiple recipients using Gmail SMTP."""

    sender_email = os.getenv("EMAIL_SENDER") 
    sender_password = os.getenv("EMAIL_PASSWORD")

    if not sender_email or not sender_password:
        raise Exception(
            "❌ Missing email credentials. Set EMAIL_SENDER and EMAIL_PASSWORD as environment variables.")

    if isinstance(recipients, str):
        recipients = [recipients] 
    recipient_list = ", ".join(recipients)

    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = recipient_list 
    msg["Subject"] = subject
    msg.set_content(body)

    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    with open(file_path, "rb") as attachment:
        msg.add_attachment(attachment.read(), maintype=mime_type.split(
            "/")[0], subtype=mime_type.split("/")[1], filename=os.path.basename(file_path))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print(f"📧 Email sent successfully to {recipient_list}")

    except Exception as e:
        print(f"❌ Error sending email: {e}")
