# PRD — BRE Workflow 다중 PC 개발 · 서버 자동배포

- 작성일: 2026-08-06
- 대상 저장소: `jung372/BRE-Workflow-Automation2`
- 참조 구현: `Stock_Report_Codex` (동일 서버 PC에서 운영 중인 선행 사례)

## 1. 배경 및 문제

현재 BRE Workflow는 서버 PC 한 대가 "개발 환경 겸 운영 환경"이다. `D:\05 AI Study\BRE Workflow Automation`에 있는 git clone이 그대로 실행 대상이어서, 코드를 고치려면 그 PC에 접속해야 한다. 데스크탑 PC나 회사 노트북에서 코드를 수정해 push해도 서버 PC는 그 사실을 모른다. 오히려 서버가 매시간 `data/status.json`과 `last_state.json`을 commit & push하기 때문에 원격과 로컬이 계속 어긋난다.

| 현재 | 문제 |
|---|---|
| 서버 PC의 clone이 곧 운영 코드 | 다른 PC에서 고친 코드가 서버에 반영되지 않음 |
| 서버가 매시간 `data/status.json` + `last_state.json` push | 코드 commit과 데이터 commit이 뒤섞여 이력 추적 불가 |
| `last_state.json` 6MB가 git 추적 대상 | commit당 약 11만 줄 diff, clone·fetch 비용 증가 |
| 배포 전 검증 없음 | 깨진 코드가 곧바로 운영에 반영 |
| 롤백 수단 없음 | 장애 시 수동 복구 |
| 예약 작업이 `run_local.py`를 repo 루트에서 직접 실행 | 배포와 실행이 겹치면 부분 반영된 코드로 동작 |

**목표 상태.** `Stock_Report_Codex`와 동일하게 — 데스크탑 PC / 회사 노트북에서 코드를 수정 → `main`에 push → GitHub Actions가 검증 → 서버 PC의 self-hosted runner가 자동 배포 → 서버는 항상 최신 검증 commit 기준으로 시간당 스크래핑을 수행한다.

### 1.1 BRE 고유 제약 (Stock_Report_Codex에는 없음)

선행 사례를 그대로 복사할 수 없는 이유는 다음 네 가지다. 본 PRD의 설계 판단은 대부분 여기서 파생된다.

1. **서버가 같은 repo에 데이터를 push한다** → 배포 트리거 무한루프가 발생하고, 롤백 시 코드와 함께 데이터까지 되돌려진다.
2. **상시 웹서버가 없다** (배치 작업) → `/status` 같은 헬스체크 대상이 존재하지 않는다.
3. **데이터 2종이 반드시 git에 남아야 한다** — 아래 3.1 참조. 따라서 "데이터를 git에서 제거"하는 해법은 쓸 수 없고, **위치만 분리**해야 한다.
4. **GitHub Pages가 repo 루트를 그대로 서빙한다** (`https://jung372.github.io/BRE-Workflow-Automation2/`) → `data/status.json`은 계속 커밋되어야 한다.

### 1.2 git 추적을 유지해야 하는 데이터

Teams 정기 보고는 **GitHub Actions(`report.yml`)에서 발송하는 현행 체계를 그대로 유지한다.** 이 워크플로는 클라우드 러너에서 저장소를 체크아웃해 `last_state.json`을 읽고 전일/금일 08시 스냅샷을 비교하므로, 상태파일이 저장소에 없으면 동작할 수 없다.

| 파일 | 크기 | git 추적 이유 |
|---|---|---|
| `data/status.json` | 약 3KB | GitHub Pages 대시보드가 읽음 |
| `last_state.json` | 약 6MB | `report.yml`(Teams 발송)이 클라우드에서 읽음 |

> **설계 귀결.** 데이터를 저장소 밖으로 뺄 수 없으므로, "런타임 디렉터리로 이전"이 아니라 **"릴리스 폴더 밖의 전용 git clone에 배치"** 방식을 택한다. 결과적으로 배포·롤백이 데이터를 건드리지 않는다는 목표(G5)는 동일하게 달성된다. 저장소 용량 증가는 현행과 동일한 수준으로 유지되며 별도 과제로 남긴다(10항).

## 2. 목표 / 비목표

**목표**

- G1. 개발 PC(데스크탑, 회사 노트북)에서 `main` push 시 서버 PC가 자동으로 최신 검증 commit으로 전환된다.
- G2. 검증(문법·단위테스트·실제 스크래핑 스모크)을 통과한 commit만 배포된다.
- G3. 배포 실패 시 직전 릴리스로 자동 롤백된다.
- G4. 배포와 시간당 스크래핑이 서로를 침범하지 않는다.
- G5. 운영 상태 데이터(`last_state.json`)와 비밀정보(`.env`)가 배포·롤백의 영향을 받지 않는다.
- G6. GitHub Pages 대시보드가 기존과 동일하게 동작한다.
- G7. **Teams 정기 보고는 GitHub Actions(`report.yml`)에서 발송하는 현행 체계를 그대로 유지한다.**

**비목표**

- 스크래핑 대상 사이트·파싱 로직 변경
- 대시보드 UI 변경
- **Teams 발송 체계 변경** (클라우드 → 서버 이관하지 않음)
- `last_state.json`의 git 추적 해제
- 서버 이중화·무중단 배포 (배치 작업이므로 불필요)

## 3. 대상 노드

| 장비 | Tailscale 이름 | 역할 | 경로 |
|---|---|---|---|
| 데스크탑 PC | `desktop-n9l7j2p` | 개발 | `C:\Personal\05 AI Study\BRE Workflow` (※ 현재 접속 불가, 잠정값 — 최초 clone 시 확정) |
| 회사 노트북 | `nb01-pf4jsbde` | 개발 (사내 프록시 `HTTP_PROXY_KR` 사용) | `C:\Personal\05 AI Study\BRE Workflow` |
| 서버 PC | `desktop-evu6usl` | 운영·배포 대상. Stock_Report_Codex와 동일 PC | 아래 4항 |

개발 PC 2대는 경로 규약을 동일하게 맞춘다. 두 PC의 `.env`는 각자 로컬에만 존재하며(git 제외), 회사 노트북에는 `HTTP_PROXY_KR`을 추가로 설정한다.

## 4. 서버 PC 디렉터리 구조

```
D:\05 AI Study\BRE Workflow Automation\        InstallRoot
  releases\20260806_143000_abc123def456\       릴리스 스냅샷(.git 없음) + 전용 .venv
  launcher\run_scrape.ps1                      현재 릴리스를 찾아 실행하는 진입점
  current_release.txt                          현재 릴리스 포인터

D:\05 AI Study\BRE_Workflow_runtime\           RuntimeRoot (배포와 무관하게 영속)
  .env                                         METMAST_*, HTTP_PROXY_KR
  deployment.json                              현재 배포 메타(commit, release, 시각)
  logs\run_local.log, logs\deploy.log
  run.lock / deploy.lock                       상호배제
  publish\                                     DataRoot — 데이터 발행 전용 git clone
    last_state.json                              상태 DB (git 추적)
    data\status.json                             대시보드 데이터 (git 추적)

D:\actions-runner-bre-workflow\                GitHub Actions 러너 (Stock 러너와 별도)
```

역할이 셋으로 갈린다.

| 구분 | 위치 | 배포 시 |
|---|---|---|
| 코드 | `releases\<ts>_<sha>\` | 매 배포마다 새로 생성, 포인터로 전환 |
| 데이터 | `RuntimeRoot\publish\` (git clone) | **손대지 않음** |
| 비밀정보·로그 | `RuntimeRoot\` | **손대지 않음** |

`TEAMS_WEBHOOK_URL`은 GitHub Secret에 그대로 두며 서버 `.env`에는 넣지 않는다.

Stock_Report_Codex와 동일 PC이므로 러너 루트·러너 이름·레이블·예약 작업 이름을 모두 분리한다.

## 5. 아키텍처

### 5.1 코드 흐름 (배포)

```
개발 PC ──push main──▶ GitHub
                        │
                        ├─ test job (windows-latest)
                        │    compileall / unittest / import 스모크
                        │
                        └─ deploy job (self-hosted, bre-workflow-server)
                             scripts\deploy_server.ps1
                               1. deploy.lock 확보, 진행 중 스크래핑 종료 대기
                               2. 워크스페이스 → releases\<ts>_<sha> robocopy
                               3. 릴리스 전용 .venv + requirements + playwright chromium
                               4. 릴리스 내 unittest 실행
                               5. 실제 스크래핑 스모크 (격리 런타임, push 생략)
                               6. current_release.txt 전환
                               7. deployment.json 기록 / 실패 시 포인터 복구 후 실패
```

### 5.2 데이터 흐름 (운영)

```
예약 작업 "BRE Scraper" (매시 06~20 KST)
  └ launcher\run_scrape.ps1 → 현재 릴리스 .venv → run_local.py
       코드: releases\<현재>\        (읽기 전용)
       데이터: RuntimeRoot\publish\  (읽기·쓰기)
         스크래핑 → last_state.json 갱신 + data\status.json 생성
                  → git pull --rebase → commit & push
                       ├▶ GitHub Pages 갱신 (status.json)
                       └▶ report.yml 입력 갱신 (last_state.json)

GitHub Actions "report.yml" (평일 08:30 KST, ubuntu-latest)  ※ 현행 유지
  └ checkout → last_state.json 전일/금일 08시 비교 → Teams 발송
```

**선행 의존성.** `report.yml`이 08:30에 읽는 것은 서버가 08:00 회차에 push한 `last_state.json`이다. 서버가 08시에 꺼져 있으면 그날 보고는 전일 데이터 기준이 된다 — 현행과 동일한 특성이며 본 과제에서 바꾸지 않는다.

### 5.3 무한루프 차단

서버의 데이터 push가 배포를 다시 트리거하지 않도록 **3중 방어**를 둔다.

1. `ci-deploy.yml`의 `paths-ignore: ['data/status.json', 'last_state.json']`
2. 데이터 commit 메시지에 `[skip ci]` 부가
3. deploy job의 `if`에 `vars.SERVER_DEPLOY_ENABLED == 'true'` 게이트

`report.yml`은 `schedule`·`workflow_dispatch`로만 실행되므로 데이터 push에 영향받지 않는다.

## 6. 상세 요구사항

### 6.1 경로 해석 분리 (신규 `runtime_config.py`)

`Stock_Report_Codex/app_config.py`와 동일한 패턴으로 작성한다.

| 함수 | 동작 |
|---|---|
| `get_data_dir()` | `BRE_DATA_DIR` 환경변수 우선, 없으면 프로젝트 루트. `last_state.json`과 `data\status.json`의 기준 경로 |
| `get_runtime_dir()` | `BRE_RUNTIME_DIR` 우선, 없으면 프로젝트 루트. 로그·락·배포 메타의 기준 경로 |
| `get_env_file()` | `BRE_ENV_FILE` 우선 → `RuntimeRoot\.env` → 프로젝트 루트 `.env` |
| `load_app_environment()` | `override=False`로 `.env` 로드 |
| `is_server_node()` | `BRE_NODE_ROLE == 'server'` |

개발 PC는 `BRE_DATA_DIR`·`BRE_RUNTIME_DIR`을 설정하지 않으므로 모두 프로젝트 루트로 폴백해 **현행과 동일하게 동작**한다.

기존 진입점(`run_local.py`, `dashboard_app.py`)의 `load_dotenv(Path(__file__).parent / '.env')`를 `load_app_environment()`로 대체한다.

### 6.2 데이터 위치 재배치 (git 추적은 유지)

`last_state.json`과 `data/status.json`은 **저장소에 계속 추적**한다(1.2항). 바꾸는 것은 서버에서의 물리적 위치뿐이다.

- `state.py`의 `STATE_FILE`을 `get_data_dir() / "last_state.json"`으로 변경
- `logic/runner.py`의 `DATA_DIR`/`OUTPUT`을 `get_data_dir() / "data" / "status.json"` 기준으로 변경 (현재 `logic/runner.py:11`의 `_ROOT` 계산을 대체)
- `notify_teams.py`의 `STATUS_FILE`도 동일 기준으로 변경 (클라우드에서는 `BRE_DATA_DIR` 미설정 → 체크아웃 루트로 폴백되어 현행 동작 유지)
- `.gitignore`는 **변경하지 않음** (`last_state.json` 추적 유지)
- `report.yml`은 **유지**, `TEAMS_WEBHOOK_URL`은 **GitHub Secret에 유지**
- 서버 최초 세팅 시 기존 `last_state.json`을 `publish` clone으로 이동 (`setup_server.ps1`이 자동 수행)

이로써 릴리스 폴더에는 데이터가 존재하지 않고, 배포·롤백이 데이터에 영향을 주지 않는다(G5).

### 6.3 데이터 발행 (`push_to_github.py` 개편)

릴리스 폴더에는 `.git`이 없으므로 push는 전용 clone(`RuntimeRoot\publish`)에서 수행한다. 이 clone이 곧 `BRE_DATA_DIR`이므로 **파일 복사 단계가 없다** — 스크래핑이 이미 그 위치에 기록한다.

- 발행 대상: `data/status.json`, `last_state.json`
- 절차: `git pull --rebase` → `git add` 두 파일 → 변경 없으면 skip → `git commit -m "chore: update monitoring data [<KST>] [skip ci]"` → `git push`
- 순서 주의: 스크래핑 **전에** `git pull --rebase`를 수행한다. 스크래핑 후에 pull하면 방금 갱신한 `last_state.json`과 원격 이력이 충돌한다.
- `publish` clone이 없으면 최초 1회 생성 (`setup_server.ps1`)
- `BRE_SKIP_PUSH=1`이면 push 단계 전체 생략 (스모크·개발 PC용)

### 6.4 실행 진입점 (`run_local.py`)

- `--smoke` : 격리 런타임 디렉터리 사용 + push 생략 + 스모크 판정 종료코드 반환
- `--no-push` : 스크래핑만 수행
- 시작 시 `deploy.lock`이 있으면 이번 회차 skip (로그 기록)
- 실행 중 `run.lock` 생성, 종료 시 해제 (비정상 종료 대비 stale lock 타임아웃 30분)
- 로그를 `RuntimeRoot\logs\run_local.log`로 출력

### 6.5 검증 게이트

**test job (GitHub 호스팅 `windows-latest`)**

- `pip install -r requirements.txt`, `playwright install chromium`
- `python -m compileall -q config.py state.py runtime_config.py scraper.py run_local.py notify_teams.py push_to_github.py logic scrapers presentation`
- `python -m unittest discover -s tests -p "test_*.py" -v`

**신규 `tests/`** — 현재 저장소에 테스트가 없다. 외부 네트워크에 의존하지 않는 단위 테스트를 추가한다.

| 파일 | 검증 대상 |
|---|---|
| `tests/test_state.py` | `item_id` 정규화(NEW 접미사 제거), `get_baseline_ids` 5일 기준·레거시 list 형식, `update_site_state` KEEP_DAYS 정리 |
| `tests/test_detector.py` | `get_new_items` 신규 추출, `prev_weekday` 월요일 → 금요일 |
| `tests/test_config.py` | `playwright_proxy`/`requests_proxies` 파싱, `SITES` 필수 키·id 중복 없음 |
| `tests/test_runtime_config.py` | 환경변수 우선순위, 미설정 시 프로젝트 루트 폴백 |

**스모크 (deploy job, 서버 PC)**

- `BRE_DATA_DIR`·`BRE_RUNTIME_DIR`을 모두 `<release>\_smoke`로 지정해 실제 `last_state.json`·`status.json`을 오염시키지 않는다
  - 특히 `hourly_snapshots`는 `YYYY-MM-DD HH` 키로 덮어쓰기되므로, 08시대에 배포하면 `report.yml`이 읽을 08시 스냅샷이 스모크 결과로 바뀔 수 있다. 격리가 필수인 이유다.
- 빈 상태에서 시작하므로 baseline이 없어 신규 항목은 0건으로 나온다 (정상)
- `.env`는 RuntimeRoot 것을 참조 (실제 자격증명·프록시까지 검증)
- 판정: 종료코드 0 **AND** 오류 없이 수집된 사이트 수 ≥ `BRE_SMOKE_MIN_OK` (기본 3 / 전체 5)

> **트레이드오프.** 정부 사이트(KOREC·NIE·EIASS)는 간헐적으로 타임아웃된다. "전체 사이트 성공"을 요구하면 정상 코드도 배포에 실패한다. 임계값 방식으로 완화하되, 값은 저장소 변수로 조정 가능하게 둔다.

### 6.6 배포 스크립트 `scripts\deploy_server.ps1`

`Stock_Report_Codex/scripts/deploy_server.ps1`을 원본으로 하되 아래를 교체한다.

| Stock | BRE |
|---|---|
| 포트 5000 점유 프로세스 정리 | `run.lock` 대기 + 스크래핑 예약 작업 일시 중지 |
| `/status` 헬스체크 | 6.5의 스모크 실행 결과 |
| 서버 프로세스 재시작 | 예약 작업 재개 (다음 정시에 새 릴리스로 실행) |

유지하는 요소: robocopy 릴리스 복사, 릴리스 전용 venv, `release.json`, `current_release.txt` 포인터 전환, 이전 릴리스 기록 및 실패 시 포인터 복구, `deployment.json` 기록.

robocopy 제외 대상: `.git .venv __pycache__ releases launcher data tests\artifacts` / `.env *.log *.pyc last_state.json`

`data` 디렉터리와 `last_state.json`을 제외하는 이유는 릴리스 폴더에 **오래된 데이터 사본이 남지 않게** 하기 위함이다. 실제 데이터는 `BRE_DATA_DIR`(=`publish` clone)에서만 읽고 쓴다.

### 6.7 워크플로 `.github/workflows/ci-deploy.yml`

```yaml
on:
  push:
    branches: [main]
    paths-ignore: ['data/status.json', 'last_state.json']
  workflow_dispatch:
concurrency:
  group: bre-workflow-production
  cancel-in-progress: false
```

- `test` : `windows-latest` (서버와 동일 OS)
- `deploy` : `needs: test`, `runs-on: [self-hosted, windows, x64, bre-workflow-server]`,
  `if: github.repository == 'jung372/BRE-Workflow-Automation2' && vars.SERVER_DEPLOY_ENABLED == 'true'`,
  `timeout-minutes: 45` (스모크 스크래핑 포함)

### 6.8 세팅 스크립트

| 스크립트 | 역할 |
|---|---|
| `scripts\setup_server.ps1` | RuntimeRoot 생성, `.env` 템플릿 배치(플레이스홀더 남으면 exit 2), `publish` clone 생성, 기존 `last_state.json`을 `publish` clone으로 이전, 초기 배포(`-SkipSmoke`), 예약 작업 `BRE Scraper`(매시 06~20 KST) 등록 |
| `scripts\setup_github_runner.ps1` | 러너 다운로드·등록. `RunnerRoot=D:\actions-runner-bre-workflow`, `RunnerName=desktop-evu6usl-bre`, `Labels=bre-workflow-server`, 예약 작업 `BRE Workflow Runner`(로그온 시 자동 시작 + 재시작 루프) |
| `scripts\run_scrape.ps1` | 런처. 포인터 → 릴리스 venv → `BRE_DATA_DIR`·`BRE_RUNTIME_DIR`·`BRE_ENV_FILE`·`BRE_NODE_ROLE` 설정 → `run_local.py` |
| `scripts\doctor.ps1` | Python / git / 러너 작업 상태 / 스크래퍼 작업 `LastTaskResult` / 포인터 / `.env` 플레이스홀더 / `publish` clone 원격 도달성 및 미푸시 commit 유무 / `last_state.json` 신선도 / Pages `status.json` 갱신 시각 점검 |

예약 작업은 `BRE Scraper` 하나만 등록한다. Teams 발송은 GitHub Actions에 그대로 두므로 서버 작업이 필요 없다.

기존 `register_task.ps1`, `setup_scheduler.bat`는 `setup_server.ps1`로 대체하고 삭제한다.

### 6.9 개발 PC 워크플로 (README 문서화)

```powershell
git switch main; git pull --ff-only
git switch -c feature/작업이름
# 수정
python -m unittest discover -s tests -p "test_*.py" -v
git add -A; git commit -m "..."; git push -u origin feature/작업이름
# PR → main 병합 → 자동 배포
```

개발 PC는 `.env`를 저장소 루트에 두고 `BRE_DATA_DIR`·`BRE_RUNTIME_DIR`을 설정하지 않는다 → 상태파일도 루트에 생성되어 기존과 동일하게 동작한다. 같은 브랜치를 두 PC에서 동시에 수정하지 않는 것이 충돌을 줄이는 가장 단순한 원칙이다.

**주의.** 개발 PC에서 스크래핑을 직접 실행하면 루트의 `last_state.json`이 갱신되어 커밋 대상으로 잡힌다. 개발 PC에서 실행할 때는 `--no-push`를 쓰고, `git add -A` 전에 `git status`로 데이터 파일이 섞이지 않았는지 확인한다.

## 7. 마이그레이션 순서

1. 로컬에 남아 있는 프록시·재시도 변경(`config.py`, `scrapers/*`)을 먼저 commit & push
2. 코드 변경 일괄 반영 (`runtime_config.py`, `state.py`, `logic/runner.py`, `notify_teams.py`, `push_to_github.py`, `run_local.py`, `tests/`, `scripts/`, `ci-deploy.yml`) → push (아직 `SERVER_DEPLOY_ENABLED` 미설정이므로 자동 배포는 일어나지 않음)
3. 기존 `register_task.ps1`·`setup_scheduler.bat` 삭제
4. 서버 PC: 기존 `BRE-Scraper` 예약 작업 중지 → `last_state.json` 백업 → `setup_server.ps1` 실행 → `.env` 실제 값 입력 → 재실행
5. 서버 PC: `setup_github_runner.ps1` 실행 (관리자 PowerShell)
6. 저장소 변수 `SERVER_DEPLOY_ENABLED=true` 설정
7. 빈 commit push로 전체 파이프라인 1회 검증
8. `doctor.ps1` 통과 확인
9. 다음 평일 08:30 `report.yml` 실행 결과 확인 (Teams 수신)

`report.yml`과 `.gitignore`는 손대지 않으므로 Teams 발송 경로는 마이그레이션 전 구간에서 중단 없이 유지된다.

**롤백 계획:** `SERVER_DEPLOY_ENABLED=false` → 러너 작업 중지 → 서버에서 이전 clone 기준 `BRE-Scraper` 재등록 (`publish` clone의 `last_state.json`을 원래 위치로 복사).

## 8. 성공 기준

| # | 기준 | 확인 방법 |
|---|---|---|
| A1 | 개발 PC push 후 5분 내 서버 `current_release.txt`가 해당 sha로 전환 | `deployment.json`의 `commit_sha` |
| A2 | 검증 실패 commit은 배포되지 않음 | 의도적으로 깨진 commit push → deploy job 미실행 |
| A3 | 스모크 실패 시 직전 릴리스로 포인터 복구 | 포인터 값 비교 |
| A4 | 배포와 스크래핑이 겹치지 않음 | 스크래핑 실행 중 수동 배포 → 로그에 대기 기록 |
| A5 | 배포 후에도 상태·자격증명 보존 | `publish\last_state.json` mtime·크기 유지, `.env` 불변 |
| A6 | Pages 대시보드 정상 | `status.json` 갱신 시각 |
| A7 | **Teams 보고가 GitHub Actions에서 계속 발송됨** | 평일 08:30 `report.yml` 성공 + Teams 수신 |
| A8 | 데이터 commit이 배포를 트리거하지 않음 | Actions 실행 이력 |
| A9 | 릴리스 폴더에 데이터 사본이 없음 | `releases\<현재>\`에 `last_state.json`·`data\` 부재 |

## 9. 리스크

| 리스크 | 완화 |
|---|---|
| 서버 PC 로그오프/재부팅 시 러너 정지 | 로그온 트리거 + 재시작 루프, `doctor.ps1`로 상태 확인 |
| 정부 사이트 간헐 장애로 스모크 실패 | `BRE_SMOKE_MIN_OK` 임계값 + `workflow_dispatch` 재실행 |
| 스모크가 매 배포마다 실제 트래픽 발생 | 배포 빈도가 낮아 허용. 잦아지면 `[skip smoke]` 커밋 태그 도입 |
| 릴리스 폴더 디스크 누적 | 최근 5개만 보존하고 정리 |
| Stock 러너와 자원 경합 | 러너 루트·레이블·작업명 완전 분리, 동시 실행 허용 |
| `publish` clone 최초 생성 시 저장소 용량 (6MB × 과거 370 commit 이력) | 최초 1회 clone 비용은 감수. 이후 fetch는 증분. history 정리는 10항 별도 과제 |
| `publish` clone에서 rebase 충돌 (6MB JSON) | 스크래핑 **전에** `git pull --rebase` 수행(6.3항). 충돌 시 원격 우선으로 리셋하고 다음 회차에 재생성 |
| 서버가 08시에 꺼져 있으면 Teams 보고가 전일 기준 | 현행과 동일한 특성. `doctor.ps1`의 `last_state.json` 신선도 점검으로 조기 인지 |

## 10. 열린 이슈

- `last_state.json` 과거 이력(약 370 commit × 6MB) 정리 여부 — 별도 과제. 정리하면 `publish` clone 비용과 fetch 시간이 크게 줄어든다.
- 배포 결과 Teams 알림 추가 여부
