import os

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
        "id": "eiass_wind", "name": "소규모 환평(풍력)", "icon": "🌬️", "color": "#0ea5e9",
        "url": "https://www.eiass.go.kr/biz/base/info/perList.do?menu=biz&biz_gubn=M",
        "type": "eiass",
    },
    {
        "id": "kepco_notice", "name": "한전 재분배 용량 공지", "icon": "⚡", "color": "#f97316",
        "url": "https://online.kepco.co.kr/EWM040D00",
        "type": "kepco",
    },
    {
        "id": "nie_notice", "name": "생태·자연도 공고", "icon": "🍃", "color": "#eab308",
        "url": "https://www.nie.re.kr/nie/bbs/BMSR00038/list.do?menuNo=200099&pageIndex=1&gubunCd=&searchCondition=&searchKeyword=",
        "title_idx": 1, "date_idx": 4, "num_idx": 0,
    },
]

METMASTS = [
    {"id": "SIRU", "name": "SIRU", "env_prefix": "METMAST_SIRU", "url": os.environ.get("METMAST_SIRU_URL", "https://D225107.connect.ammonit.com/")},
    {"id": "GOGK", "name": "GOGK", "env_prefix": "METMAST_GOGK", "url": os.environ.get("METMAST_GOGK_URL", "https://D243097.connect.ammonit.com/")},
    {"id": "BLMU", "name": "BLMU", "env_prefix": "METMAST_BLMU", "url": os.environ.get("METMAST_BLMU_URL", "")},
    {"id": "DKAM", "name": "DKAM", "env_prefix": "METMAST_DKAM", "url": os.environ.get("METMAST_DKAM_URL", "")},
]
