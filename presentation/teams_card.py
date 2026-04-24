import os

DASHBOARD_URL  = os.environ.get("DASHBOARD_URL", "https://jung372.github.io/BRE-Workflow-Automation2/")
MUTED_METMASTS = {"DKAM"}

SITE_DISPLAY = {
    "notice":       "전기위 공지사항",
    "result":       "위원회 개최결과",
    "eiass_wind":   "소규모 환평(풍력)",
    "kepco_notice": "한전 재분배 용량 공지",
    "nie_notice":   "생태·자연도 공고",
}


def build_card(new_items: list, metmasts: list) -> dict:
    """Teams MessageCard 딕셔너리 생성."""
    offline = [m for m in metmasts if m.get("status") != "Online" and m.get("id") not in MUTED_METMASTS]

    theme_color  = "E74C3C" if offline else "8FC31F"
    metmast_text = (
        f"⚠️ {', '.join(m['name'] for m in offline)} 운영중단"
        if offline else "✅ 모든 설비 운영중"
    )

    sections = [
        {
            "facts": [
                {"name": "📡 계측기 운영 상태", "value": metmast_text},
                {"name": "🆕 신규 게시글",       "value": f"총 {len(new_items)}건"},
            ]
        }
    ]

    if new_items:
        sections.append({
            "title": "📰 신규 게시글 목록",
            "facts": [
                {
                    "name":  f"[{item['site_name']}]",
                    "value": f"[{item['title']}]({item['url']}) ({item['date']})",
                }
                for item in new_items
            ],
        })

    sections.append({
        "facts": [{"name": "", "value": f"[📊 전체 현황 보기]({DASHBOARD_URL})"}]
    })

    return {
        "@type":       "MessageCard",
        "@context":    "https://schema.org/extensions",
        "themeColor":  theme_color,
        "summary":     f"전일 대비 신규 게시글 {len(new_items)}건",
        "title":       "🔔 [정기 보고] 전일 대비 신규 게시글 현황",
        "sections":    sections,
        "potentialAction": [
            {
                "@type":   "OpenUri",
                "name":    "📊 전체 현황 보기",
                "targets": [{"os": "default", "uri": DASHBOARD_URL}],
            }
        ],
    }
