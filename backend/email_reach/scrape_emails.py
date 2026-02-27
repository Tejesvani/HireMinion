import json
import os
import re
import sys
import signal
import time
import asyncio
from urllib.parse import unquote, quote_plus

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


# Handle Ctrl+C gracefully
def signal_handler(sig, frame):
    print("\n\n⛔ Interrupted by user. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ============ CONFIGURATION ============
DEBUG_PORT = "127.0.0.1:9222"
WAIT_SECONDS = 5
# =======================================

# Paths
BASE_DIR = os.getcwd()
DOWNLOADED_DIR = os.path.join(BASE_DIR, "downloaded")
LINKEDIN_FILE = os.path.join(DOWNLOADED_DIR, "linkedin_emails.json")
EMAIL_CONTENT_FILE = os.path.join(DOWNLOADED_DIR, "email_content.json")
EMAIL_TEXT_FILE = os.path.join(DOWNLOADED_DIR, "tailored_email.txt")


# ==================== PREPARE ====================

def ensure_downloaded_dir():
    if not os.path.exists(DOWNLOADED_DIR):
        os.makedirs(DOWNLOADED_DIR)


def clear_files():
    with open(LINKEDIN_FILE, "w") as f:
        json.dump([], f, indent=2)
    with open(EMAIL_CONTENT_FILE, "w") as f:
        json.dump({}, f, indent=2)
    print("🧹 Cleared JSON files")


def is_valid_linkedin_url(text: str) -> bool:
    text = text.strip()
    pattern = r"https?://(www\.)?linkedin\.com/in/[\w\-]+"
    return bool(re.match(pattern, text))


def clean_linkedin_url(url: str) -> str:
    url = url.strip()
    url = unquote(url)
    url = url.split("?")[0].split("#")[0]
    url = url.replace("://linkedin.com", "://www.linkedin.com")
    url = url.replace("http://", "https://")
    if not url.endswith("/"):
        url += "/"
    return url


def load_email_content() -> dict:
    email_content = {}
    if not os.path.exists(EMAIL_TEXT_FILE):
        print(f"⚠️ {EMAIL_TEXT_FILE} not found")
        return email_content
    try:
        with open(EMAIL_TEXT_FILE, "r", encoding="utf-8") as f:
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


async def get_clipboard_history() -> list[str]:
    try:
        from winsdk.windows.applicationmodel.datatransfer import Clipboard
        result = await Clipboard.get_history_items_async()
        texts = []
        for item in result.items:
            try:
                content = item.content
                if content.contains("Text"):
                    text = await content.get_text_async()
                    if text:
                        texts.append(text)
            except Exception:
                continue
        return texts
    except Exception as e:
        print(f"❌ Failed to access clipboard history: {e}")
        return []


async def prepare():
    print("\n📋 Step 1 — Preparing data...\n")

    ensure_downloaded_dir()
    clear_files()

    # Clipboard
    clipboard_items = await get_clipboard_history()
    if not clipboard_items:
        print("⚠️ No clipboard items found.")
        return False

    # LinkedIn links
    linkedin_links = []
    seen_urls = set()

    for item in clipboard_items:
        if is_valid_linkedin_url(item):
            if "moheesh" in item.lower():
                continue
            clean_url = clean_linkedin_url(item)
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                linkedin_links.append({
                    "linkedin_url": clean_url,
                    "email": "",
                    "name": "",
                    "job_title": "",
                    "company": ""
                })

    # Email content
    email_content = load_email_content()

    # Save
    with open(LINKEDIN_FILE, "w") as f:
        json.dump(linkedin_links, f, indent=2)
    with open(EMAIL_CONTENT_FILE, "w") as f:
        json.dump(email_content, f, indent=2)

    print(f"✅ LinkedIn links: {len(linkedin_links)}")
    print(f"{'✅' if email_content else '⚠️'} Email content: {'Found' if email_content else 'Not found'}")

    return len(linkedin_links) > 0


# ==================== SCRAPE ====================

class EmailFinder:
    def __init__(self):
        self.driver = None
        self.data = []

    def load_data(self) -> bool:
        try:
            with open(LINKEDIN_FILE, "r") as f:
                self.data = json.load(f)
            return True
        except Exception:
            print("❌ Failed to load linkedin_emails.json")
            return False

    def save_data(self):
        with open(LINKEDIN_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def connect_to_chrome(self) -> bool:
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", DEBUG_PORT)
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            return True
        except Exception:
            print("❌ Failed to connect. Make sure Chrome is running with --remote-debugging-port=9222")
            return False

    def fetch_email(self, linkedin_url: str) -> dict:
        result = {"email": "", "name": "", "job_title": "", "company": ""}

        if not linkedin_url.endswith("/"):
            linkedin_url += "/"
        linkedin_url = linkedin_url.replace("://linkedin.com", "://www.linkedin.com")

        encoded_url = quote_plus(linkedin_url)
        api_url = f"https://jobright.ai/swan/email/external-linkedin-to-email?url={encoded_url}"

        try:
            self.driver.get(api_url)
            time.sleep(WAIT_SECONDS)

            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            response = json.loads(body_text)

            if response.get("success") and response.get("result"):
                emails = response["result"].get("emails", [])
                user_info = response["result"].get("userInfo", {})

                if emails:
                    result["email"] = emails[0]
                    result["name"] = user_info.get("name", "")
                    result["job_title"] = user_info.get("jobTitle", "")
                    result["company"] = user_info.get("companyName", "")
        except Exception:
            pass

        return result

    def scrape(self):
        print("\n📧 Step 2 — Scraping emails...\n")

        if not self.load_data() or not self.data:
            print("⚠️ No data to process.")
            return

        if not self.connect_to_chrome():
            return

        to_process = [i for i, entry in enumerate(self.data) if not entry.get("email")]
        total = len(to_process)

        if total == 0:
            print("✅ All entries already processed.")
            return

        print(f"🔍 Processing {total} entries...\n")

        found = 0
        not_found = 0

        for count, idx in enumerate(to_process, 1):
            entry = self.data[idx]
            result = self.fetch_email(entry["linkedin_url"])

            entry["email"] = result["email"]
            entry["name"] = result["name"]
            entry["job_title"] = result["job_title"]
            entry["company"] = result["company"]

            if result["email"]:
                found += 1
                print(f"  [{count}/{total}] ✅ {result['name']} — {result['email']}")
            else:
                not_found += 1
                print(f"  [{count}/{total}] ❌ {entry['linkedin_url']}")

            self.save_data()

        print(f"\n📊 Done! Found: {found} | Not found: {not_found} | Total: {total}")


# ==================== ENTRY ====================

async def run():
    has_links = await prepare()
    if has_links:
        finder = EmailFinder()
        finder.scrape()


if __name__ == "__main__":
    asyncio.run(run())