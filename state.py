import json, os, re
from datetime import datetime, timezone, timedelta

KST           = timezone(timedelta(hours=9))
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
STATE_FILE    = os.path.join(BASE_DIR, "last_state.json")
BASELINE_DAYS = 5
KEEP_DAYS     = 11


def item_id(n: dict) -> str:
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
    hourly[hour_str] = [
        {
            "id":    item_id(item),
            "title": item.get("title", ""),
            "date":  item.get("date", ""),
            "url":   item.get("url", ""),
        }
        for item in (current_items or [])[:100]
    ]
    site_state["hourly_snapshots"] = {k: v for k, v in hourly.items() if k >= cutoff_hr}

    return site_state
