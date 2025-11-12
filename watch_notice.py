import os
import requests
import hashlib
import time
import random
import logging
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load secrets
load_dotenv()

# Configuration
URL = os.getenv("WATCH_URL")
HASH_FILE = "last_hash.txt"
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT = os.getenv("TG_CHAT_ID")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
)

# Rotating user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
]

REFERERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://www.facebook.com/",
    "https://t.co/"
]

def create_session():
    """Create a requests session with retry strategy and proper headers"""
    session = requests.Session()
    
    # Retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def get_stealth_headers():
    """Generate realistic browser headers"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
        "Referer": random.choice(REFERERS)
    }

def human_delay():
    """Random delay to appear human"""
    delay = random.uniform(2, 8)
    logging.info(f"Waiting {delay:.1f}s before request...")
    time.sleep(delay)

def fetch_text_requests():
    """Fetch using requests with advanced anti-blocking"""
    session = create_session()
    headers = get_stealth_headers()
    
    try:
        human_delay()
        
        # First, visit a search engine to establish "browsing history"
        try:
            session.get("https://www.google.com", timeout=5, headers=headers)
            time.sleep(1)
        except:
            pass  # Ignore if this fails
        
        # Now try the target URL
        response = session.get(URL, headers=headers, timeout=30)
        
        # Check for blocking patterns
        if response.status_code == 403:
            logging.warning("Received 403 Forbidden")
            return None
        if "cloudflare" in response.headers.get('server', '').lower():
            logging.warning("Cloudflare protection detected")
            return None
        if any(blocked in response.text.lower() for blocked in ['access denied', 'bot detected', 'captcha']):
            logging.warning("Bot detection triggered")
            return None
            
        response.raise_for_status()
        
        # Parse and clean content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
            
        # Get clean text
        text = soup.get_text(separator='\n', strip=True)
        
        # Remove extra whitespace and normalize
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        clean_text = '\n'.join(lines)
        
        logging.info(f"Successfully fetched {len(clean_text)} characters via requests")
        return clean_text
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Requests method failed: {e}")
        return None

def fetch_text_selenium_fallback():
    """Fallback method using Selenium (if installed)"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        logging.info("Attempting Selenium fallback...")
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        
        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        try:
            driver.get(URL)
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get page source and parse
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Clean content
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
                
            text = soup.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            clean_text = '\n'.join(lines)
            
            logging.info(f"Successfully fetched {len(clean_text)} characters via Selenium")
            return clean_text
            
        finally:
            driver.quit()
            
    except ImportError:
        logging.error("Selenium not installed. Install with: pip install selenium")
        return None
    except Exception as e:
        logging.error(f"Selenium method failed: {e}")
        return None

def fetch_text():
    """Main fetch function with fallback strategies"""
    # Try requests method first
    content = fetch_text_requests()
    
    # If requests fail, try Selenium
    if not content:
        logging.warning("Requests method failed, trying Selenium...")
        content = fetch_text_selenium_fallback()
    
    return content

def compute_hash(text):
    """Compute SHA256 hash of text"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def read_last_hash():
    """Read last known hash from file"""
    try:
        if os.path.exists(HASH_FILE):
            with open(HASH_FILE, 'r') as f:
                return f.read().strip()
    except Exception as e:
        logging.error(f"Error reading hash file: {e}")
    return ""

def write_last_hash(hash_value):
    """Write hash to file"""
    try:
        with open(HASH_FILE, 'w') as f:
            f.write(hash_value)
    except Exception as e:
        logging.error(f"Error writing hash file: {e}")

def send_telegram(message):
    """Send notification via Telegram"""
    if not TG_TOKEN or not TG_CHAT:
        logging.warning("Telegram credentials not configured")
        return False
        
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {
            'chat_id': TG_CHAT,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        
        logging.info("Telegram notification sent successfully")
        return True
        
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")
        return False

def extract_meaningful_snippet(text, max_length=400):
    """Extract a meaningful snippet from the text"""
    # Find the first substantial paragraph
    paragraphs = [p for p in text.split('\n') if len(p.strip()) > 50]
    
    if paragraphs:
        snippet = paragraphs[0]
    else:
        snippet = text
    
    # Trim to max length
    if len(snippet) > max_length:
        snippet = snippet[:max_length] + "..."
    
    return snippet

def main():
    """Main monitoring function"""
    logging.info("🔍 Starting website monitoring check...")
    
    # Fetch content
    content = fetch_text()
    
    if not content:
        logging.error("❌ All fetch methods failed. Website might be blocking aggressively.")
        send_telegram("🚨 <b>Monitor Alert:</b> Unable to fetch website content. Check if blocking occurred.")
        return
    
    if len(content) < 100:
        logging.warning("⚠️ Content suspiciously short, possible blocking")
        return
    
    # Compute and compare hash
    new_hash = compute_hash(content)
    old_hash = read_last_hash()
    
    logging.info(f"Content hash: {new_hash[:16]}... (old: {old_hash[:16]}...)")
    
    if new_hash == old_hash:
        logging.info("✅ No changes detected")
        return
    
    # Change detected!
    logging.info("🎯 Change detected! Sending notification...")
    
    snippet = extract_meaningful_snippet(content)
    message = f"""
📢 <b>Website Update Detected!</b>

🔗 <b>URL:</b> {URL}

📝 <b>Latest Content:</b>
{snippet}

⏰ <i>Update detected at {time.strftime('%Y-%m-%d %H:%M:%S')}</i>
"""
    
    if send_telegram(message):
        write_last_hash(new_hash)
        logging.info("✅ Change notified and hash updated")
    else:
        logging.error("❌ Failed to send notification, hash not updated")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Monitoring interrupted by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        send_telegram(f"🚨 <b>Monitor Crash:</b> {str(e)}")
