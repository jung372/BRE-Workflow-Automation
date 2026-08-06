import json, os, re
from datetime import datetime, timezone, timedelta

from runtime_config import get_state_file

KST           = timezone(timedelta(hours=9))
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
STATE_FILE    = str(get_state_file())
BASELINE_DAYS = 5
KEEP_DAYS     = 11


def item_id(n: dict) -> str:
    # 소스가 진짜 고유키를 주면(open.go.kr 의 PRDCTN_INSTT_REGIST_NO) 그것을 쓴다.
    # uid 가 없는 기존 소스는 종전 로직을 그대로 타므로 하위 호환된다.
    uid = n.get("uid")
    if uid:
        return str(uid)

    comp   = n.get("comp_date", "")
    status = n.get("status", "")
    title  = re.sub(r"NEW$", "", n["title"]).strip()
    return f"{title}||{n['date']}||{comp}||{status}"


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_baseline_ids(site_state: dict) -> set:
    """5일 전 스냅샷 기준 ID set 반환. 없으면 빈 set(첫 실행 처리)."""
    if isinstance(site_state, list):
        return set()
    daily = site_state.get("daily_snapshots", {})
    if not daily:
        return set()

    today      = datetime.now(KST).date()
    target_str = (today - timedelta(days=BASELINE_DAYS)).strftime("%Y-%m-%d")
    baseline   = None
    for d in sorted(daily.keys()):
        if d <= target_str:
            baseline = d

    if baseline is None:
        return set()
    return set(daily[baseline])


def _snapshot_entry(item: dict) -> dict:
    """시간별 스냅샷 항목. Teams 보고가 이 값을 읽는다.

    dept/keyword 는 값이 있을 때만 넣는다. 기존 5개 사이트에 빈 문자열을
    추가하면 6MB 짜리 last_state.json 이 이유 없이 커지기 때문이다.
    """
    entry = {
        "id":    item_id(item),
        "title": item.get("title", ""),
        "date":  item.get("date", ""),
        "url":   item.get("url", ""),
    }
    for key in ("dept", "keyword"):
        value = item.get(key)
        if value:
            entry[key] = value
    return entry


def update_site_state(site_state: dict, current_ids: list, current_items: list) -> dict:
    """오늘 날짜 스냅샷 저장 + KEEP_DAYS 초과분 정리."""
    if isinstance(site_state, list):
        site_state = {}

    now        = datetime.now(KST)
    today_str  = now.strftime("%Y-%m-%d")
    hour_str   = now.strftime("%Y-%m-%d %H")
    cutoff_str = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    cutoff_hr  = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d %H")

    daily = site_state.get("daily_snapshots", {})
    daily[today_str] = current_ids[:100]
    site_state["daily_snapshots"] = {k: v for k, v in daily.items() if k >= cutoff_str}

    hourly = site_state.get("hourly_snapshots", {})
    hourly[hour_str] = [_snapshot_entry(item) for item in (current_items or [])[:100]]
    site_state["hourly_snapshots"] = {k: v for k, v in hourly.items() if k >= cutoff_hr}

    return site_state
