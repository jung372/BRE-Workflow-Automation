import os
from urllib.parse import urlparse

# page.goto 등 네비게이션 타임아웃(ms). 프록시 지연이 크면 GOTO_TIMEOUT_MS 로 상향.
GOTO_TIMEOUT = int(os.environ.get("GOTO_TIMEOUT_MS", "40000"))


def playwright_proxy():
    """HTTP_PROXY_KR 환경변수가 있으면 Playwright launch/new_context 용 proxy dict, 없으면 None."""
    raw = os.environ.get("HTTP_PROXY_KR", "").strip()
    if not raw:
        return None
    u = urlparse(raw)
    server = f"{u.scheme}://{u.hostname}" + (f":{u.port}" if u.port else "")
    proxy = {"server": server}
    if u.username:
        proxy["username"] = u.username
    if u.password:
        proxy["password"] = u.password
    return proxy


def requests_proxies():
    """HTTP_PROXY_KR 환경변수가 있으면 requests 용 proxies dict, 없으면 None."""
    raw = os.environ.get("HTTP_PROXY_KR", "").strip()
    return {"http": raw, "https": raw} if raw else None


# "proxy": True 인 사이트만 한국 리전 프록시(HTTP_PROXY_KR)를 경유한다.
# 해외 IP를 지오-차단하는 정부/공공 도메인(.go.kr / .re.kr)에만 적용하고,
# 이미 정상 동작하는 한전(.co.kr)·MetMast(해외)는 프록시를 태우지 않는다.
SITES = [
    {
        "id": "notice", "name": "전기위 공지사항", "icon": "📢", "color": "#3b82f6",
        "url": "https://www.korec.go.kr/notice/selectNoticeList.do",
        "title_idx": 2, "date_idx": 3, "num_idx": 0, "proxy": True,
    },
    {
        "id": "result", "name": "위원회 개최결과", "icon": "📋", "color": "#10b981",
        "url": "https://www.korec.go.kr/notice/result/selectNoticeList.do",
        "title_idx": 1, "date_idx": 2, "num_idx": 0, "proxy": True,
    },
    {
        "id": "eiass_wind", "name": "소규모 환평(풍력)", "icon": "🌬️", "color": "#0ea5e9",
        "url": "https://www.eiass.go.kr/biz/base/info/perList.do?menu=biz&biz_gubn=M",
        "type": "eiass", "proxy": True,
    },
    {
        "id": "kepco_notice", "name": "한전 재분배 용량 공지", "icon": "⚡", "color": "#f97316",
        "url": "https://online.kepco.co.kr/EWM040D00",
        "type": "kepco",
    },
    {
        "id": "nie_notice", "name": "생태·자연도 공고", "icon": "🍃", "color": "#eab308",
        "url": "https://www.nie.re.kr/nie/bbs/BMSR00038/list.do?menuNo=200099&pageIndex=1&gubunCd=&searchCondition=&searchKeyword=",
        "title_idx": 1, "date_idx": 4, "num_idx": 0, "proxy": True,
    },
]

METMASTS = [
    {"id": "SIRU", "name": "SIRU", "env_prefix": "METMAST_SIRU", "url": os.environ.get("METMAST_SIRU_URL", "https://D225107.connect.ammonit.com/")},
    {"id": "GOGK", "name": "GOGK", "env_prefix": "METMAST_GOGK", "url": os.environ.get("METMAST_GOGK_URL", "https://D243097.connect.ammonit.com/")},
    {"id": "BLMU", "name": "BLMU", "env_prefix": "METMAST_BLMU", "url": os.environ.get("METMAST_BLMU_URL", "")},
    {"id": "DKAM", "name": "DKAM", "env_prefix": "METMAST_DKAM", "url": os.environ.get("METMAST_DKAM_URL", "https://d244024.connect.ammonit.com/")},
]
