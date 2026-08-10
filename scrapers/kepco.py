import logging
import re
from bs4 import BeautifulSoup
from scrapers.retry import goto_with_retry
from config import GOTO_TIMEOUT

log = logging.getLogger(__name__)

_NOTICE_DATE_RE = re.compile(
    r"(?<!\d)(\d{4})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})(?!\d)"
)


def normalize_notice_date(text: str) -> str:
    """접근성용 숨김 문구와 무관하게 공지 등록일만 표준화한다."""
    raw = (text or "").strip()
    match = _NOTICE_DATE_RE.search(raw)
    if not match:
        return raw

    year, month, day = match.groups()
    return f"{year}.{int(month):02d}.{int(day):02d}"


def fetch_kepco(site: dict, p_instance) -> tuple:
    """한전 WebSquare 공지 전용 파서."""
    try:
        browser = p_instance.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ko-KR",
        )
        page = context.new_page()
        goto_with_retry(page, site["url"], wait_until="domcontentloaded", timeout=GOTO_TIMEOUT)
        try:
            page.wait_for_selector('div[id*="notiRowGroup"]', timeout=20000)
        except Exception:
            pass
        html = page.content()
        browser.close()
    except Exception as e:
        log.error(f"[{site['name']}] 스크래핑 실패: {e}")
        return None, str(e)

    soup    = BeautifulSoup(html, "html.parser")
    notices = []
    for row in soup.select('div[id*="notiRowGroup"]'):
        try:
            title_el = row.select_one('[id$="noticeTitle"]')
            date_el  = row.select_one('[id$="noticeRegDate"]')
            if title_el and date_el:
                notices.append({
                    "num":   "-",
                    "title": title_el.get_text(strip=True),
                    "date":  normalize_notice_date(date_el.get_text(" ", strip=True)),
                    "url":   site["url"],
                })
        except Exception:
            continue

    log.info(f"[{site['name']}] {len(notices)}건 파싱 완료")
    return notices, None
