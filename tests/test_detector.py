import unittest
from datetime import date, datetime, timedelta

from tests import context  # noqa: F401

from logic.detector import get_new_items, prev_weekday
from state import KST

SITE_DISPLAY = {"notice": "전기위 공지사항", "result": "위원회 개최결과"}


class PrevWeekdayTest(unittest.TestCase):
    def test_monday_goes_back_to_friday(self):
        monday = date(2026, 8, 3)
        self.assertEqual(monday.weekday(), 0)
        self.assertEqual(prev_weekday(monday), date(2026, 7, 31))

    def test_other_days_go_back_one_day(self):
        for day in (date(2026, 8, 4), date(2026, 8, 6), date(2026, 8, 8)):
            self.assertEqual(prev_weekday(day), day - timedelta(days=1))


class GetNewItemsTest(unittest.TestCase):
    def setUp(self):
        today = datetime.now(KST).date()
        self.today_key = today.strftime("%Y-%m-%d") + " 08"
        self.prev_key = prev_weekday(today).strftime("%Y-%m-%d") + " 08"

    def _state(self, prev_items, today_items, site_id="notice"):
        return {
            site_id: {
                "hourly_snapshots": {
                    self.prev_key: prev_items,
                    self.today_key: today_items,
                }
            }
        }

    def test_returns_items_absent_from_previous_snapshot(self):
        state = self._state(
            prev_items=[{"id": "a", "title": "기존", "date": "2026-08-05", "url": "u1"}],
            today_items=[
                {"id": "a", "title": "기존", "date": "2026-08-05", "url": "u1"},
                {"id": "b", "title": "신규", "date": "2026-08-06", "url": "u2"},
            ],
        )

        new_items, today_key, prev_key = get_new_items(state, SITE_DISPLAY)

        self.assertEqual(today_key, self.today_key)
        self.assertEqual(prev_key, self.prev_key)
        self.assertEqual(len(new_items), 1)
        self.assertEqual(new_items[0]["title"], "신규")
        self.assertEqual(new_items[0]["url"], "u2")

    def test_maps_site_id_to_display_name(self):
        state = self._state([], [{"id": "b", "title": "신규", "date": "", "url": "u"}])
        new_items, _, _ = get_new_items(state, SITE_DISPLAY)
        self.assertEqual(new_items[0]["site_name"], "전기위 공지사항")

    def test_unknown_site_id_falls_back_to_raw_id(self):
        state = self._state(
            [], [{"id": "b", "title": "신규", "date": "", "url": "u"}], site_id="mystery"
        )
        new_items, _, _ = get_new_items(state, SITE_DISPLAY)
        self.assertEqual(new_items[0]["site_name"], "mystery")

    def test_missing_today_snapshot_yields_nothing(self):
        """서버가 08시에 꺼져 있었으면 신규 0건으로 보고되어야 한다."""
        state = {"notice": {"hourly_snapshots": {self.prev_key: [{"id": "a"}]}}}
        new_items, _, _ = get_new_items(state, SITE_DISPLAY)
        self.assertEqual(new_items, [])

    def test_missing_previous_snapshot_reports_all_of_today(self):
        state = {
            "notice": {
                "hourly_snapshots": {
                    self.today_key: [
                        {"id": "a", "title": "1", "date": "", "url": "u"},
                        {"id": "b", "title": "2", "date": "", "url": "u"},
                    ]
                }
            }
        }
        new_items, _, _ = get_new_items(state, SITE_DISPLAY)
        self.assertEqual(len(new_items), 2)

    def test_legacy_list_site_state_is_skipped(self):
        state = {"notice": ["legacy", "format"]}
        new_items, _, _ = get_new_items(state, SITE_DISPLAY)
        self.assertEqual(new_items, [])

    def test_aggregates_across_sites(self):
        state = {
            "notice": {
                "hourly_snapshots": {
                    self.prev_key: [],
                    self.today_key: [{"id": "a", "title": "A", "date": "", "url": "u"}],
                }
            },
            "result": {
                "hourly_snapshots": {
                    self.prev_key: [],
                    self.today_key: [{"id": "b", "title": "B", "date": "", "url": "u"}],
                }
            },
        }
        new_items, _, _ = get_new_items(state, SITE_DISPLAY)
        self.assertEqual({i["site_name"] for i in new_items},
                         {"전기위 공지사항", "위원회 개최결과"})

    def test_missing_optional_fields_default_safely(self):
        state = self._state([], [{"id": "b"}])
        new_items, _, _ = get_new_items(state, SITE_DISPLAY)
        self.assertEqual(new_items[0]["title"], "")
        self.assertEqual(new_items[0]["url"], "#")


if __name__ == "__main__":
    unittest.main()
