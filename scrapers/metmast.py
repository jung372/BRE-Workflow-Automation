import os, logging
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_LOGIN_KEYWORDS = ["Welcome", "Meteo-40", "Logout", "Dashboard"]


def check_metmast(m: dict, p_instance) -> dict:
    """Ammonit 계측기 로그인 성공 여부로 Online/Offline 판정."""
    url  = m["url"]
    user = os.environ.get(f"{m['env_prefix']}_ID", "")
    pw   = os.environ.get(f"{m['env_prefix']}_PW", "")

    if not url or not user or not pw:
        return {"id": m["id"], "name": m["name"], "status": "Offline"}

    try:
        browser = p_instance.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page    = context.new_page()
        page.goto(url, timeout=40000, wait_until="load")

        try:
            page.wait_for_selector('input[name="access"], input[type="password"]', timeout=10000)
            page.fill('input[name="access"], input[type="password"]', "Ammonit")
            page.keyboard.press("Enter")
            page.wait_for_load_state("load")
            page.wait_for_timeout(3000)
        except Exception:
            pass

        try:
            page.wait_for_selector('input[name="user"], input[name*="login"]', timeout=10000)
            page.fill('input[name="user"], input[name*="login"]', user)
            page.fill('input[type="password"]', pw)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle", timeout=20000)
            page.wait_for_timeout(3000)
        except Exception:
            pass

        try:
            content = page.content()
        except Exception:
            page.wait_for_timeout(3000)
            content = page.content()
        browser.close()

        if any(kw in content for kw in _LOGIN_KEYWORDS):
            return {"id": m["id"], "name": m["name"], "status": "Online"}

        preview = BeautifulSoup(content, "html.parser").get_text(separator=" ", strip=True)[:200]
        log.warning(f"[{m['name']}] 키워드 미발견. 페이지: {preview}")
        return {"id": m["id"], "name": m["name"], "status": "Offline"}

    except Exception as e:
        log.error(f"[{m['name']}] 체크 오류: {e}")
        return {"id": m["id"], "name": m["name"], "status": "Offline"}
