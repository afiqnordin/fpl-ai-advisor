# email_sender.py
# Sends HTML email with embedded chart images via Gmail SMTP.
# Uses CID (Content-ID) attachment method — works in Gmail.

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


def send_email(subject: str, html_content: str, images: dict = None):
    """
    Sends an HTML email via Gmail SMTP.
    Images dict: {"cid_name": bytes_data} — referenced in HTML as cid:cid_name

    Requires GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT env variables.
    """
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("EMAIL_RECIPIENT")

    if not all([gmail_address, gmail_password, recipient]):
        raise ValueError("Missing email environment variables")

    # Use 'related' subtype to allow CID image references
    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From'] = f"FPL Moneyball Advisor <{gmail_address}>"
    msg['To'] = recipient

    # Attach HTML body
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)

    # Attach images with Content-ID so HTML can reference them
    if images:
        for cid, img_bytes in images.items():
            img = MIMEImage(img_bytes)
            img.add_header('Content-ID', f'<{cid}>')
            img.add_header('Content-Disposition', 'inline', filename=f'{cid}.png')
            msg.attach(img)

    print(f"📧 Sending email to {recipient}...")
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, recipient, msg.as_string())

    print("✅ Email sent successfully!")