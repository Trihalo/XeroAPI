import os
import smtplib
from email.message import EmailMessage
import mimetypes
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def sendEmailWithAttachment(recipients, subject, body, provider, file_path=None):
    """Sends an email with an attachment to multiple recipients using an SMTP Provider."""

    sender_email = os.getenv(f"EMAIL_SENDER_{provider}")
    sender_password = os.getenv(f"EMAIL_PASSWORD_{provider}")

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

    if file_path is not None and not os.path.exists(file_path):
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"
        with open(file_path, "rb") as attachment:
            msg.add_attachment(attachment.read(), maintype=mime_type.split(
                "/")[0], subtype=mime_type.split("/")[1], filename=os.path.basename(file_path))

    if provider == "OUTLOOK": emailUrl = "smtp.office365.com"
    elif provider == "GMAIL": emailUrl = "smtp.gmail.com"
    
    try:
        with smtplib.SMTP(emailUrl, 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print(f"📧 Email sent successfully to {recipient_list}")

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication error: {e.smtp_code} - {e.smtp_error}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")


if __name__ == "__main__":
    recipients = ["leo@trihalo.com.au"]
    subject = "ATB Report"
    time = (datetime.now() + timedelta(hours=11)).strftime("%d-%m-%Y %I:%M%p").lower()
    body = f"Hi Leo,\n\n This is a test email{time}.\n\nThanks"

    sendEmailWithAttachment(recipients, subject, body, provider="GMAIL")