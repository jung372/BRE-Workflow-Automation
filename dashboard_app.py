"""
로컬 모니터링 대시보드 서버 (백그라운드 자동 갱신)
실행: python dashboard_app.py
접속: http://localhost:5000
"""

import logging, os, threading, time
from flask import Flask, jsonify, send_from_directory

from logic.runner import run
from state        import STATE_FILE

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
_latest_data = {"checked_at": "-", "sites": [], "metmasts": [], "is_updating": True}
_data_lock   = threading.Lock()

app = Flask(__name__, static_folder=BASE_DIR)
log = logging.getLogger(__name__)


def update_loop():
    global _latest_data
    while True:
        try:
            with _data_lock:
                _latest_data["is_updating"] = True
            result = run()
            with _data_lock:
                _latest_data = result
        except Exception as e:
            log.error(f"업데이트 오류: {e}")
            with _data_lock:
                _latest_data["is_updating"] = False
        log.info("데이터 업데이트 완료. 1시간 대기...")
        time.sleep(3600)


@app.route("/api/status")
def api_status():
    with _data_lock:
        return jsonify(_latest_data)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    return jsonify({"ok": True})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    return jsonify({"ok": True})


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "dashboard.html")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    threading.Thread(target=update_loop, daemon=True).start()
    print("=" * 50)
    print("  주요 사이트 공지 모니터링 대시보드")
    print("  http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
