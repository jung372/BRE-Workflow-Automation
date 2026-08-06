"""수집 결과를 저장소에 발행한다.

서버에서는 BRE_DATA_DIR 이 발행 전용 git clone(publish)을 가리키므로
스크래핑이 이미 그 위치에 기록한다. 따라서 파일 복사 단계는 없다.

발행 대상 두 파일은 git 추적을 유지한다.
  data/status.json  GitHub Pages 대시보드가 읽음
  last_state.json   report.yml(Teams 보고)이 클라우드에서 읽음

commit 메시지에 [skip ci] 를 붙이고 워크플로에서 두 경로를 paths-ignore 하여
데이터 push 가 배포를 다시 트리거하지 않게 한다.
"""

import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone

from runtime_config import get_data_dir

KST = timezone(timedelta(hours=9))

TRACKED_FILES = ["data/status.json", "last_state.json"]

log = logging.getLogger(__name__)


def skip_push() -> bool:
    return os.environ.get("BRE_SKIP_PUSH", "").strip() in ("1", "true", "True")


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(get_data_dir()),
        check=check,
        capture_output=True,
    )


def _stderr(exc: subprocess.CalledProcessError) -> str:
    if exc.stderr:
        return exc.stderr.decode("utf-8", errors="replace").strip()
    return str(exc)


def is_git_repo() -> bool:
    """BRE_DATA_DIR 이 git 작업 트리인지 확인한다(개발 PC는 저장소 루트)."""
    try:
        result = _git("rev-parse", "--is-inside-work-tree", check=False)
    except FileNotFoundError:
        return False
    return result.returncode == 0


def prepare_publish() -> bool:
    """스크래핑 전에 원격 이력을 먼저 받아 둔다.

    스크래핑 후에 pull 하면 방금 갱신한 6MB last_state.json 과 원격 이력이
    충돌한다. 순서를 반드시 지켜야 하는 이유다.
    """
    if skip_push() or not is_git_repo():
        return False
    try:
        _git("pull", "--rebase", "--autostash")
        log.info("publish clone 최신화 완료")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"publish clone pull 실패 - 이번 회차 push 생략: {_stderr(e)}")
        _git("rebase", "--abort", check=False)
        return False


def push_to_github() -> bool:
    """수집 결과를 commit & push 한다. 실제로 push 했으면 True."""
    if skip_push():
        log.info("BRE_SKIP_PUSH 설정 - push 생략")
        return False
    if not is_git_repo():
        log.warning(f"git 작업 트리가 아님 - push 생략: {get_data_dir()}")
        return False

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    try:
        _git("add", "--", *TRACKED_FILES)
        if _git("diff", "--staged", "--quiet", check=False).returncode == 0:
            log.info("변경사항 없음 - push 생략")
            return False

        _git("commit", "-m", f"chore: update monitoring data [{now}] [skip ci]")
        _git("push")
        log.info(f"GitHub push 완료: {now}")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"Git 작업 실패: {_stderr(e)}")
        return False
