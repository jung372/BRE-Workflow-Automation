"""정보공개포털(open.go.kr) 정보목록 검색.

검색 결과는 정적 HTML 이 아니다. uniSrhMoreList.do 는 껍데기이고 실제 데이터는
infoList.ajax 가 JSON 으로 반환한다. 그리고 이 API 는 JS 가 심는 쿠키
(ufp = fingerprint, XSRF-TOKEN)가 없으면 rtnList 를 주지 않는다. 그래서
Playwright 로 셸 페이지를 한 번 열어 세션을 만든 뒤, 같은 컨텍스트의
request 로 API 를 호출한다.

컬렉션 선택 주의: 형제 엔드포인트인 orginlInfoList.ajax(원문정보)로 조회하면
풍력 사업명 키워드가 전부 0건이다. 반드시 infoList.ajax(정보목록)를 쓴다.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from config import GOTO_TIMEOUT, playwright_proxy
from keywords import load_keywords
from scrapers.retry import goto_with_retry

KST = timezone(timedelta(hours=9))

BASE = "https://www.open.go.kr"
SEARCH_PAGE = BASE + "/com/search/uniSrhMoreList.do"
LIST_API = BASE + "/othicInfo/infoList/infoList.ajax"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# 이 건수를 넘으면 키워드가 너무 광범위하다는 신호다(예: '시루' 18,928건).
NOISY_TOTAL = 500

log = logging.getLogger(__name__)


def search_url(keyword: str) -> str:
    return f"{SEARCH_PAGE}?kwd={quote(keyword)}"


def extract_dept(record: dict) -> str:
    """발송처의 마지막 부서명만 뽑는다.

    CHRG_DEPT_NM 이 이미 말단 부서명이다(예: '도시계획과'). 비어 있으면
    NFLST_CHRG_DEPT_NM('경상북도 경주시 도시개발국 도시계획과')의 마지막
    토큰을 쓴다. API 는 공백으로 계층을 구분한다.
    """
    dept = (record.get("CHRG_DEPT_NM") or "").strip()
    if dept:
        return dept
    full = (record.get("NFLST_CHRG_DEPT_NM") or "").strip()
    return full.split()[-1] if full else ""


def to_iso_date(raw) -> str:
    """YYYYMMDD 또는 YYYYMMDDHHMMSS -> YYYY-MM-DD."""
    text = str(raw or "").strip()
    if len(text) >= 8 and text[:8].isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return ""


def normalize(record: dict, keyword: str) -> dict:
    """API 레코드를 대시보드 스키마로 변환한다.

    CHARGER_NM(담당자 실명)과 FILE_NM 은 의도적으로 제외한다. 대시보드가
    GitHub Pages 로 공개되므로 개인정보를 발행하지 않는다.
    """
    title = (record.get("INFO_SJ") or "").strip()
    date = to_iso_date(record.get("R_DATE"))
    doc_no = (record.get("DOC_NO") or "").strip()

    uid = (record.get("PRDCTN_INSTT_REGIST_NO") or "").strip()
    if not uid:
        uid = f"{doc_no}||{date}||{title}"

    return {
        "uid": uid,
        "title": title,
        "dept": extract_dept(record),
        "dept_full": (record.get("NFLST_CHRG_DEPT_NM") or "").strip(),
        "instt": (record.get("ALL_PROC_INSTT_NM") or "").strip(),
        "date": date,
        "prod_date": to_iso_date(record.get("P_DATE")),
        "doc_no": doc_no,
        "keyword": keyword,
        "url": search_url(keyword),
    }


def dedupe(items: list) -> list:
    """같은 공문이 여러 키워드에 걸리면 1건으로 합치고 최신순으로 정렬한다."""
    merged = {}
    for item in items:
        prev = merged.get(item["uid"])
        if prev is None:
            merged[item["uid"]] = item
        elif item["keyword"] not in prev["keyword"].split(", "):
            # 어떤 키워드로 걸렸는지 모두 보이게 합친다
            prev["keyword"] = f"{prev['keyword']}, {item['keyword']}"
    return sorted(merged.values(), key=lambda x: x["date"], reverse=True)


def _payload(keyword: str, cfg, start: str, end: str) -> dict:
    return {
        "kwd": keyword,
        "eduYn": "",
        "insttSeCd": "",
        "ignoreKeyword": "",
        "mustKeyword": "",
        "srchFd": "",
        "startDate": start,
        "endDate": end,
        "kwdUnit": "",
        "reSrchFlag": "off",
        "detailSearch": "false",
        "insttCd": "",
        "insttCdNm": "",
        "pageIndex": "1",
        "rowPage": str(cfg.row_page),
        "recordCountPerPage": str(cfg.row_page),
        "pageUnit": str(cfg.row_page),
    }


def fetch_open_portal(site: dict, p_instance) -> tuple:
    """지정 키워드로 정보목록을 조회해 정규화된 항목 목록을 반환한다."""
    cfg = load_keywords()
    for warning in cfg.warnings:
        log.warning(f"[{site['name']}] {warning}")

    today = datetime.now(KST).date()
    start = (today - timedelta(days=cfg.window_days)).strftime("%Y%m%d")
    end = (today + timedelta(days=1)).strftime("%Y%m%d")

    browser = None
    try:
        launch_kwargs = {"headless": True}
        if site.get("proxy"):
            proxy = playwright_proxy()
            if proxy:
                launch_kwargs["proxy"] = proxy
        browser = p_instance.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="ko-KR",
            extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
        )
        page = context.new_page()

        # 셸 페이지를 열어야 setFingerPrint.ajax 가 실행되고 ufp/XSRF 쿠키가 생긴다.
        goto_with_retry(
            page,
            search_url(cfg.keywords[0]),
            wait_until="networkidle",
            timeout=GOTO_TIMEOUT,
        )
        page.wait_for_timeout(2000)

        cookies = {c["name"]: c["value"] for c in context.cookies()}
        xsrf = cookies.get("XSRF-TOKEN", "")
        if not xsrf:
            log.warning(f"[{site['name']}] XSRF-TOKEN 미확보. 조회가 실패할 수 있습니다.")

        collected = []
        failed = []
        for keyword in cfg.keywords:
            try:
                resp = context.request.post(
                    LIST_API,
                    form=_payload(keyword, cfg, start, end),
                    headers={
                        "X-Requested-With": "XMLHttpRequest",
                        "X-XSRF-TOKEN": xsrf,
                        "Referer": search_url(keyword),
                    },
                    timeout=GOTO_TIMEOUT,
                )
                result = json.loads(resp.text()).get("result") or {}
            except Exception as e:
                log.error(f"[{site['name']}] '{keyword}' 조회 실패: {e}")
                failed.append(keyword)
                continue

            rows = result.get("rtnList")
            if rows is None:
                log.error(
                    f"[{site['name']}] '{keyword}' 응답에 rtnList 가 없습니다. "
                    "세션 쿠키 정책이 바뀌었을 수 있습니다."
                )
                failed.append(keyword)
                continue

            total = result.get("rtnTotal")
            # pageIndex 페이징이 동작하지 않아(1/2페이지 결과 동일) 한 번에 받는다.
            # 전량을 받지 못하면 조용히 누락되므로 반드시 경고를 남긴다.
            if isinstance(total, int) and total > len(rows):
                log.warning(
                    f"[{site['name']}] '{keyword}' 전체 {total}건 중 {len(rows)}건만 "
                    f"수집했습니다. row_page({cfg.row_page}) 상향이 필요합니다."
                )
            if isinstance(total, int) and total > NOISY_TOTAL:
                log.warning(
                    f"[{site['name']}] '{keyword}' 가 {total}건입니다. 키워드가 너무 "
                    "광범위할 수 있습니다. 사업 전체명을 쓰세요."
                )

            collected.extend(normalize(r, keyword) for r in rows)
            log.info(f"[{site['name']}] '{keyword}' {len(rows)}건 (전체 {total})")

        if failed and len(failed) == len(cfg.keywords):
            return None, f"모든 키워드 조회 실패: {', '.join(failed)}"

        items = dedupe(collected)
        log.info(f"[{site['name']}] {len(items)}건 파싱 완료 (키워드 {len(cfg.keywords)}개)")
        return items, None

    except Exception as e:
        log.error(f"[{site['name']}] 스크래핑 실패: {e}")
        return None, str(e)
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
