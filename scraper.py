"""
주요 사이트 공지 모니터링 스크래퍼 - GitHub Actions 전용
실행: python scraper.py
출력: data/status.json  (GitHub Pages 대시보드에서 읽음)
"""
import json, os, logging
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "last_state.json")
DATA_DIR   = os.path.join(BASE_DIR, "data")
OUTPUT     = os.path.join(DATA_DIR, "status.json")
KST        = timezone(timedelta(hours=9))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SITES = [
    {
        "id": "notice", "name": "전기위 공지사항", "icon": "📢", "color": "#3b82f6",
        "url": "https://www.korec.go.kr/notice/selectNoticeList.do",
        "title_idx": 2, "date_idx": 3, "num_idx": 0,
    },
    {
        "id": "result", "name": "위원회 개최결과", "icon": "📋", "color": "#10b981",
        "url": "https://www.korec.go.kr/notice/result/selectNoticeList.do",
        "title_idx": 1, "date_idx": 2, "num_idx": 0,
    },
    {
        "id": "nie_notice", "name": "생태.자연도 공고", "icon": "🍃", "color": "#eab308",
        "url": "https://www.nie.re.kr/nie/bbs/BMSR00038/list.do?menuNo=200099&pageIndex=1&gubunCd=&searchCondition=&searchKeyword=",
        "title_idx": 1, "date_idx": 4, "num_idx": 0,
    },
    {
        "id": "kepco_notice", "name": "한전 설계포털 공지", "icon": "⚡", "color": "#f97316",
        "url": "https://online.kepco.co.kr/EWM040D00",
        "type": "kepco",
    },
]


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_notices(site, p_instance):
    try:
        browser = p_instance.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ko-KR",
        )
        page = context.new_page()
        page.goto(site["url"], wait_until="domcontentloaded", timeout=40000)

        if site.get("type") == "kepco":
            try: page.wait_for_selector('div[id*="notiRowGroup"]', timeout=20000)
            except: pass
        else:
            try: page.wait_for_selector("tbody tr", timeout=20000)
            except: pass

        html = page.content()
        browser.close()
    except Exception as e:
        log.error(f"[{site['name']}] 스크래핑 실패: {e}")
        return None, str(e)

    soup = BeautifulSoup(html, "html.parser")
    notices = []

    if site.get("type") == "kepco":
        rows = soup.select('div[id*="notiRowGroup"]')
        for row in rows:
            try:
                title_el = row.select_one('[id$="noticeTitle"]')
                date_el  = row.select_one('[id$="noticeRegDate"]')
                if title_el and date_el:
                    notices.append({
                        "num":   "-",
                        "title": title_el.get_text(strip=True),
                        "date":  date_el.get_text(strip=True),
                        "url":   site["url"],
                    })
            except:
                continue
    else:
        rows = soup.select("tbody tr")
        if len(rows) == 1 and "없습니다" in rows[0].get_text():
            return [], None
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < max(site.get("title_idx", 0), site.get("date_idx", 0)) + 1:
                continue
            try:
                num      = tds[site["num_idx"]].get_text(strip=True)
                title_td = tds[site["title_idx"]]
                title_a  = title_td.find("a")
                title    = title_a.get_text(strip=True) if title_a else title_td.get_text(strip=True)
                date     = tds[site["date_idx"]].get_text(strip=True)
                if title:
                    notices.append({"num": num, "title": title, "date": date, "url": site["url"]})
            except:
                continue

    log.info(f"[{site['name']}] {len(notices)}건 파싱 완료")
    return notices, None


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    state = load_state()

    results = {
        "checked_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "sites": [],
        "is_updating": False,
    }

    with sync_playwright() as p:
        for site in SITES:
            current, err = fetch_notices(site, p)
            if err or current is None:
                results["sites"].append({
                    "id": site["id"], "name": site["name"],
                    "icon": site["icon"], "color": site["color"],
                    "url": site["url"], "error": err or "스크래핑 실패",
                    "new_count": 0, "new_items": [], "total": 0,
                })
            else:
                def item_id(n): return f"{n['num']}||{n['title']}"
                prev_ids    = set(state.get(site["id"], []))
                current_ids = [item_id(n) for n in current]
                new_items   = [n for n in current if item_id(n) not in prev_ids] if prev_ids else []
                state[site["id"]] = current_ids[:30]

                results["sites"].append({
                    "id": site["id"], "name": site["name"],
                    "icon": site["icon"], "color": site["color"],
                    "url": site["url"], "error": None,
                    "new_count": len(new_items),
                    "new_items": new_items[:10],
                    "total": len(current),
                })
                log.info(f"[{site['name']}] 신규: {len(new_items)}건 / 전체: {len(current)}건")

    save_state(state)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log.info(f"✅ 저장 완료: {OUTPUT}")


if __name__ == "__main__":
    main()
