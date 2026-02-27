import json
import os
import re
import sys
import signal
import base64
import mimetypes
import random
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Handle Ctrl+C gracefully
def signal_handler(sig, frame):
    print("\n\n⛔ Interrupted by user. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ============ CONFIGURATION ============
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
SIGNATURE = "\n\nBest regards,\n\nMoheesh Kavitha Arumugam\n+1-857-707-6684\nmoheeshmsh@gmail.com"
# =======================================

# Paths
BASE_DIR = os.getcwd()
DOWNLOADED_DIR = os.path.join(BASE_DIR, "downloaded")
LINKEDIN_FILE = os.path.join(DOWNLOADED_DIR, "linkedin_emails.json")
EMAIL_CONTENT_FILE = os.path.join(DOWNLOADED_DIR, "email_content.json")
OPTIONAL_EMAILS_FILE = os.path.join(DOWNLOADED_DIR, "optional_emails.txt")
TAILORED_EMAIL_FILE = os.path.join(DOWNLOADED_DIR, "tailored_email.txt")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")


def select_pdf() -> str:
    print("📎 Select a PDF file to attach...")
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        file_path = filedialog.askopenfilename(
            parent=root,
            title="Select PDF to attach",
            filetypes=[("PDF files", "*.pdf")]
        )
        root.destroy()
        if not file_path:
            print("❌ No file selected.")
            return ""
        print(f"✅ Selected: {file_path}")
        return file_path
    except Exception as e:
        print(f"❌ File picker failed: {e}")
        # Fallback to manual input
        file_path = input("Enter the full path to your PDF: ").strip().strip('"')
        if os.path.exists(file_path) and file_path.lower().endswith(".pdf"):
            print(f"✅ Selected: {file_path}")
            return file_path
        print("❌ Invalid file path.")
        return ""


def load_email_content() -> dict:
    email_content = {}
    if not os.path.exists(TAILORED_EMAIL_FILE):
        print(f"⚠️ {TAILORED_EMAIL_FILE} not found")
        return email_content
    try:
        with open(TAILORED_EMAIL_FILE, "r", encoding="utf-8") as f:
            text = f.read().strip()
        subject_match = re.search(r"Subject:\s*(.+?)(?:\n|Body:)", text, re.DOTALL)
        body_match = re.search(r"Body:\s*(.+)", text, re.DOTALL)
        if subject_match and body_match:
            email_content = {
                "subject": subject_match.group(1).strip(),
                "body": body_match.group(1).strip()
            }
    except Exception as e:
        print(f"❌ Failed to read email text: {e}")
    return email_content


def load_optional_emails() -> list[dict]:
    if not os.path.exists(OPTIONAL_EMAILS_FILE):
        return []

    contacts = []
    seen = set()

    with open(OPTIONAL_EMAILS_FILE, "r") as f:
        for line in f:
            email = line.strip()
            if email and "@" in email and email not in seen:
                seen.add(email)
                contacts.append({
                    "email": email,
                    "name": "",
                    "linkedin_url": "",
                    "job_title": "",
                    "company": ""
                })

    if contacts:
        print(f"📄 Loaded {len(contacts)} optional emails")

    return contacts


def clear_files():
    with open(LINKEDIN_FILE, "w") as f:
        json.dump([], f, indent=2)

    with open(EMAIL_CONTENT_FILE, "w") as f:
        json.dump({}, f, indent=2)

    if os.path.exists(OPTIONAL_EMAILS_FILE):
        with open(OPTIONAL_EMAILS_FILE, "w") as f:
            f.write("")

    if os.path.exists(TAILORED_EMAIL_FILE):
        with open(TAILORED_EMAIL_FILE, "w") as f:
            f.write("")

    print("🧹 Cleared all data files")


def get_gmail_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"❌ {CREDENTIALS_FILE} not found.")
                print("   Download it from Google Cloud Console → APIs & Services → Credentials")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_message(to: str, subject: str, body: str, attachment_path: str) -> dict:
    message = MIMEMultipart()
    message["to"] = to
    message["subject"] = subject

    # Convert newlines to HTML paragraphs
    paragraphs = body.split("\n\n")
    html_body = ""
    for p in paragraphs:
        p = p.replace("\n", "<br>")
        html_body += f"<p style='margin:0 0 12px 0;font-family:Arial,sans-serif;font-size:14px;color:#333;'>{p}</p>"

    message.attach(MIMEText(html_body, "html"))

    content_type, _ = mimetypes.guess_type(attachment_path)
    main_type, sub_type = content_type.split("/", 1)

    with open(attachment_path, "rb") as f:
        attachment = MIMEBase(main_type, sub_type)
        attachment.set_payload(f.read())

    encoders.encode_base64(attachment)
    filename = os.path.basename(attachment_path)
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    message.attach(attachment)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


def run():
    print("\n📨 Email Sender — Starting...\n")

    # Step 1: Select PDF
    pdf_path = select_pdf()
    if not pdf_path:
        return

    # Step 2: Load email content from tailored_email.txt
    email_content = load_email_content()

    subject = email_content.get("subject", "")
    body = email_content.get("body", "")

    if not subject or not body:
        print("❌ Email subject or body is empty. Check tailored_email.txt")
        return

    # Step 3: Load contacts from linkedin_emails.json
    contacts = []
    if os.path.exists(LINKEDIN_FILE):
        try:
            with open(LINKEDIN_FILE, "r") as f:
                contacts = json.load(f)
        except Exception:
            pass

    # Filter contacts with valid emails
    to_send = [c for c in contacts if c.get("email")]

    # Add optional emails
    optional = load_optional_emails()
    existing_emails = {c["email"] for c in to_send}
    for contact in optional:
        if contact["email"] not in existing_emails:
            to_send.append(contact)

    if not to_send:
        print("⚠️ No contacts with valid emails found.")
        return

    print(f"📧 Sending to {len(to_send)} contacts...")

    # Step 4: Connect to Gmail
    service = get_gmail_service()
    if not service:
        return

    print("✅ Connected to Gmail\n")

    # Step 5: Send emails
    sent = 0
    failed = 0

    for i, contact in enumerate(to_send, 1):
        email = contact["email"]
        name = contact.get("name", "").strip()

        try:
            greeting = f"Hi {name},\n\n" if name else "Hi Hiring Team,\n\n"
            full_body = greeting + body + SIGNATURE

            message = create_message(email, subject, full_body, pdf_path)
            service.users().messages().send(userId="me", body=message).execute()
            sent += 1
            print(f"  [{i}/{len(to_send)}] ✅ Sent to {name or 'Hiring Team'} — {email}")

            # Random delay between 2-5 seconds
            if i < len(to_send):
                delay = random.uniform(2, 5)
                print(f"  ⏳ Waiting {delay:.1f}s...")
                time.sleep(delay)

        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(to_send)}] ❌ Failed: {email} — {e}")

    # Step 6: Clear files after successful send
    if sent > 0:
        clear_files()

    print(f"\n📊 Done! Sent: {sent} | Failed: {failed} | Total: {len(to_send)}\n")


if __name__ == "__main__":
    run()