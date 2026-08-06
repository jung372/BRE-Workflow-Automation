import unittest

from tests import context  # noqa: F401

from scrapers.open_portal import (
    dedupe,
    extract_dept,
    normalize,
    search_url,
    to_iso_date,
)

# 2026-08-06 open.go.kr infoList.ajax 실측 응답에서 가져온 레코드
REAL_RECORD = {
    "ALL_PROC_INSTT_NM": "경상북도 경주시",
    "CHARGER_NM": "홍길동",
    "CHRG_DEPT_NM": "도시계획과",
    "DOC_NO": "도시계획과-13792",
    "FILE_NM": "[본문] 회신.pdf",
    "INFO_SJ": "전기사업 허가 신청에 따른 회신(경주시루풍력 2호)",
    "NFLST_CHRG_DEPT_NM": "경상북도 경주시 도시개발국 도시계획과",
    "P_DATE": "20260803",
    "PRDCTN_DT": "20260803171129",
    "PRDCTN_INSTT_REGIST_NO": "DCT1B2D6C2EA3A14C62BCFE3A87A4868CBB",
    "R_DATE": "20260804",
}


class ExtractDeptTest(unittest.TestCase):
    def test_prefers_chrg_dept_nm(self):
        self.assertEqual(extract_dept(REAL_RECORD), "도시계획과")

    def test_falls_back_to_last_token_of_full_path(self):
        """API 계층 구분자는 '>' 가 아니라 공백이다."""
        rec = {"NFLST_CHRG_DEPT_NM": "기후에너지환경부 자연보전국 환경영향평가과"}
        self.assertEqual(extract_dept(rec), "환경영향평가과")

    def test_institution_only_record(self):
        rec = {"CHRG_DEPT_NM": "한국에너지공단", "NFLST_CHRG_DEPT_NM": "한국에너지공단"}
        self.assertEqual(extract_dept(rec), "한국에너지공단")

    def test_blank_fields_yield_empty_string(self):
        self.assertEqual(extract_dept({}), "")
        self.assertEqual(extract_dept({"CHRG_DEPT_NM": "  ", "NFLST_CHRG_DEPT_NM": ""}), "")

    def test_none_values_do_not_raise(self):
        self.assertEqual(extract_dept({"CHRG_DEPT_NM": None, "NFLST_CHRG_DEPT_NM": None}), "")


class ToIsoDateTest(unittest.TestCase):
    def test_converts_yyyymmdd(self):
        self.assertEqual(to_iso_date("20260804"), "2026-08-04")

    def test_truncates_timestamp(self):
        self.assertEqual(to_iso_date("20260803171129"), "2026-08-03")

    def test_invalid_input_returns_empty(self):
        for bad in ("", None, "2026", "abcdefgh"):
            self.assertEqual(to_iso_date(bad), "")


class NormalizeTest(unittest.TestCase):
    def setUp(self):
        self.item = normalize(REAL_RECORD, "시루풍력")

    def test_maps_required_fields(self):
        self.assertEqual(self.item["title"], "전기사업 허가 신청에 따른 회신(경주시루풍력 2호)")
        self.assertEqual(self.item["dept"], "도시계획과")
        self.assertEqual(self.item["date"], "2026-08-04")
        self.assertEqual(self.item["prod_date"], "2026-08-03")
        self.assertEqual(self.item["keyword"], "시루풍력")
        self.assertEqual(self.item["uid"], REAL_RECORD["PRDCTN_INSTT_REGIST_NO"])

    def test_keeps_full_hierarchy_for_reference(self):
        self.assertEqual(self.item["dept_full"], "경상북도 경주시 도시개발국 도시계획과")
        self.assertEqual(self.item["instt"], "경상북도 경주시")

    def test_excludes_personal_information(self):
        """대시보드는 공개되므로 담당자 실명·첨부파일명을 발행하지 않는다."""
        self.assertNotIn("CHARGER_NM", self.item)
        self.assertNotIn("charger", self.item)
        self.assertNotIn("홍길동", str(self.item))
        self.assertNotIn("FILE_NM", self.item)
        self.assertNotIn("회신.pdf", str(self.item))

    def test_url_points_at_keyword_search(self):
        self.assertIn("uniSrhMoreList.do", self.item["url"])
        self.assertIn("kwd=", self.item["url"])

    def test_falls_back_to_composite_uid(self):
        rec = dict(REAL_RECORD)
        rec["PRDCTN_INSTT_REGIST_NO"] = ""
        item = normalize(rec, "시루풍력")
        self.assertTrue(item["uid"])
        self.assertIn("도시계획과-13792", item["uid"])

    def test_missing_fields_do_not_raise(self):
        item = normalize({}, "시루풍력")
        self.assertEqual(item["title"], "")
        self.assertEqual(item["dept"], "")
        self.assertEqual(item["date"], "")


class SearchUrlTest(unittest.TestCase):
    def test_encodes_korean_keyword(self):
        url = search_url("시루풍력")
        self.assertNotIn("시루풍력", url)
        self.assertIn("%EC%8B%9C%EB%A3%A8%ED%92%8D%EB%A0%A5", url)


class DedupeTest(unittest.TestCase):
    def _item(self, uid, date, keyword="시루풍력"):
        return {"uid": uid, "date": date, "keyword": keyword, "title": uid}

    def test_merges_same_document_from_two_keywords(self):
        items = dedupe([
            self._item("A", "2026-08-01", "시루풍력"),
            self._item("A", "2026-08-01", "왕신풍력"),
        ])
        self.assertEqual(len(items), 1)
        self.assertIn("시루풍력", items[0]["keyword"])
        self.assertIn("왕신풍력", items[0]["keyword"])

    def test_does_not_repeat_same_keyword(self):
        items = dedupe([
            self._item("A", "2026-08-01", "시루풍력"),
            self._item("A", "2026-08-01", "시루풍력"),
        ])
        self.assertEqual(items[0]["keyword"], "시루풍력")

    def test_sorts_newest_first(self):
        items = dedupe([
            self._item("A", "2026-08-01"),
            self._item("B", "2026-08-05"),
            self._item("C", "2026-07-20"),
        ])
        self.assertEqual([i["uid"] for i in items], ["B", "A", "C"])

    def test_empty_input(self):
        self.assertEqual(dedupe([]), [])


class StateIntegrationTest(unittest.TestCase):
    def test_item_id_uses_uid_for_open_portal_items(self):
        from state import item_id

        item = normalize(REAL_RECORD, "시루풍력")
        self.assertEqual(item_id(item), REAL_RECORD["PRDCTN_INSTT_REGIST_NO"])

    def test_item_id_unchanged_for_legacy_items(self):
        """기존 5개 사이트의 판정 결과가 바뀌면 안 된다."""
        from state import item_id

        legacy = {"title": "공고 제1호", "date": "2026-08-06", "comp_date": "", "status": ""}
        self.assertEqual(item_id(legacy), "공고 제1호||2026-08-06||||")

    def test_snapshot_entry_includes_dept_and_keyword(self):
        from state import _snapshot_entry

        entry = _snapshot_entry(normalize(REAL_RECORD, "시루풍력"))
        self.assertEqual(entry["dept"], "도시계획과")
        self.assertEqual(entry["keyword"], "시루풍력")

    def test_snapshot_entry_omits_empty_extras(self):
        """기존 사이트 항목에 빈 필드를 추가해 상태 파일을 키우지 않는다."""
        from state import _snapshot_entry

        entry = _snapshot_entry({"title": "공고", "date": "2026-08-06", "url": "u"})
        self.assertNotIn("dept", entry)
        self.assertNotIn("keyword", entry)


if __name__ == "__main__":
    unittest.main()
