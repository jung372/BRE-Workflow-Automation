import json, logging, os
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

from config  import SITES, METMASTS
from state   import load_state, save_state, get_baseline_ids, update_site_state, item_id
from scrapers          import fetch_site
from scrapers.metmast  import check_metmast

KST      = timezone(timedelta(hours=9))
_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_ROOT, "data")
OUTPUT   = os.path.join(DATA_DIR, "status.json")

log = logging.getLogger(__name__)


def run() -> dict:
    """전체 스크래핑 실행 → state 갱신 → status.json 저장 → 결과 dict 반환."""
    os.makedirs(DATA_DIR, exist_ok=True)
    state = load_state()

    results = {
        "checked_at":  datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "sites":       [],
        "metmasts":    [],
        "is_updating": False,
    }

    with sync_playwright() as p:
        for m in METMASTS:
            log.info(f"[MetMast] {m['name']} 상태 확인 중...")
            status = check_metmast(m, p)
            results["metmasts"].append(status)
            log.info(f" → {status['status']}")

        for site in SITES:
            log.info(f"[{site['name']}] 수집 시작")
            current, err = fetch_site(site, p)

            if err or current is None:
                results["sites"].append({
                    "id": site["id"], "name": site["name"],
                    "icon": site["icon"], "color": site["color"],
                    "url": site["url"], "error": err or "데이터 수집 실패",
                    "new_count": 0, "new_items": [], "total": 0,
                })
                continue

            site_state   = state.get(site["id"], {})
            baseline_ids = get_baseline_ids(site_state)
            current_ids  = [item_id(n) for n in current]
            new_items    = [n for n in current if item_id(n) not in baseline_ids] if baseline_ids else []

            state[site["id"]] = update_site_state(site_state, current_ids, current)
            results["sites"].append({
                "id": site["id"], "name": site["name"],
                "icon": site["icon"], "color": site["color"],
                "url": site["url"], "error": None,
                "new_count": len(new_items),
                "new_items": new_items[:10],
                "total":     len(current),
            })
            log.info(f"[{site['name']}] 신규 {len(new_items)}건 / 전체 {len(current)}건")

    save_state(state)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info(f"✅ 저장 완료: {OUTPUT}")

    return results
