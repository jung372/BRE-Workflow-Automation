import importlib
import os
import unittest

from tests import context  # noqa: F401

import config


class ProxyConfigTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("HTTP_PROXY_KR")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("HTTP_PROXY_KR", None)
        else:
            os.environ["HTTP_PROXY_KR"] = self._saved

    def test_returns_none_when_unset(self):
        """프록시 미설정 시 직접 접속 경로를 타야 한다."""
        os.environ.pop("HTTP_PROXY_KR", None)
        self.assertIsNone(config.playwright_proxy())
        self.assertIsNone(config.requests_proxies())

    def test_blank_value_is_treated_as_unset(self):
        os.environ["HTTP_PROXY_KR"] = "   "
        self.assertIsNone(config.playwright_proxy())
        self.assertIsNone(config.requests_proxies())

    def test_parses_host_and_port(self):
        os.environ["HTTP_PROXY_KR"] = "http://proxy.example.com:3128"
        self.assertEqual(
            config.playwright_proxy(), {"server": "http://proxy.example.com:3128"}
        )

    def test_omits_port_when_absent(self):
        os.environ["HTTP_PROXY_KR"] = "http://proxy.example.com"
        self.assertEqual(
            config.playwright_proxy(), {"server": "http://proxy.example.com"}
        )

    def test_extracts_credentials_out_of_server_url(self):
        """Playwright 는 자격증명을 server 문자열이 아니라 별도 키로 받는다."""
        os.environ["HTTP_PROXY_KR"] = "http://user:pw@proxy.example.com:3128"
        proxy = config.playwright_proxy()

        self.assertEqual(proxy["server"], "http://proxy.example.com:3128")
        self.assertEqual(proxy["username"], "user")
        self.assertEqual(proxy["password"], "pw")

    def test_requests_proxies_passes_raw_url_for_both_schemes(self):
        raw = "http://user:pw@proxy.example.com:3128"
        os.environ["HTTP_PROXY_KR"] = raw
        self.assertEqual(config.requests_proxies(), {"http": raw, "https": raw})


class SitesTest(unittest.TestCase):
    def test_site_ids_are_unique(self):
        ids = [s["id"] for s in config.SITES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_site_has_dashboard_fields(self):
        for site in config.SITES:
            with self.subTest(site=site.get("id")):
                for key in ("id", "name", "icon", "color", "url"):
                    self.assertIn(key, site)
                    self.assertTrue(site[key], f"{key} 가 비어 있음")

    def test_generic_sites_declare_column_indexes(self):
        """type 이 없는 사이트는 general 파서가 컬럼 인덱스를 요구한다."""
        for site in config.SITES:
            if site.get("type"):
                continue
            with self.subTest(site=site["id"]):
                for key in ("title_idx", "date_idx", "num_idx"):
                    self.assertIn(key, site)

    def test_only_geo_blocked_domains_use_proxy(self):
        """프록시는 해외 IP를 차단하는 .go.kr/.re.kr 에만 적용한다."""
        for site in config.SITES:
            if site.get("proxy"):
                with self.subTest(site=site["id"]):
                    self.assertRegex(site["url"], r"https://[^/]*\.(go|re)\.kr")

    def test_metmasts_declare_env_prefix(self):
        prefixes = [m["env_prefix"] for m in config.METMASTS]
        self.assertEqual(len(prefixes), len(set(prefixes)))
        for metmast in config.METMASTS:
            with self.subTest(metmast=metmast["id"]):
                self.assertTrue(metmast["env_prefix"].startswith("METMAST_"))


class GotoTimeoutTest(unittest.TestCase):
    def test_default_and_override(self):
        saved = os.environ.get("GOTO_TIMEOUT_MS")
        try:
            os.environ.pop("GOTO_TIMEOUT_MS", None)
            self.assertEqual(importlib.reload(config).GOTO_TIMEOUT, 40000)

            os.environ["GOTO_TIMEOUT_MS"] = "75000"
            self.assertEqual(importlib.reload(config).GOTO_TIMEOUT, 75000)
        finally:
            if saved is None:
                os.environ.pop("GOTO_TIMEOUT_MS", None)
            else:
                os.environ["GOTO_TIMEOUT_MS"] = saved
            importlib.reload(config)


if __name__ == "__main__":
    unittest.main()
