"""
MS Teams 정기 보고 (평일 09:00 KST)
Entry Point — 비교 로직과 카드 빌딩은 logic/detector.py, presentation/teams_card.py 참조.

환경변수:
  TEAMS_WEBHOOK_URL  (필수) GitHub Secret에 등록
  DASHBOARD_URL      (선택) 대시보드 바로가기 URL
  FORCE_SEND         (선택) "true" 설정 시 --force와 동일
"""

import json, os, sys
import requests

from state                  import load_state, STATE_FILE
from logic.detector         import get_new_items
from presentation.teams_card import build_card, SITE_DISPLAY, MUTED_METMASTS

FORCE_SEND  = "--force" in sys.argv or os.environ.get("FORCE_SEND", "").lower() == "true"
WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")
STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "status.json")


def load_metmasts() -> list:
    if not os.path.exists(STATUS_FILE):
        return []
    with open(STATUS_FILE, encoding="utf-8") as f:
        return json.load(f).get("metmasts", [])


def main():
    if not WEBHOOK_URL:
        print("❌ TEAMS_WEBHOOK_URL 환경변수 미설정. GitHub Secret 확인.")
        sys.exit(1)
    if not os.path.exists(STATE_FILE):
        print("❌ last_state.json 없음. scraper.py 를 먼저 실행하세요.")
        sys.exit(1)

    state    = load_state()
    metmasts = load_metmasts()
    new_items, b_key, a_key = get_new_items(state, SITE_DISPLAY)
    offline  = [m for m in metmasts if m.get("status") != "Online" and m.get("id") not in MUTED_METMASTS]

    print(f"📊 비교 윈도우: {a_key}  →  {b_key}")
    print(f"📰 신규 게시글: {len(new_items)}건 / 📡 오프라인 계측기: {len(offline)}대")

    if not new_items and not offline:
        if FORCE_SEND:
            print("⚡ --force 모드: 신규 항목 없어도 강제 발송합니다.")
        else:
            print("✅ 신규 게시글 없음 + 모든 계측기 정상 → 알림 생략")
            return

    card = build_card(new_items, metmasts)
    resp = requests.post(WEBHOOK_URL, json=card, timeout=15)
    if resp.status_code in (200, 202):
        print("✅ Teams 알림 발송 완료")
    else:
        print(f"❌ Teams 발송 실패: HTTP {resp.status_code} / {resp.text[:200]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
