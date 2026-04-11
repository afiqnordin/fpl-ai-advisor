import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email(subject: str, html_content: str):
    """
    Sends an HTML email via Gmail SMTP.
    Requires GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT env variables.
    """
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("EMAIL_RECIPIENT")

    if not all([gmail_address, gmail_password, recipient]):
        raise ValueError("Missing email environment variables")

    # Build the email
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"FPL AI Advisor <{gmail_address}>"
    msg['To'] = recipient

    # Attach HTML content
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)

    # Send via Gmail SMTP
    print(f"📧 Sending email to {recipient}...")
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, recipient, msg.as_string())

    print(f"✅ Email sent successfully!")