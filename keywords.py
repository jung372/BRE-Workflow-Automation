"""정보공개 청구 감시 키워드 설정 로딩과 검증.

키워드는 코드가 아니라 설정 데이터다. 저장소의 config/keywords.json 을
GitHub 웹 편집기로 고치면 재배포 없이 다음 정시 실행부터 반영된다.
서버는 BRE_DATA_DIR(=publish clone)에서 읽고, publish clone 은 스크래핑
직전에 git pull 하므로 원격 수정이 자동으로 도달한다.

런타임에서는 절대 예외를 던지지 않는다. 파일이 없거나 깨져 있으면 기본값으로
동작하고 경고만 남긴다. 잘못된 편집 한 번으로 수집이 멈추면 안 되기 때문이다.
CI 검증(validate_file)은 반대로 문제를 발견하면 실패시켜 운영에 도달하지
못하게 막는다.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from runtime_config import ensure_utf8_stdout, get_keywords_file

DEFAULT_KEYWORDS = ("시루풍력", "왕신풍력", "해파랑육상풍력")
DEFAULT_WINDOW_DAYS = 90
DEFAULT_ROW_PAGE = 100

# 2자 키워드는 무관한 결과가 만 건 넘게 잡힌다('시루' 18,928건, '왕신' 10,859건).
MIN_KEYWORD_LEN = 3
MAX_KEYWORDS = 20
WINDOW_DAYS_RANGE = (7, 365)
ROW_PAGE_RANGE = (10, 200)


@dataclass(frozen=True)
class KeywordConfig:
    keywords: tuple = DEFAULT_KEYWORDS
    exact_title_keywords: tuple = ()
    window_days: int = DEFAULT_WINDOW_DAYS
    row_page: int = DEFAULT_ROW_PAGE
    source: str = "default"
    warnings: tuple = field(default_factory=tuple)


def validate(raw: dict) -> list:
    """설정 딕셔너리를 검증해 오류 메시지 목록을 반환한다. 비어 있으면 정상."""
    errors = []

    if not isinstance(raw, dict):
        return ["최상위 구조가 객체(JSON object)가 아닙니다."]

    kws = raw.get("keywords")
    normalized_keywords = set()
    if not isinstance(kws, list):
        errors.append("keywords 가 배열이 아닙니다.")
    elif not kws:
        errors.append("keywords 가 비어 있습니다. 최소 1개가 필요합니다.")
    elif len(kws) > MAX_KEYWORDS:
        errors.append(f"keywords 가 {len(kws)}개입니다. 최대 {MAX_KEYWORDS}개까지 허용합니다.")
    else:
        seen = set()
        for i, kw in enumerate(kws):
            if not isinstance(kw, str):
                errors.append(f"keywords[{i}] 가 문자열이 아닙니다: {kw!r}")
                continue
            stripped = kw.strip()
            if not stripped:
                errors.append(f"keywords[{i}] 가 빈 문자열입니다.")
            elif len(stripped) < MIN_KEYWORD_LEN:
                errors.append(
                    f"keywords[{i}] '{stripped}' 가 {MIN_KEYWORD_LEN}자보다 짧습니다. "
                    "짧은 키워드는 무관한 결과가 폭증하므로 사업 전체명을 쓰세요."
                )
            elif stripped in seen:
                errors.append(f"keywords[{i}] '{stripped}' 가 중복입니다.")
            else:
                seen.add(stripped)
                normalized_keywords.add(stripped)

    exact_kws = raw.get("exact_title_keywords", [])
    if not isinstance(exact_kws, list):
        errors.append("exact_title_keywords 가 배열이 아닙니다.")
    else:
        seen_exact = set()
        for i, kw in enumerate(exact_kws):
            if not isinstance(kw, str):
                errors.append(f"exact_title_keywords[{i}] 가 문자열이 아닙니다: {kw!r}")
                continue
            stripped = kw.strip()
            if not stripped:
                errors.append(f"exact_title_keywords[{i}] 가 빈 문자열입니다.")
            elif stripped in seen_exact:
                errors.append(f"exact_title_keywords[{i}] '{stripped}' 가 중복입니다.")
            elif stripped not in normalized_keywords:
                errors.append(
                    f"exact_title_keywords[{i}] '{stripped}' 가 keywords 에 없습니다."
                )
            else:
                seen_exact.add(stripped)

    for name, default, (low, high) in (
        ("window_days", DEFAULT_WINDOW_DAYS, WINDOW_DAYS_RANGE),
        ("row_page", DEFAULT_ROW_PAGE, ROW_PAGE_RANGE),
    ):
        value = raw.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{name} 가 정수가 아닙니다: {value!r}")
        elif not (low <= value <= high):
            errors.append(f"{name} 가 {value} 입니다. {low}~{high} 범위여야 합니다.")

    return errors


def _from_raw(raw: dict, source: str, warnings: list) -> KeywordConfig:
    return KeywordConfig(
        keywords=tuple(k.strip() for k in raw["keywords"]),
        exact_title_keywords=tuple(
            k.strip() for k in raw.get("exact_title_keywords", [])
        ),
        window_days=int(raw.get("window_days", DEFAULT_WINDOW_DAYS)),
        row_page=int(raw.get("row_page", DEFAULT_ROW_PAGE)),
        source=source,
        warnings=tuple(warnings),
    )


def load_keywords(path: Path = None) -> KeywordConfig:
    """설정을 읽는다. 실패해도 예외 없이 기본값 + 경고로 되돌린다."""
    target = Path(path) if path else get_keywords_file()

    if not target.exists():
        return KeywordConfig(
            source="default",
            warnings=(f"키워드 설정 파일이 없어 기본값을 사용합니다: {target}",),
        )

    try:
        # utf-8-sig 로 읽어 BOM 을 흡수한다. 사람이 손으로 편집하는 파일이고
        # 메모장·PowerShell Out-File 은 BOM 을 붙인다. utf-8 로 읽으면 BOM 때문에
        # 설정이 조용히 무시되고 기본 키워드로 되돌아간다.
        raw = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        return KeywordConfig(
            source="default",
            warnings=(f"키워드 설정을 읽을 수 없어 기본값을 사용합니다 ({target}): {e}",),
        )

    errors = validate(raw)
    if errors:
        return KeywordConfig(
            source="default",
            warnings=tuple(
                [f"키워드 설정이 유효하지 않아 기본값을 사용합니다: {target}"] + errors
            ),
        )

    return _from_raw(raw, str(target), [])


def validate_file(path: Path) -> list:
    """CI 검증용. 파일 부재·JSON 오류도 오류로 취급한다."""
    target = Path(path)
    if not target.exists():
        return [f"파일이 없습니다: {target}"]
    try:
        # utf-8-sig 로 읽어 BOM 을 흡수한다. 사람이 손으로 편집하는 파일이고
        # 메모장·PowerShell Out-File 은 BOM 을 붙인다. utf-8 로 읽으면 BOM 때문에
        # 설정이 조용히 무시되고 기본 키워드로 되돌아간다.
        raw = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"JSON 을 읽을 수 없습니다 ({target}): {e}"]
    return validate(raw)


def main(argv: list = None) -> int:
    # 키워드와 오류 메시지가 한글이다. 콘솔이 cp1252 인 CI 러너에서도 죽지 않게.
    ensure_utf8_stdout()

    argv = sys.argv[1:] if argv is None else argv
    target = Path(argv[0]) if argv else Path(__file__).resolve().parent / "config" / "keywords.json"

    errors = validate_file(target)
    if errors:
        print(f"[FAIL] 키워드 설정 검증 실패: {target}")
        for e in errors:
            print(f"  - {e}")
        return 1

    cfg = load_keywords(target)
    print(f"[OK] 키워드 설정 검증 통과: {target}")
    print(f"  키워드 {len(cfg.keywords)}개: {', '.join(cfg.keywords)}")
    if cfg.exact_title_keywords:
        print(f"  제목 연속일치: {', '.join(cfg.exact_title_keywords)}")
    print(f"  조회 기간 {cfg.window_days}일 / 페이지 크기 {cfg.row_page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
