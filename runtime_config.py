"""데이터·런타임·환경파일 경로를 한곳에서 관리한다.

서버 PC는 코드(릴리스 폴더)와 데이터(publish clone)와 런타임(로그·락)을
서로 다른 위치에 둔다. 개발 PC는 환경변수를 설정하지 않으므로 모두
프로젝트 루트로 폴백해 기존과 동일하게 동작한다.

환경변수:
  BRE_DATA_DIR     last_state.json / data/status.json 기준 경로
  BRE_RUNTIME_DIR  로그·락·배포 메타 기준 경로
  BRE_ENV_FILE     .env 경로 (미설정 시 RuntimeRoot/.env → 프로젝트 루트/.env)
  BRE_NODE_ROLE    'server' 이면 서버 노드
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # report.yml(클라우드)은 requests만 설치한다
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parent


def _expanded_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def ensure_utf8_stdout() -> None:
    """콘솔 코드페이지가 한글을 담지 못해도 죽지 않게 한다.

    GitHub windows-latest 러너의 stdout 은 cp1252 라서 한글을 print 하면
    UnicodeEncodeError 로 프로세스가 죽는다. 사이트명·키워드 값 자체가
    한글이므로 메시지를 ASCII 로 바꾸는 것으로는 해결되지 않는다.
    errors='replace' 를 둬서 최악의 경우에도 죽지 않고 물음표로 대체한다.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def get_data_dir() -> Path:
    """last_state.json 과 data/status.json 이 놓이는 디렉터리를 반환한다.

    서버에서는 발행 전용 git clone(publish)을 가리켜, 배포·롤백이 데이터를
    건드리지 않게 한다. 이 두 파일은 GitHub Pages 대시보드와 Teams 보고
    워크플로가 저장소에서 직접 읽으므로 git 추적 대상으로 유지된다.
    """
    configured = os.getenv("BRE_DATA_DIR", "").strip()
    if configured:
        return _expanded_path(configured)
    return PROJECT_ROOT


def get_runtime_dir() -> Path:
    """로그·락·배포 메타를 보존할 디렉터리를 반환한다."""
    configured = os.getenv("BRE_RUNTIME_DIR", "").strip()
    if configured:
        return _expanded_path(configured)
    return PROJECT_ROOT


def get_env_file() -> Path:
    """서버 외부 .env를 우선하고 기존 프로젝트 .env를 호환 지원한다."""
    configured = os.getenv("BRE_ENV_FILE", "").strip()
    if configured:
        return _expanded_path(configured)

    runtime_env = get_runtime_dir() / ".env"
    if runtime_env.exists():
        return runtime_env
    return PROJECT_ROOT / ".env"


def get_log_dir() -> Path:
    return get_runtime_dir() / "logs"


def get_keywords_file() -> Path:
    """정보공개 청구 감시 키워드 설정 경로를 반환한다.

    설정 데이터이므로 데이터 쪽(publish clone)을 우선한다. 그러면 GitHub 에서
    파일만 고쳐도 다음 정시 실행에 반영되고 재배포가 필요 없다. 개발 PC는
    BRE_DATA_DIR 이 없어 저장소 사본으로 폴백한다.
    """
    data_copy = get_data_dir() / "config" / "keywords.json"
    if data_copy.exists():
        return data_copy
    return PROJECT_ROOT / "config" / "keywords.json"


def get_state_file() -> Path:
    return get_data_dir() / "last_state.json"


def get_status_file() -> Path:
    return get_data_dir() / "data" / "status.json"


def load_app_environment() -> Path:
    """이미 프로세스에 설정된 값을 유지하면서 환경파일을 불러온다."""
    env_file = get_env_file()
    if load_dotenv is not None and env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)
    return env_file


def is_server_node() -> bool:
    """예약 작업으로 운영되는 서버 노드인지 확인한다."""
    return os.getenv("BRE_NODE_ROLE", "development").strip().lower() == "server"


load_app_environment()
