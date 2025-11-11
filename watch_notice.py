import os
import requests
import hashlib
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load secrets
load_dotenv()

URL = os.getenv("WATCH_URL")
HASH_FILE = "last_hash.txt"
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT = os.getenv("TG_CHAT_ID")

def fetch_text():
    """Fetch notice page text with safe headers and retry logic."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    try:
        # First try normally
        r = requests.get(URL, headers=headers, timeout=30)
        if r.status_code == 403:
            # Try again with a fake referrer to bypass filter
            headers["Referer"] = "https://www.google.com/"
            r = requests.get(URL, headers=headers, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(separator="\n").strip()
    except Exception as e:
        print("⚠️ Error fetching page:", e)
        return ""

def compute_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def read_last():
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r") as f:
            return f.read().strip()
    return ""

def write_last(h):
    with open(HASH_FILE, "w") as f:
        f.write(h)

def send_telegram(msg):
    if not TG_TOKEN or not TG_CHAT:
        print("⚠️ Missing Telegram config.")
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TG_CHAT, "text": msg}, timeout=10)
        print("✅ Telegram message sent.")
    except Exception as e:
        print("⚠️ Telegram send failed:", e)

def main():
    print("🔍 Checking for updates...")
    text = fetch_text()
    if not text:
        print("⚠️ No content fetched. Exiting.")
        return

    new_hash = compute_hash(text)
    old_hash = read_last()

    if new_hash != old_hash:
        snippet = text[:500].replace("\n", " ").strip()
        message = f"📢 Notice page updated:\n{URL}\n\n{snippet}"
        send_telegram(message)
        write_last(new_hash)
        print("✅ Change detected and notified.")
    else:
        print("ℹ️ No change detected.")

if __name__ == "__main__":
    main()
