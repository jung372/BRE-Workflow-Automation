"""서버 PC 예약 작업 진입점.

  python run_local.py              스크래핑 -> 발행(commit & push)
  python run_local.py --no-push    스크래핑만 (개발 PC 권장)
  python run_local.py --smoke      배포 검증용. 격리 디렉터리 사용, 발행 생략

종료 코드
  0  정상
  1  스크래핑 예외
  2  스모크 판정 실패 (수집 성공 사이트 수 < BRE_SMOKE_MIN_OK)
  3  배포 진행 중이라 이번 회차 건너뜀
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from runtime_config import (
    ensure_utf8_stdout,
    get_log_dir,
    get_runtime_dir,
    load_app_environment,
)

# 로그 메시지가 한글이다. 콘솔 코드페이지가 한글을 못 담으면 StreamHandler 가
# UnicodeEncodeError 로 죽는다(영문 로케일 Windows). 로깅 설정 전에 처리한다.
ensure_utf8_stdout()

# 스모크는 실제 데이터를 오염시키지 않도록 경로를 먼저 격리해야 한다.
# state.py / logic.runner 는 import 시점에 경로를 확정하므로 그 전에 처리한다.
_ARGS = argparse.ArgumentParser(description="BRE 모니터링 스크래핑 실행")
_ARGS.add_argument("--no-push", action="store_true", help="발행 단계 생략")
_ARGS.add_argument("--smoke", action="store_true", help="격리 디렉터리로 배포 검증 실행")
_ARGS.add_argument(
    "--smoke-min-ok",
    type=int,
    default=int(os.environ.get("BRE_SMOKE_MIN_OK", "3")),
    help="스모크 통과에 필요한 최소 수집 성공 사이트 수 (기본 3)",
)
args = _ARGS.parse_args()

if args.smoke:
    # hourly_snapshots 는 'YYYY-MM-DD HH' 키로 덮어써진다. 08시대에 배포하면
    # report.yml 이 읽을 08시 스냅샷이 스모크 결과로 바뀌므로 격리가 필수다.
    smoke_dir = Path(__file__).resolve().parent / "_smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    os.environ["BRE_DATA_DIR"] = str(smoke_dir)
    os.environ["BRE_RUNTIME_DIR"] = str(smoke_dir)
    os.environ["BRE_SKIP_PUSH"] = "1"
elif args.no_push:
    os.environ["BRE_SKIP_PUSH"] = "1"

load_app_environment()

LOG_DIR = get_log_dir()
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "run_local.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from logic.runner import run                                  # noqa: E402
from push_to_github import prepare_publish, push_to_github     # noqa: E402

RUNTIME_DIR = get_runtime_dir()
RUN_LOCK = RUNTIME_DIR / "run.lock"
DEPLOY_LOCK = RUNTIME_DIR / "deploy.lock"
STALE_LOCK_SECONDS = 30 * 60


def _is_stale(lock: Path) -> bool:
    try:
        return (time.time() - lock.stat().st_mtime) > STALE_LOCK_SECONDS
    except OSError:
        return True


def acquire_run_lock() -> bool:
    """실행 락을 잡는다. 배포 중이거나 이미 실행 중이면 False."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    if DEPLOY_LOCK.exists():
        if _is_stale(DEPLOY_LOCK):
            logging.warning("오래된 deploy.lock 무시하고 진행합니다.")
        else:
            logging.info("배포 진행 중 - 이번 회차를 건너뜁니다.")
            return False

    if RUN_LOCK.exists():
        if _is_stale(RUN_LOCK):
            logging.warning("오래된 run.lock 제거 후 진행합니다.")
            RUN_LOCK.unlink(missing_ok=True)
        else:
            logging.info("이전 회차가 아직 실행 중 - 이번 회차를 건너뜁니다.")
            return False

    RUN_LOCK.write_text(str(os.getpid()), encoding="utf-8")
    return True


def evaluate_smoke(results: dict, min_ok: int) -> bool:
    """수집 성공 사이트 수로 스모크를 판정한다.

    정부 사이트(KOREC/NIE/EIASS)는 간헐적으로 타임아웃되므로 '전체 성공'을
    요구하면 정상 코드도 배포에 실패한다. 임계값 방식으로 완화한다.
    """
    sites = results.get("sites", [])
    ok = [s for s in sites if not s.get("error")]
    failed = [s["name"] for s in sites if s.get("error")]

    logging.info(f"스모크 결과: 수집 성공 {len(ok)}/{len(sites)} (기준 {min_ok})")
    if failed:
        logging.warning(f"수집 실패 사이트: {', '.join(failed)}")

    if len(ok) < min_ok:
        logging.error("스모크 판정 실패 - 배포를 중단해야 합니다.")
        return False
    return True


def main() -> int:
    if not args.smoke and not acquire_run_lock():
        return 3

    try:
        logging.info(f"=== 스크래핑 시작 (smoke={args.smoke}) ===")
        # 스크래핑 전에 원격 이력을 먼저 받아야 last_state.json 충돌을 피한다.
        prepare_publish()

        try:
            results = run()
        except Exception:
            logging.exception("스크래핑 중 예외 발생")
            return 1

        if args.smoke:
            passed = evaluate_smoke(results, args.smoke_min_ok)
            logging.info("=== 스모크 완료 ===")
            return 0 if passed else 2

        push_to_github()
        logging.info("=== 완료 ===")
        return 0
    finally:
        if not args.smoke:
            RUN_LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
