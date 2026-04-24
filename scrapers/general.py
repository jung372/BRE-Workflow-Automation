import logging
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


def fetch_general(site: dict, p_instance) -> tuple:
    """Playwright 기반 일반 테이블 파서 (KOREC, NIE 등 공통)."""
    try:
        browser = p_instance.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ko-KR",
        )
        page = context.new_page()
        page.goto(site["url"], wait_until="domcontentloaded", timeout=40000)
        try:
            page.wait_for_selector("tbody tr", timeout=20000)
        except Exception:
            pass
        html = page.content()
        browser.close()
    except Exception as e:
        log.error(f"[{site['name']}] 스크래핑 실패: {e}")
        return None, str(e)

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tbody tr")
    if len(rows) == 1 and "없습니다" in rows[0].get_text():
        return [], None

    notices = []
    for row in rows:
        tds = row.find_all(["td", "th"])
        if len(tds) < max(site.get("title_idx", 0), site.get("date_idx", 0)) + 1:
            continue
        try:
            num_td   = tds[site["num_idx"]]
            title_td = tds[site["title_idx"]]
            title_a  = title_td.find("a")
            title    = title_a.get_text(strip=True) if title_a else title_td.get_text(strip=True)
            num      = num_td.get_text(strip=True)
            if not num and num_td.find("img"):
                num = (num_td.find("img").get("alt") or "").strip()
            date = tds[site["date_idx"]].get_text(strip=True)
            if title:
                notices.append({"num": num, "title": title, "date": date, "url": site["url"]})
        except Exception:
            continue

    log.info(f"[{site['name']}] {len(notices)}건 파싱 완료")
    return notices, None
