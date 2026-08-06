import unittest
from datetime import datetime, timedelta

from tests import context  # noqa: F401

from state import (
    BASELINE_DAYS,
    KEEP_DAYS,
    KST,
    get_baseline_ids,
    item_id,
    update_site_state,
)


def _item(title, date, comp_date="", status=""):
    return {"title": title, "date": date, "comp_date": comp_date, "status": status}


class ItemIdTest(unittest.TestCase):
    def test_strips_new_suffix_so_same_post_keeps_one_id(self):
        """목록에 붙는 NEW 배지 때문에 같은 글이 신규로 오인되면 안 된다."""
        self.assertEqual(
            item_id(_item("공고 제2026-1호NEW", "2026-08-06")),
            item_id(_item("공고 제2026-1호", "2026-08-06")),
        )

    def test_trailing_whitespace_is_trimmed(self):
        self.assertEqual(
            item_id(_item("공고  NEW", "2026-08-06")),
            item_id(_item("공고", "2026-08-06")),
        )

    def test_new_only_inside_title_is_kept(self):
        """NEW 가 제목 끝이 아니면 제거 대상이 아니다."""
        self.assertNotEqual(
            item_id(_item("NEW 사업 공고", "2026-08-06")),
            item_id(_item("사업 공고", "2026-08-06")),
        )

    def test_id_includes_date_comp_date_and_status(self):
        base = item_id(_item("공고", "2026-08-06", "2026-08-10", "접수중"))
        self.assertNotEqual(base, item_id(_item("공고", "2026-08-07", "2026-08-10", "접수중")))
        self.assertNotEqual(base, item_id(_item("공고", "2026-08-06", "2026-08-11", "접수중")))
        self.assertNotEqual(base, item_id(_item("공고", "2026-08-06", "2026-08-10", "마감")))


class BaselineTest(unittest.TestCase):
    def setUp(self):
        self.today = datetime.now(KST).date()

    def _day(self, offset):
        return (self.today - timedelta(days=offset)).strftime("%Y-%m-%d")

    def test_no_snapshots_returns_empty_set(self):
        """첫 실행은 baseline 이 없어야 한다(전체를 신규로 보고하지 않도록)."""
        self.assertEqual(get_baseline_ids({}), set())
        self.assertEqual(get_baseline_ids({"daily_snapshots": {}}), set())

    def test_legacy_list_state_returns_empty_set(self):
        self.assertEqual(get_baseline_ids(["a", "b"]), set())

    def test_picks_snapshot_at_baseline_days_ago(self):
        state = {
            "daily_snapshots": {
                self._day(BASELINE_DAYS): ["old"],
                self._day(0): ["new"],
            }
        }
        self.assertEqual(get_baseline_ids(state), {"old"})

    def test_picks_latest_snapshot_not_newer_than_baseline(self):
        """정확히 5일 전이 없으면 그보다 오래된 것 중 가장 최신을 쓴다."""
        state = {
            "daily_snapshots": {
                self._day(BASELINE_DAYS + 3): ["oldest"],
                self._day(BASELINE_DAYS + 1): ["expected"],
                self._day(1): ["recent"],
            }
        }
        self.assertEqual(get_baseline_ids(state), {"expected"})

    def test_returns_empty_when_all_snapshots_are_newer_than_baseline(self):
        state = {"daily_snapshots": {self._day(1): ["recent"]}}
        self.assertEqual(get_baseline_ids(state), set())


class UpdateSiteStateTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(KST)
        self.today = self.now.strftime("%Y-%m-%d")
        self.hour = self.now.strftime("%Y-%m-%d %H")

    def test_records_today_and_current_hour(self):
        items = [_item("공고", "2026-08-06")]
        result = update_site_state({}, [item_id(items[0])], items)

        self.assertIn(self.today, result["daily_snapshots"])
        self.assertIn(self.hour, result["hourly_snapshots"])
        self.assertEqual(len(result["hourly_snapshots"][self.hour]), 1)

    def test_hourly_entry_keeps_fields_needed_by_teams_report(self):
        items = [{"title": "공고", "date": "2026-08-06", "url": "https://x/1"}]
        result = update_site_state({}, [item_id(items[0])], items)
        entry = result["hourly_snapshots"][self.hour][0]

        self.assertEqual(
            set(entry.keys()), {"id", "title", "date", "url"}
        )
        self.assertEqual(entry["url"], "https://x/1")

    def test_prunes_snapshots_older_than_keep_days(self):
        stale_day = (self.now - timedelta(days=KEEP_DAYS + 2)).strftime("%Y-%m-%d")
        stale_hour = (self.now - timedelta(days=KEEP_DAYS + 2)).strftime("%Y-%m-%d %H")
        site_state = {
            "daily_snapshots": {stale_day: ["x"]},
            "hourly_snapshots": {stale_hour: [{"id": "x"}]},
        }

        result = update_site_state(site_state, [], [])

        self.assertNotIn(stale_day, result["daily_snapshots"])
        self.assertNotIn(stale_hour, result["hourly_snapshots"])

    def test_keeps_snapshots_inside_retention_window(self):
        fresh_day = (self.now - timedelta(days=KEEP_DAYS - 1)).strftime("%Y-%m-%d")
        site_state = {"daily_snapshots": {fresh_day: ["x"]}}

        result = update_site_state(site_state, [], [])

        self.assertIn(fresh_day, result["daily_snapshots"])

    def test_legacy_list_state_is_replaced_with_dict(self):
        result = update_site_state(["legacy"], ["a"], [_item("공고", "2026-08-06")])
        self.assertIsInstance(result, dict)
        self.assertIn("daily_snapshots", result)

    def test_caps_stored_items_at_100(self):
        items = [_item(f"공고 {i}", "2026-08-06") for i in range(150)]
        ids = [item_id(i) for i in items]

        result = update_site_state({}, ids, items)

        self.assertEqual(len(result["daily_snapshots"][self.today]), 100)
        self.assertEqual(len(result["hourly_snapshots"][self.hour]), 100)

    def test_handles_none_current_items(self):
        result = update_site_state({}, [], None)
        self.assertEqual(result["hourly_snapshots"][self.hour], [])


if __name__ == "__main__":
    unittest.main()
