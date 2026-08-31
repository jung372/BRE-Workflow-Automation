import contextlib
import importlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from tests import context  # noqa: F401

import keywords as kw_mod


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


VALID = {"keywords": ["시루풍력", "왕신풍력"], "window_days": 90, "row_page": 100}


class ValidateTest(unittest.TestCase):
    def test_valid_config_has_no_errors(self):
        self.assertEqual(kw_mod.validate(VALID), [])

    def test_defaults_are_allowed_to_be_absent(self):
        self.assertEqual(kw_mod.validate({"keywords": ["시루풍력"]}), [])

    def test_accepts_exact_title_keyword_from_keywords(self):
        raw = {
            "keywords": ["시루풍력", "한국바람"],
            "exact_title_keywords": ["한국바람"],
        }
        self.assertEqual(kw_mod.validate(raw), [])

    def test_rejects_exact_title_keyword_not_in_keywords(self):
        raw = {
            "keywords": ["시루풍력"],
            "exact_title_keywords": ["한국바람"],
        }
        errors = kw_mod.validate(raw)
        self.assertTrue(any("keywords 에 없습니다" in e for e in errors))

    def test_rejects_invalid_exact_title_keywords_type(self):
        raw = {
            "keywords": ["시루풍력"],
            "exact_title_keywords": "시루풍력",
        }
        self.assertTrue(kw_mod.validate(raw))

    def test_rejects_non_object(self):
        self.assertTrue(kw_mod.validate(["시루풍력"]))

    def test_rejects_missing_or_non_list_keywords(self):
        self.assertTrue(kw_mod.validate({}))
        self.assertTrue(kw_mod.validate({"keywords": "시루풍력"}))

    def test_rejects_empty_keywords(self):
        self.assertTrue(kw_mod.validate({"keywords": []}))

    def test_rejects_short_keyword(self):
        """2자 키워드는 무관한 결과가 만 건 넘게 잡히므로 막아야 한다."""
        errors = kw_mod.validate({"keywords": ["시루"]})
        self.assertTrue(any("짧습니다" in e for e in errors))

    def test_accepts_exactly_minimum_length(self):
        self.assertEqual(kw_mod.validate({"keywords": ["시루풍"]}), [])

    def test_rejects_duplicates(self):
        errors = kw_mod.validate({"keywords": ["시루풍력", "시루풍력"]})
        self.assertTrue(any("중복" in e for e in errors))

    def test_duplicate_detection_ignores_surrounding_space(self):
        errors = kw_mod.validate({"keywords": ["시루풍력", " 시루풍력 "]})
        self.assertTrue(any("중복" in e for e in errors))

    def test_rejects_blank_keyword(self):
        self.assertTrue(kw_mod.validate({"keywords": ["   "]}))

    def test_rejects_non_string_keyword(self):
        self.assertTrue(kw_mod.validate({"keywords": [123]}))

    def test_rejects_too_many_keywords(self):
        many = [f"키워드{i:03d}" for i in range(kw_mod.MAX_KEYWORDS + 1)]
        errors = kw_mod.validate({"keywords": many})
        self.assertTrue(any("최대" in e for e in errors))

    def test_accepts_exactly_max_keywords(self):
        many = [f"키워드{i:03d}" for i in range(kw_mod.MAX_KEYWORDS)]
        self.assertEqual(kw_mod.validate({"keywords": many}), [])

    def test_range_checks(self):
        low, high = kw_mod.WINDOW_DAYS_RANGE
        self.assertTrue(kw_mod.validate({"keywords": ["시루풍력"], "window_days": low - 1}))
        self.assertTrue(kw_mod.validate({"keywords": ["시루풍력"], "window_days": high + 1}))
        self.assertEqual(kw_mod.validate({"keywords": ["시루풍력"], "window_days": low}), [])

        low, high = kw_mod.ROW_PAGE_RANGE
        self.assertTrue(kw_mod.validate({"keywords": ["시루풍력"], "row_page": low - 1}))
        self.assertTrue(kw_mod.validate({"keywords": ["시루풍력"], "row_page": high + 1}))

    def test_rejects_bool_as_int(self):
        self.assertTrue(kw_mod.validate({"keywords": ["시루풍력"], "row_page": True}))


class LoadTest(unittest.TestCase):
    """런타임 로딩은 무슨 일이 있어도 예외를 던지지 않아야 한다."""

    def test_loads_valid_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keywords.json"
            write(p, VALID)
            cfg = kw_mod.load_keywords(p)

            self.assertEqual(cfg.keywords, ("시루풍력", "왕신풍력"))
            self.assertEqual(cfg.exact_title_keywords, ())
            self.assertEqual(cfg.window_days, 90)
            self.assertEqual(cfg.warnings, ())
            self.assertEqual(cfg.source, str(p))

    def test_loads_exact_title_keywords(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keywords.json"
            write(
                p,
                {
                    "keywords": ["시루풍력", "한국바람"],
                    "exact_title_keywords": ["한국바람"],
                },
            )
            cfg = kw_mod.load_keywords(p)

            self.assertEqual(cfg.exact_title_keywords, ("한국바람",))

    def test_strips_whitespace(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keywords.json"
            write(p, {"keywords": [" 시루풍력 "]})
            self.assertEqual(kw_mod.load_keywords(p).keywords, ("시루풍력",))

    def test_reads_file_with_utf8_bom(self):
        """메모장·PowerShell Out-File 은 BOM 을 붙인다. 무시되면 안 된다."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keywords.json"
            p.write_text(json.dumps(VALID, ensure_ascii=False), encoding="utf-8-sig")
            cfg = kw_mod.load_keywords(p)

            self.assertEqual(cfg.keywords, ("시루풍력", "왕신풍력"))
            self.assertEqual(cfg.warnings, ())

    def test_validate_file_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keywords.json"
            p.write_text(json.dumps(VALID, ensure_ascii=False), encoding="utf-8-sig")
            self.assertEqual(kw_mod.validate_file(p), [])

    def test_missing_file_falls_back_with_warning(self):
        cfg = kw_mod.load_keywords(Path(tempfile.gettempdir()) / "nope-does-not-exist.json")
        self.assertEqual(cfg.keywords, kw_mod.DEFAULT_KEYWORDS)
        self.assertTrue(cfg.warnings)

    def test_broken_json_falls_back_with_warning(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keywords.json"
            p.write_text("{ not json", encoding="utf-8")
            cfg = kw_mod.load_keywords(p)
            self.assertEqual(cfg.keywords, kw_mod.DEFAULT_KEYWORDS)
            self.assertTrue(cfg.warnings)

    def test_invalid_content_falls_back_with_warning(self):
        """잘못된 편집 한 번으로 수집이 멈추면 안 된다."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keywords.json"
            write(p, {"keywords": ["시루"]})
            cfg = kw_mod.load_keywords(p)
            self.assertEqual(cfg.keywords, kw_mod.DEFAULT_KEYWORDS)
            self.assertTrue(any("짧습니다" in w for w in cfg.warnings))


class PathResolutionTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("BRE_DATA_DIR")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("BRE_DATA_DIR", None)
        else:
            os.environ["BRE_DATA_DIR"] = self._saved
        importlib.reload(importlib.import_module("runtime_config"))

    def test_prefers_data_dir_copy(self):
        rc = importlib.import_module("runtime_config")
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "config" / "keywords.json"
            target.parent.mkdir(parents=True)
            write(target, VALID)
            os.environ["BRE_DATA_DIR"] = d
            importlib.reload(rc)
            # 경로 해석이 Windows 8.3 단축 경로를 장경로로 확장하므로 양쪽을 정규화한다.
            self.assertEqual(rc.get_keywords_file().resolve(), target.resolve())

    def test_falls_back_to_repo_copy_when_data_copy_absent(self):
        rc = importlib.import_module("runtime_config")
        with tempfile.TemporaryDirectory() as d:
            os.environ["BRE_DATA_DIR"] = d
            importlib.reload(rc)
            self.assertEqual(
                rc.get_keywords_file(), rc.PROJECT_ROOT / "config" / "keywords.json"
            )


class RepoConfigTest(unittest.TestCase):
    def test_shipped_config_is_valid(self):
        """저장소에 커밋된 기본 설정이 항상 검증을 통과해야 한다."""
        path = Path(__file__).resolve().parent.parent / "config" / "keywords.json"
        self.assertEqual(kw_mod.validate_file(path), [])

    def test_cli_returns_zero_for_shipped_config(self):
        path = Path(__file__).resolve().parent.parent / "config" / "keywords.json"
        self.assertEqual(kw_mod.main([str(path)]), 0)

    def test_cli_returns_one_for_invalid_config(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keywords.json"
            write(p, {"keywords": ["시루"]})
            self.assertEqual(kw_mod.main([str(p)]), 1)


class CliEncodingTest(unittest.TestCase):
    """콘솔이 한글을 못 담는 환경에서도 CLI 가 죽지 않아야 한다.

    GitHub windows-latest 러너의 stdout 은 cp1252 다. 키워드 값 자체가
    한글이므로 메시지를 ASCII 로 바꾸는 것으로는 해결되지 않는다.
    """

    @staticmethod
    @contextlib.contextmanager
    def cp1252_stdout():
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252", newline="")
        try:
            with contextlib.redirect_stdout(stream):
                yield buffer
        finally:
            # detach 하지 않으면 wrapper 소멸 시 buffer 까지 닫혀 getvalue 가 실패한다.
            stream.flush()
            stream.detach()

    def test_success_path_survives_cp1252_console(self):
        path = Path(__file__).resolve().parent.parent / "config" / "keywords.json"
        with self.cp1252_stdout() as buffer:
            code = kw_mod.main([str(path)])
        self.assertEqual(code, 0)
        self.assertIn("시루풍력", buffer.getvalue().decode("utf-8", errors="replace"))

    def test_failure_path_survives_cp1252_console(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "keywords.json"
            write(p, {"keywords": ["시루"]})
            with self.cp1252_stdout() as buffer:
                code = kw_mod.main([str(p)])
        self.assertEqual(code, 1)
        self.assertIn("짧습니다", buffer.getvalue().decode("utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main()
