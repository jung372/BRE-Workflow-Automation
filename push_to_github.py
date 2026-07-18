import subprocess
import logging
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def push_to_github():
    now = datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')
    try:
        subprocess.run(
            ['git', 'add', 'data/status.json', 'last_state.json'],
            check=True, capture_output=True
        )
        diff = subprocess.run(['git', 'diff', '--staged', '--quiet'])
        if diff.returncode != 0:
            subprocess.run(
                ['git', 'commit', '-m', f'chore: update monitoring data [{now}]'],
                check=True, capture_output=True
            )
            subprocess.run(['git', 'push'], check=True, capture_output=True)
            logging.info(f"GitHub push 완료: {now}")
        else:
            logging.info("변경사항 없음 - push 생략")
    except subprocess.CalledProcessError as e:
        logging.error(f"Git 작업 실패: {e.stderr.decode('utf-8', errors='replace') if e.stderr else e}")
