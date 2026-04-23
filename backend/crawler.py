import requests
from bs4 import BeautifulSoup
from datetime import datetime
from database import data_collection
import io
import PyPDF2
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import urllib3
from urllib.parse import urljoin, urlparse
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================== CONFIG ==================
MAX_TIME_PER_SOURCE = 60
MAX_PAGES_PER_SOURCE = 30
MAX_DEPTH = 3
REQUEST_TIMEOUT = 10

IGNORED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".css", ".js",
    ".zip", ".rar", ".exe", ".mp4", ".mp3"
)

# ================== SESSION ==================
session = requests.Session()

HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
]

# ================== UTILS ==================
def extract_text_from_pdf(content, max_pages=3):
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            text += page.extract_text() or ""
        return text
    except:
        return ""

def safe_request(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            headers = random.choice(HEADERS_POOL)
            r = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers=headers,
                verify=False,
                allow_redirects=True
            )

            if r.text and ("cloudflare" in r.text.lower() or "captcha" in r.text.lower()):
                print(f"[BLOCKED BY CLOUDFLARE] {url}")
                return None
            if r.status_code == 429 or r.status_code == 403:
                time.sleep(random.uniform(2,5))
                continue

            return r

        except requests.exceptions.RequestException:
            time.sleep(random.uniform(1,3))

    return None

# ================== CRAWL PAGE ==================
def crawl_single_page(url, source):
    try:
        r = safe_request(url)
        if r is None or r.status_code == 404:
            print(f"[SKIP] {url} inaccessible ou 404")
            return False, ""

        content_type = r.headers.get("Content-Type", "").lower()
        text = ""

        if "pdf" in content_type:
            text = extract_text_from_pdf(r.content)
        elif "html" in content_type:
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(" ", strip=True)
        elif "xml" in content_type or "rss" in content_type:
            soup = BeautifulSoup(r.content, "xml")
            text = soup.get_text(" ", strip=True)
        else:
            text = r.text

        text = text[:5000]

        # ------------------ DETECTION MOTS-CLÉS ------------------
        keywords_found = []
        for kw in source.get("keywords", []):
            if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
                keywords_found.append(kw)

        if not keywords_found:
            print(f"[SKIP] Aucun mot-clé trouvé sur {url}")
            return False, ""  # ne pas enregistrer si aucun mot-clé

        # ------------------ ENREGISTREMENT MONGODB ------------------
        data_collection.insert_one({
            "url": url,
            "source": source["url"],
            "content_type": content_type,
            "content": text,
            "keywords_found": keywords_found,
            "crawled_at": datetime.now()
        })

        print(f"[OK] {url} → mots-clés trouvés: {keywords_found}")
        return True, r.text if "html" in content_type else ""

    except Exception as e:
        print(f"[FAIL] {url} : {e}")
        return False, ""

# ================== CRAWL SOURCE ==================
def crawl_source_smart(source):
    start_url = source["url"]
    visited = set()
    queue = [(start_url, 0)]
    start_time = time.time()
    start_domain = urlparse(start_url).netloc

    while queue:
        if time.time() - start_time > MAX_TIME_PER_SOURCE:
            print(f"[TIMEOUT SOURCE] {start_url}")
            break

        url, depth = queue.pop(0)

        if url in visited or depth > MAX_DEPTH or len(visited) >= MAX_PAGES_PER_SOURCE:
            continue
        if url.lower().endswith(IGNORED_EXTENSIONS):
            continue

        visited.add(url)
        ok, html = crawl_single_page(url, source)

        # 🔹 Propager les liens seulement si un mot-clé a été trouvé
        if ok and html:
            try:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.find_all("a", href=True):
                    link = urljoin(url, a["href"]).split("#")[0]
                    if not link.startswith("http"):
                        continue
                    if urlparse(link).netloc != start_domain:
                        continue
                    if link not in visited:
                        queue.append((link, depth + 1))
            except:
                pass

        time.sleep(random.uniform(1.5, 4))

    print(f"[DONE] {start_url} → {len(visited)} pages visitées")
