from __future__ import annotations

import unittest

from tools.audit_runtime_expected_titles import audit_runtime_expected_titles


def _row(
    post_id: int,
    *,
    title: str | None,
    safe_resolved: bool,
    status: str,
    publish_allowed: bool,
) -> dict:
    return {
        "post_id": post_id,
        "analysis_result": {
            "safe_resolved": safe_resolved,
            "candidate_ledger_status": "safe_resolved" if status == "publish" else "promotion_blocked",
            "identity": {
                "post_id": post_id,
                "novel_identity": {"official_title": title} if title else None,
                "promotion_decision": {
                    "status": status,
                    "publish_allowed": publish_allowed,
                    "official_title": title if publish_allowed else None,
                    "reason_codes": [
                        "serialized_public_identity_published"
                        if publish_allowed
                        else "serialized_public_identity_scrubbed"
                    ],
                },
                "publish_ledger": {
                    "public_publish": {
                        "official_title": title if publish_allowed else None,
                        "candidate_ledger_status": "safe_resolved"
                        if publish_allowed
                        else "promotion_blocked",
                    }
                },
            },
        },
    }


class RuntimeExpectedTitleAuditTest(unittest.TestCase):
    def test_classifies_exact_blocked_variant_and_missing_rows(self) -> None:
        manifest = {
            "post_ids": [1, 2, 3, 4],
            "expected_titles": ["월야의 여인들", "퇴마록", "인간실격", "미완료"],
        }
        result_rows = [
            _row(1, title="월야의 여인들", safe_resolved=True, status="publish", publish_allowed=True),
            _row(2, title="퇴마록", safe_resolved=False, status="candidate_only", publish_allowed=False),
            _row(3, title="인간 실격", safe_resolved=True, status="publish", publish_allowed=True),
        ]

        audit = audit_runtime_expected_titles(
            input_manifest=manifest,
            result_rows=result_rows,
            runtime_manifest={"run_id": "unit", "completed_count": 3},
            generated_at="2026-07-07T00:00:00+09:00",
        )

        self.assertEqual(audit["gate"], "NO-GO")
        self.assertEqual(audit["summary"]["row_count"], 4)
        self.assertEqual(audit["summary"]["exact_safe_resolved_pass"], 1)
        self.assertEqual(
            audit["summary"]["status_counts"],
            {
                "FAIL_MISSING_RUNTIME_ROW": 1,
                "FAIL_RUNTIME_PROMOTION_BLOCKED": 1,
                "FAIL_VARIANT_COMPACT_MATCH_ONLY": 1,
                "PASS_EXACT_SAFE_RESOLVED": 1,
            },
        )
        self.assertEqual(audit["rows"][0]["audit_status"], "PASS_EXACT_SAFE_RESOLVED")
        self.assertEqual(audit["rows"][1]["audit_status"], "FAIL_RUNTIME_PROMOTION_BLOCKED")
        self.assertEqual(audit["rows"][2]["audit_status"], "FAIL_VARIANT_COMPACT_MATCH_ONLY")
        self.assertEqual(audit["rows"][3]["audit_status"], "FAIL_MISSING_RUNTIME_ROW")


if __name__ == "__main__":
    unittest.main()
