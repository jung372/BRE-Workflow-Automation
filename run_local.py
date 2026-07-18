import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("run_local.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
)

from logic.runner import run
from push_to_github import push_to_github

if __name__ == "__main__":
    logging.info("=== 스크래핑 시작 ===")
    run()
    logging.info("스크래핑 완료 - GitHub push 시작")
    push_to_github()
    logging.info("=== 완료 ===")
