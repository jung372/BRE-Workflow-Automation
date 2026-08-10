import unittest

from scrapers.kepco import normalize_notice_date


class NormalizeNoticeDateTests(unittest.TestCase):
    def test_removes_accessibility_label_from_date(self):
        self.assertEqual(
            normalize_notice_date("게시글 등록일 2026.06.29"),
            "2026.06.29",
        )

    def test_keeps_existing_date_format(self):
        self.assertEqual(normalize_notice_date("2025.11.03"), "2025.11.03")

    def test_normalizes_supported_separators_and_padding(self):
        self.assertEqual(normalize_notice_date("등록일 2026-6-9"), "2026.06.09")

    def test_preserves_unrecognized_text_for_diagnostics(self):
        self.assertEqual(normalize_notice_date("등록일 미상"), "등록일 미상")


if __name__ == "__main__":
    unittest.main()
