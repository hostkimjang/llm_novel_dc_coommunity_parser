"""Slang DB 화면 API(`/api/slang-db`)의 표현 계약을 저장 파일 단위로 고정한다.

임시 slang_db JSON과 ASGI transport만 사용하며 실제 중앙 DB·포트·외부 호출은 쓰지 않는다.
정렬, term 첫 순서와 중복 제거, pending kind 기본값, family alias 제목 일치, 예시 절편,
전체 기준 summary와 페이지 절편, 비어 있거나 깨진 파일의 빈 응답을 확인한다.
dict가 아닌 title bucket처럼 현재 예외가 나는 입력은 개선 대상이 아니므로 다루지 않는다.
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import llm_batch.monitor.server as server_module


FIXTURE = {
    "updated_at": "2026-10-16T00:00:00",
    "titles": {
        "나 혼자만 레벨업": {
            "slang": ["나혼렙", {"term": "나혼렙"}, {"term": " 혼렙 "}, {"term": ""}, None],
            "pending": [
                {"term": "나렙", "pending_kind": "alias"},
                {"term": "나렙", "pending_kind": ""},
                "솔로렙",
                {"term": "엑스"},
            ],
            "conflicts": [{"term": "레벨업"}],
            "examples": [
                {"post_id": 1, "alias": "나혼렙", "bucket": "slang", "extra": "dropped"},
                "not-a-dict",
                {"post_id": 3, "pending_kind": "alias"},
                {"post_id": 4},
            ],
        },
        "가": {"slang": [], "pending": [], "examples": []},
        "Zeta": {"slang": [{"term": "제타"}]},
    },
    "family_aliases": {
        "회귀물": {"titles": ["나 혼자만 레벨업", "다른 작품"]},
        "k2": {"term": "레벨업물", "titles": [" 나 혼자만 레벨업 "]},
        "k3": {"term": "회귀물", "titles": ["나 혼자만 레벨업"]},
        "bad": "not-a-dict",
        "k4": {"term": "무관", "titles": ["가"]},
    },
}

EMPTY_SUMMARY = {
    "titles_with_slang": 0,
    "titles_with_pending": 0,
    "titles_with_conflicts": 0,
    "titles_with_family_aliases": 0,
}


def _preview(**values):
    keys = ("post_id", "alias", "bucket", "source_role", "discussion_type", "work_resolution",
            "pending_kind", "classification_confidence", "created_at")
    return {key: values.get(key) for key in keys}


EXPECTED_ROWS = [
    {
        "title": "Zeta",
        "slang_terms": ["제타"], "slang_count": 1,
        "pending_terms": [], "pending_count": 0, "pending_kind_counts": {},
        "conflict_terms": [], "conflict_count": 0,
        "family_alias_terms": [], "family_alias_count": 0,
        "example_preview": [], "example_count": 0,
    },
    {
        "title": "가",
        "slang_terms": [], "slang_count": 0,
        "pending_terms": [], "pending_count": 0, "pending_kind_counts": {},
        "conflict_terms": [], "conflict_count": 0,
        "family_alias_terms": ["무관"], "family_alias_count": 1,
        "example_preview": [], "example_count": 0,
    },
    {
        "title": "나 혼자만 레벨업",
        "slang_terms": ["나혼렙", "혼렙"], "slang_count": 2,
        "pending_terms": ["나렙", "솔로렙", "엑스"], "pending_count": 3,
        "pending_kind_counts": {"alias": 1, "unknown": 2},
        "conflict_terms": ["레벨업"], "conflict_count": 1,
        "family_alias_terms": ["회귀물", "레벨업물"], "family_alias_count": 2,
        # 앞 3개 위치를 자른 뒤 dict만 남긴다. example_count는 원래 전체 수다.
        "example_preview": [
            _preview(post_id=1, alias="나혼렙", bucket="slang"),
            _preview(post_id=3, pending_kind="alias"),
        ],
        "example_count": 4,
    },
]

FULL_SUMMARY = {
    "titles_with_slang": 2,
    "titles_with_pending": 1,
    "titles_with_conflicts": 1,
    "titles_with_family_aliases": 2,
}


class SlangDbViewApiTest(unittest.IsolatedAsyncioTestCase):
    async def _get(self, path, params=None):
        transport = httpx.ASGITransport(app=server_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://dashboard.test") as client:
            response = await client.get("/api/slang-db", params=params or {})
        self.assertEqual(response.status_code, 200)
        return response.json()

    async def _request_with_file(self, content, params=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "slang_db.json"
            if content is not None:
                path.write_bytes(content)
            before = path.read_bytes() if path.exists() else None
            with patch.object(server_module, "_SLANG_DB_PATH", path):
                payload = await self._get("/api/slang-db", params)
            after = path.read_bytes() if path.exists() else None
            self.assertEqual(before, after)  # 조회는 파일을 바꾸지 않는다.
            return payload

    async def test_rows_are_sorted_deduplicated_and_summarised(self):
        raw = json.dumps(FIXTURE, ensure_ascii=False).encode("utf-8")
        payload = await self._request_with_file(raw)
        self.assertEqual(payload["items"], EXPECTED_ROWS)
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["offset"], 0)
        self.assertEqual(payload["limit"], 100)
        self.assertEqual(payload["updated_at"], "2026-10-16T00:00:00")
        self.assertEqual(payload["summary"], FULL_SUMMARY)

    async def test_page_slice_keeps_full_summary_and_total(self):
        raw = json.dumps(FIXTURE, ensure_ascii=False).encode("utf-8")
        payload = await self._request_with_file(raw, {"offset": 1, "limit": 1})
        self.assertEqual(payload["items"], EXPECTED_ROWS[1:2])
        self.assertEqual(payload["total"], 3)
        self.assertEqual((payload["offset"], payload["limit"]), (1, 1))
        self.assertEqual(payload["summary"], FULL_SUMMARY)

        beyond = await self._request_with_file(raw, {"offset": 5, "limit": 2})
        self.assertEqual(beyond["items"], [])
        self.assertEqual(beyond["total"], 3)
        self.assertEqual(beyond["summary"], FULL_SUMMARY)

    async def test_missing_broken_or_non_object_file_returns_empty_payload(self):
        expected = {"items": [], "total": 0, "offset": 0, "limit": 100,
                    "updated_at": None, "summary": EMPTY_SUMMARY}
        for name, content in (
            ("missing", None),
            ("broken", b"{not json"),
            ("list", b"[1, 2]"),
            ("titles_not_object", json.dumps({"updated_at": "u", "titles": [1]}).encode("utf-8")),
        ):
            with self.subTest(name=name):
                payload = await self._request_with_file(content)
                if name == "titles_not_object":
                    self.assertEqual(payload, {**expected, "updated_at": "u"})
                else:
                    self.assertEqual(payload, expected)


if __name__ == "__main__":
    unittest.main()
