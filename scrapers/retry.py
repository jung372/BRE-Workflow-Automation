import time, logging

log = logging.getLogger(__name__)


def goto_with_retry(page, url, attempts=2, backoff_sec=8, **goto_kwargs):
    """page.goto() 실패 시 지정 횟수만큼 재시도."""
    last_exc = None
    for i in range(attempts):
        try:
            return page.goto(url, **goto_kwargs)
        except Exception as e:
            last_exc = e
            if i < attempts - 1:
                log.warning(f"goto 실패 (시도 {i + 1}/{attempts}), {backoff_sec}s 후 재시도: {e}")
                time.sleep(backoff_sec)
    raise last_exc
