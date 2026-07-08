import unittest
from unittest import mock

from tools import audit_search_shards


def _ok_get(url: str, timeout: float):
    payload = {"status": "ok", "searxng": True} if url.endswith("/readyz") else {"status": "ok"}
    return {
        "ok": True,
        "status_code": 200,
        "latency_ms": 1.0,
        "payload": payload,
        "preview": "",
    }


def _ok_docker(name: str):
    return {"ok": True, "state": {"Running": True, "Status": "running"}}


class AuditSearchShardsTests(unittest.TestCase):
    def test_query_probe_blocks_forbidden_engine_even_with_results(self):
        def post_probe(url, payload, timeout):
            return {
                "ok": True,
                "status_code": 200,
                "latency_ms": 2.0,
                "payload": {
                    "results": [{"title": "재벌집 막내아들", "url": "https://novel.munpia.com/69583"}],
                    "total": 1,
                    "raw_total": 3,
                    "degraded": False,
                    "possible_throttle": False,
                    "engines": "google,bing,presearch,webcrawler,naver",
                    "unresponsive_engines": [["presearch", "액세스 거부"]],
                    "engine_errors": [],
                },
            }

        with mock.patch.object(audit_search_shards, "_probe", side_effect=_ok_get), mock.patch.object(
            audit_search_shards, "_docker_state", side_effect=_ok_docker
        ), mock.patch.object(audit_search_shards, "_post_json_probe", side_effect=post_probe):
            audit = audit_search_shards.build_audit(
                1,
                mcp_base_port=3333,
                search_ui_base_port=0,
                timeout=1.0,
                probe_query="재벌집 막내아들 웹소설",
                forbidden_engines=["presearch"],
            )

        self.assertEqual(audit["bad_count"], 1)
        self.assertEqual(audit["search_probe_summary"]["forbidden_engine_count"], 1)
        probe = audit["shards"][0]["search_probe"]
        self.assertFalse(probe["ok"])
        self.assertIn("search_probe_forbidden_engine", probe["reasons"])

    def test_query_probe_passes_clean_non_degraded_result(self):
        def post_probe(url, payload, timeout):
            return {
                "ok": True,
                "status_code": 200,
                "latency_ms": 2.0,
                "payload": {
                    "results": [{"title": "재벌집 막내아들", "url": "https://novel.munpia.com/69583"}],
                    "total": 1,
                    "raw_total": 3,
                    "degraded": False,
                    "possible_throttle": False,
                    "engines": "google,bing,webcrawler,naver",
                    "unresponsive_engines": [],
                    "engine_errors": [],
                },
            }

        with mock.patch.object(audit_search_shards, "_probe", side_effect=_ok_get), mock.patch.object(
            audit_search_shards, "_docker_state", side_effect=_ok_docker
        ), mock.patch.object(audit_search_shards, "_post_json_probe", side_effect=post_probe):
            audit = audit_search_shards.build_audit(
                1,
                mcp_base_port=3333,
                search_ui_base_port=0,
                timeout=1.0,
                probe_query="재벌집 막내아들 웹소설",
                forbidden_engines=["presearch"],
            )

        self.assertEqual(audit["bad_count"], 0)
        self.assertEqual(audit["search_probe_summary"]["ok_count"], 1)
        self.assertTrue(audit["shards"][0]["search_probe"]["ok"])


if __name__ == "__main__":
    unittest.main()
