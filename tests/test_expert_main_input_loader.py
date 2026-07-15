import io
import json
import hashlib
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import expert_main as expert_main_module
PublicationCommitError = expert_main_module.PublicationCommitError
from expert_main import (
    _allow_local_shard_auto_up,
    _allow_local_shard_recreate,
    _allow_missing_shard_auto_scale_up,
    _apply_reuse_only_healthy_endpoint_filter,
    _assert_fresh_output_attempt,
    _build_decision_call_measurement_gate,
    _build_runtime_completion_gate,
    _build_completed_subset_rows,
    _can_auto_manage_local_shards,
    _configure_mcp_endpoints,
    _count_image_posts,
    _count_nonempty_jsonl_lines,
    _create_output_attempt_claim,
    _default_mcp_health_include_search,
    _decision_env_key_is_secret,
    _effective_parallel_for_post_count,
    _env_toggle_enabled,
    _env_shard_lifecycle_blocked_by_context,
    _healthy_endpoint_filter_reason,
    _mcp_goal_run_light_health_mode,
    _mcp_health_probe_batch_size,
    _mcp_health_required_ok_count,
    _fresh_execution_authoritative_reference_for_row,
    _large_run_complete_from_gates,
    _publication_decision_environment,
    _post_has_image_block,
    _public_comment_context_lines,
    _public_comment_dialogue_context_lines,
    _public_comment_metadata,
    _runtime_binding_echo_fields,
    _require_fresh_execution_authoritative_references,
    _small_run_shard_lifecycle_blocked,
    load_jsonl_posts,
)


class ExpertMainInputLoaderTest(unittest.TestCase):
    def test_loader_and_line_count_use_one_immutable_input_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.jsonl"
            original = (
                json.dumps(
                    {
                        "post_id": 101,
                        "title": "snapshot title",
                        "content": ["snapshot body"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8")
            path.write_bytes(original)
            snapshot = path.read_bytes()
            path.write_text(
                json.dumps(
                    {"post_id": 999, "title": "changed", "content": ["changed"]},
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            posts = load_jsonl_posts(path, snapshot_bytes=snapshot)
            count = _count_nonempty_jsonl_lines(path, snapshot_bytes=snapshot)

            self.assertEqual(count, 1)
            self.assertEqual([post.post_id for post in posts], [101])
            self.assertEqual(posts[0].title, "snapshot title")

    def test_decision_env_secret_filter_keeps_token_budgets_in_scope(self):
        self.assertFalse(_decision_env_key_is_secret("LLM_MAX_TOKENS"))
        self.assertFalse(_decision_env_key_is_secret("LLM_CONTEXT_LIMIT_TOKENS"))
        self.assertFalse(
            _decision_env_key_is_secret("LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS")
        )
        self.assertTrue(_decision_env_key_is_secret("LLM_API_KEY"))
        self.assertTrue(_decision_env_key_is_secret("LLM_ACCESS_TOKEN"))
        self.assertTrue(_decision_env_key_is_secret("PIPELINE_PASSWORD"))

    def test_existing_output_attempt_is_refused_without_truncation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "result.json"
            checkpoint = Path(tmpdir) / "result_checkpoint.jsonl"
            checkpoint.write_text("durable evidence\n", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "덮어쓰지 않습니다"):
                _assert_fresh_output_attempt([output, checkpoint])

            self.assertFalse(output.exists())
            self.assertEqual(
                checkpoint.read_text(encoding="utf-8"),
                "durable evidence\n",
            )

    def test_output_attempt_claim_is_exclusive_and_immutable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            claim = Path(tmpdir) / "result_attempt_claim.json"
            first_hash = _create_output_attempt_claim(
                claim,
                {"schema_version": "expert_output_attempt_claim_v1", "run_id": "first"},
            )
            first_bytes = claim.read_bytes()

            with self.assertRaises(FileExistsError):
                _create_output_attempt_claim(
                    claim,
                    {"schema_version": "expert_output_attempt_claim_v1", "run_id": "second"},
                )

            self.assertEqual(claim.read_bytes(), first_bytes)
            import hashlib

            self.assertEqual(first_hash, hashlib.sha256(first_bytes).hexdigest())

    def test_p2_attempt_sidecars_use_durable_write_helpers(self):
        source = Path(expert_main_module.__file__).read_text(encoding="utf-8")
        for name in (
            "checkpoint_jsonl_path",
            "pending_snapshot_path",
            "completed_subset_path",
            "completed_subset_manifest_path",
            "result_manifest_path",
            "out_result_path",
        ):
            self.assertNotIn(f"{name}.write_text(", source)
        self.assertNotIn('checkpoint_jsonl_path.open("a"', source)
        self.assertIn("_append_jsonl_fsync(checkpoint_jsonl_path", source)
        self.assertIn("_atomic_write_json(result_manifest_path", source)
        self.assertIn("_atomic_write_json(out_result_path", source)

    def test_publication_scope_binds_decision_environment_and_full_config_hash(self):
        source = Path(expert_main_module.__file__).read_text(encoding="utf-8")
        for fragment in (
            '"vlm_enabled": vlm_enabled',
            '"ocr_enabled": ocr_enabled',
            '"slang_db_path": str(_scope_slang_db_path)',
            '"slang_db_input_sha256": _scope_slang_db_sha256',
            '"decision_environment_sha256": _decision_environment_sha256',
            "publication_scope_descriptor = build_publication_scope_descriptor(",
            "config_hash=_publication_config_hash",
            '"publication_input_snapshot_sha256": _input_snapshot_sha256',
            '"schema_version": "publication_scope_config_v1"',
            '"decision_environment": _decision_environment',
            '"publication_scope_config_sha256"',
            '"publication_release_attestation_status"',
            '"publication_commit_tail_repair_ledger_sha256"',
        ):
            self.assertIn(fragment, source)
        self.assertLess(
            source.index("_run_config_payload.update("),
            source.index("_publication_config_hash = hashlib.sha256("),
        )

    def test_actual_environment_path_excludes_measurement_keys_from_publication_scope(self):
        base = {
            "LLM_MODEL": "decision-model-a",
            "PIPELINE_REASON_FULL_MODE": "1",
            "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
            "PIPELINE_DECISION_CALL_PAIR_ID": "pair-before",
            "PIPELINE_DECISION_CALL_ARM": "BEFORE",
            "PIPELINE_DECISION_CALL_RUN_SPEC_SHA256": "a" * 64,
            "PIPELINE_DECISION_CALL_EXECUTION_SOURCE": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
            "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "a" * 64,
            "PIPELINE_MEASUREMENT_PAIR_ID": "pair-before",
            "PIPELINE_MEASUREMENT_ARM": "BEFORE",
            "PIPELINE_MEASUREMENT_EXECUTION_MODE": "FRESH_EXECUTION_REQUIRED",
        }
        changed_measurement = {
            **base,
            "PIPELINE_DECISION_CALL_PAIR_ID": "pair-after",
            "PIPELINE_DECISION_CALL_ARM": "AFTER",
            "PIPELINE_DECISION_CALL_RUN_SPEC_SHA256": "b" * 64,
            "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "b" * 64,
            "PIPELINE_MEASUREMENT_PAIR_ID": "pair-after",
            "PIPELINE_MEASUREMENT_ARM": "AFTER",
        }
        with patch.dict(os.environ, base, clear=True):
            before = _publication_decision_environment()
        with patch.dict(os.environ, changed_measurement, clear=True):
            after = _publication_decision_environment()

        def digest(value):
            return hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

        self.assertEqual(before, after)
        self.assertEqual(digest(before), digest(after))
        self.assertEqual(before["LLM_MODEL"], "decision-model-a")
        self.assertEqual(before["PIPELINE_REASON_FULL_MODE"], "1")
        self.assertFalse(
            any(key.startswith("PIPELINE_DECISION_CALL_") for key in before)
        )
        self.assertFalse(any(key.startswith("PIPELINE_MEASUREMENT_") for key in before))
        with patch.dict(
            os.environ,
            {**changed_measurement, "LLM_MODEL": "decision-model-b"},
            clear=True,
        ):
            changed_decision = _publication_decision_environment()
        self.assertNotEqual(digest(before), digest(changed_decision))

    def test_fresh_execution_rejects_empty_and_partial_wal_reference_sets(self):
        source = Path(expert_main_module.__file__).read_text(encoding="utf-8")
        fresh_mode = source.index('if _decision_call_measurement["fresh_execution_required"]:')
        preflight = source.index(
            "_require_fresh_execution_authoritative_references(",
            fresh_mode,
        )
        disable_replay = source.index("_publication_replay_by_index = {}", preflight)
        self.assertLess(preflight, disable_replay)
        self.assertLess(disable_replay, source.index("def _process_one(", fresh_mode))
        with self.assertRaisesRegex(
            PublicationCommitError,
            "FRESH_EXECUTION_NO_PUBLIC_WRITE requires an authoritative WAL",
        ):
            _require_fresh_execution_authoritative_references(
                {},
                post_ids=[101, 102],
            )

        authoritative_receipt = object()
        references = {1: ({"post_id": 101}, authoritative_receipt)}
        self.assertIs(
            _fresh_execution_authoritative_reference_for_row(
                references,
                input_index=1,
                post_id=101,
            )[1],
            authoritative_receipt,
        )
        with self.assertRaisesRegex(PublicationCommitError, "missing=2:102"):
            _require_fresh_execution_authoritative_references(
                references,
                post_ids=[101, 102],
            )

    def test_required_measurement_failures_block_large_run_completion(self):
        source = Path(expert_main_module.__file__).read_text(encoding="utf-8")
        self.assertIn('"writer_complete": writer_complete', source)
        self.assertIn('"NOT_LINKABLE_WRITER_INCOMPLETE"', source)
        required = {"mode": "REQUIRED", "actual_kpi_eligible": True}
        complete_summary = {
            "instrumentation_status": "ENABLED",
            "ledger_status": "COMPLETE",
            "actual_kpi_status": "PENDING_INDEPENDENT_READBACK",
            "reason_codes": [],
        }
        linked_entry = {
            "ledger_ref": {"closure_kind": "ROW_SEAL"},
            "row_summary": {
                "writer_complete": True,
                "actual_kpi_status": "PENDING_INDEPENDENT_READBACK",
            },
            "attempt_receipt": {
                "publication_link_status": "LINKED_EXTERNAL_LEDGER",
            },
        }
        runtime_complete = _build_runtime_completion_gate(
            input_post_count=1,
            completed_count=1,
            pending_count=0,
            failed_count=0,
            terminal_artifacts_finalized=True,
        )
        valid_gate = _build_decision_call_measurement_gate(
            measurement_config=required,
            ledger_summary=complete_summary,
            row_attempts={1: linked_entry},
            expected_input_count=1,
        )
        self.assertTrue(_large_run_complete_from_gates(runtime_complete, valid_gate))

        cases = {
            "external_link_failed": (
                complete_summary,
                {
                    **linked_entry,
                    "attempt_receipt": {
                        "publication_link_status": "LINK_FAILED_NOT_ESTIMABLE",
                    },
                },
                "ROW_EXTERNAL_LEDGER_UNLINKED",
            ),
            "row_not_estimable": (
                complete_summary,
                {
                    **linked_entry,
                    "row_summary": {
                        "writer_complete": False,
                        "actual_kpi_status": "NOT_ESTIMABLE",
                    },
                },
                "ROW_NOT_ESTIMABLE",
            ),
            "ambiguous_or_unlinked_ledger": (
                {
                    **complete_summary,
                    "ledger_status": "PARTIAL",
                    "actual_kpi_status": "NOT_ESTIMABLE",
                    "reason_codes": [
                        "AMBIGUOUS_MULTIPLE_ATTEMPT_RUNS",
                        "UNLINKED_ROW_ATTEMPT",
                    ],
                },
                linked_entry,
                "LEDGER_AMBIGUOUS_MULTIPLE_ATTEMPT_RUNS",
            ),
        }
        for name, (summary, row_entry, expected_reason) in cases.items():
            with self.subTest(name=name):
                gate = _build_decision_call_measurement_gate(
                    measurement_config=required,
                    ledger_summary=summary,
                    row_attempts={1: row_entry},
                    expected_input_count=1,
                )
                self.assertEqual(gate["status"], "NO_GO")
                self.assertTrue(gate["blocks_large_run_complete"])
                self.assertIn(expected_reason, gate["reason_codes"])
                self.assertFalse(_large_run_complete_from_gates(runtime_complete, gate))

    def test_parallel_initial_manifest_contains_all_three_completion_gates(self):
        source = Path(expert_main_module.__file__).read_text(encoding="utf-8")
        parallel_start = source.index("# ===== 병렬 모드 =====")
        initial_manifest = source.index(
            "_atomic_write_json(\n                    result_manifest_path,",
            parallel_start,
        )
        worker_start = source.index("# 워커별 로그 파일 생성", initial_manifest)
        initial_block = source[initial_manifest:worker_start]
        self.assertIn("**_completion_manifest_gate_fields(", initial_block)
        self.assertIn('"next_save_idx": 1', initial_block)
        self.assertIn('"partial_flush_gap": False', initial_block)
        self.assertIn('"ordered_flush_blocked": False', initial_block)

    def test_existing_wal_rows_are_replayed_without_worker_resubmission(self):
        source = Path(expert_main_module.__file__).read_text(encoding="utf-8")
        self.assertIn("_publication_replay_by_index", source)
        self.assertIn('else "durable_replay"', source)
        self.assertIn('status="durable_replay"', source)
        self.assertIn("if i in _publication_replay_by_index:\n                            continue", source)
        self.assertIn("publication_commit_registry.result(_replay_receipt.post_id)", source)
        self.assertIn(
            "_queue_batch_context_publication_learning(\n"
            "                    input_index=_replay_index,\n"
            "                    canonical_result=_replay_result,\n"
            "                    publication_receipt=_replay_receipt,\n"
            "                    created=True,",
            source,
        )
        self.assertNotIn("_batch_context.learn_from_result(_replay_result)", source)
        self.assertIn("_slang_db_manager.record_result(_replay_result)", source)
        self.assertIn('"batch_context_learning": {', source)
        self.assertIn('"pending_count": len(_batch_context_learning_pending)', source)
        self.assertIn('"same_wave_observation_deterministic": False', source)

    def test_slang_db_uses_one_snapshot_and_defers_source_promotion(self):
        source = Path(expert_main_module.__file__).read_text(encoding="utf-8")
        self.assertIn("_slang_db_manager_path = slang_db_work_path", source)
        self.assertIn("_scope_slang_db_snapshot_bytes", source)
        self.assertIn("_scope_slang_db_snapshot_text", source)
        self.assertIn("def _finalize_slang_db(*, publish: bool)", source)
        self.assertIn("_finalize_slang_db(publish=False)", source)
        self.assertIn("_finalize_slang_db(publish=_slang_publish_ready)", source)
        self.assertIn('"publication_slang_db_writeback_complete"', source)
        self.assertIn('"explicit_post_run_only"', source)
        self.assertIn('"publication_slang_db_promotion_ready"', source)
        self.assertNotIn("_atomic_write_text(\n                    _slang_db_path,", source)
        self.assertNotIn("\n            _slang_db_manager.finalize()\n            if _PARALLEL", source)

    def test_runtime_binding_echo_fields_are_absent_without_environment(self):
        keys = ["FRESH375_RUN_BINDING_TOKEN", "RUNTIME_RELEASE_FINGERPRINT_SHA256"]
        with patch.dict(os.environ, {}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            self.assertEqual(_runtime_binding_echo_fields(), {})

    def test_runtime_binding_echo_fields_preserve_exact_values(self):
        token = "  fresh-binding-token-exact  "
        fingerprint = "a" * 64
        with patch.dict(
            os.environ,
            {
                "FRESH375_RUN_BINDING_TOKEN": token,
                "RUNTIME_RELEASE_FINGERPRINT_SHA256": fingerprint,
            },
            clear=False,
        ):
            self.assertEqual(
                _runtime_binding_echo_fields(),
                {
                    "fresh375_run_binding_token": token,
                    "runtime_release_fingerprint_sha256": fingerprint,
                },
            )

    def test_runtime_binding_echo_is_wired_to_rows_and_manifests(self):
        source = Path(expert_main_module.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("**_runtime_binding_echo_fields()"), 2)
        self.assertIn('"run_meta": {\n                        **_runtime_binding_echo_fields(),', source)
        manifest_function = source.index(
            "def _parallel_manifest_fields() -> Dict[str, Any]:"
        )
        manifest_return = source.index(
            "**_runtime_binding_echo_fields()",
            manifest_function,
        )
        self.assertGreater(manifest_return, manifest_function)

    def test_build_completed_subset_rows_keeps_flushed_prefix_and_pending_order(self):
        flushed = [
            {"post_id": 101, "title": "flushed-1"},
            {"post_id": 102, "title": "flushed-2"},
        ]
        pending = {
            5: {"post_id": 105, "title": "pending-5"},
            4: {"post_id": 104, "title": "pending-4"},
        }

        rows = _build_completed_subset_rows(flushed, pending)

        self.assertEqual([row["post_id"] for row in rows], [101, 102, 104, 105])
        self.assertEqual(flushed[0]["title"], "flushed-1")
        self.assertEqual(pending[5]["title"], "pending-5")

    def test_load_jsonl_posts_accepts_utf8_sig_and_content_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "post_id": 10426463,
                        "title": "뭔가 소설보는데 설정들을 어디서 따온거같은 느낌이 듦",
                        "content": ["단테랑 이스마엘", "작가가 프문을 좀 많이 좋아하나"],
                        "comments": ["림버스에서 가져온 소설 하나 있긴 하던데"],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8-sig",
            )

            posts = load_jsonl_posts(
                input_path,
                snapshot_bytes=input_path.read_bytes(),
            )

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].post_id, 10426463)
        self.assertEqual([block.text for block in posts[0].content_blocks], [
            "단테랑 이스마엘",
            "작가가 프문을 좀 많이 좋아하나",
        ])
        self.assertEqual(posts[0].comments[0]["content"], "림버스에서 가져온 소설 하나 있긴 하던데")

    def test_load_jsonl_posts_collapses_identical_duplicate_post_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "duplicate.jsonl"
            row = {"post_id": 10426463, "title": "동일 행", "content": ["본문 A"]}
            rows = [row, {**row, "post_id": "10426463"}]
            input_path.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in rows) + "\n",
                encoding="utf-8",
            )

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                posts = load_jsonl_posts(
                    input_path,
                    snapshot_bytes=input_path.read_bytes(),
                )

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].post_id, 10426463)
        self.assertEqual(posts[0].title, "동일 행")
        self.assertIn("duplicate_rows=1", stderr.getvalue())
        self.assertIn("duplicate_post_ids=1", stderr.getvalue())
        self.assertIn("10426463(1,2)", stderr.getvalue())

    def test_load_jsonl_posts_rejects_conflicting_duplicate_post_id_before_runtime(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "duplicate.jsonl"
            rows = [
                {"post_id": 10426463, "title": "첫 행", "content": ["본문 A"]},
                {"post_id": 10426463, "title": "덮어쓰기 행", "content": ["본문 B"]},
            ]
            input_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                r"내용이 다른 중복 post_id.*post_id=10426463.*first_line=1.*duplicate_line=2",
            ):
                load_jsonl_posts(input_path)

    def test_load_jsonl_posts_preserves_image_blocks_for_vlm_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "post_id": 11718082,
                        "title": "이게 백합 소설이 아니라니...",
                        "content": [
                            {"type": "image", "url": "https://example.test/image.jpg"},
                            "두렵구나",
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            posts = load_jsonl_posts(input_path)

        self.assertTrue(_post_has_image_block(posts[0]))
        self.assertEqual(_count_image_posts(posts), 1)
        self.assertEqual(posts[0].content_blocks[0].type, "image")
        self.assertEqual(posts[0].content_blocks[0].url, "https://example.test/image.jpg")

    def test_load_jsonl_posts_preserves_source_evidence_for_replay(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "post_id": 11705231,
                        "title": "장갤 설지후 변화도 레전드임",
                        "content": ["설지후 캐릭터 변화 이야기"],
                        "search_results": [
                            {
                                "title": "탐식의 재림 - 판타지 e북 - 카카오페이지",
                                "url": "https://page.kakao.com/content/50219568",
                                "content": "탐식의 재림 공식 상세",
                            }
                        ],
                        "native_web_seed": {
                            "official_title": "탐식의 재림",
                            "urls": ["https://series.naver.com/novel/detail.series?productNo=2847498"],
                        },
                        "source_evidence": {
                            "official_title": "탐식의 재림",
                            "official_urls": ["https://page.kakao.com/content/50219568?tab_type=comment"],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            posts = load_jsonl_posts(input_path)

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].search_results[0]["url"], "https://page.kakao.com/content/50219568")
        self.assertEqual(posts[0].native_web_seed["official_title"], "탐식의 재림")
        self.assertEqual(posts[0].source_evidence["official_urls"][0], "https://page.kakao.com/content/50219568?tab_type=comment")

    def test_load_jsonl_posts_preserves_image_url_and_src_aliases_for_vlm_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.jsonl"
            rows = [
                {
                    "post_id": 11718082,
                    "title": "이미지 안에 작품명이 있는 글",
                    "content": [
                        {"image_url": "https://dcimg.example/post11718082.jpg"},
                    ],
                },
                {
                    "post_id": 11718099,
                    "title": "이미지 첨부 글",
                    "content": [
                        {"src": "https://dcimg.example/post11718099.png"},
                    ],
                },
            ]
            input_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            posts = load_jsonl_posts(input_path)

        self.assertEqual(_count_image_posts(posts), 2)
        self.assertEqual(posts[0].content_blocks[0].type, "image")
        self.assertEqual(posts[0].content_blocks[0].url, "https://dcimg.example/post11718082.jpg")
        self.assertEqual(posts[1].content_blocks[0].type, "image")
        self.assertEqual(posts[1].content_blocks[0].url, "https://dcimg.example/post11718099.png")

    def test_env_toggle_enabled_accepts_on_value(self):
        with patch.dict(os.environ, {"LLM_VLM": "on", "LLM_OCR": "0"}, clear=False):
            self.assertTrue(_env_toggle_enabled("LLM_VLM"))
            self.assertFalse(_env_toggle_enabled("LLM_OCR", "1"))

    def test_expert_main_default_vlm_image_limit_matches_pipeline_default(self):
        self.assertEqual(expert_main_module._DEFAULT_VLM_MAX_IMAGE_BYTES, "16777216")

    def test_load_jsonl_posts_rehydrates_comment_metadata_for_embedded_strings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "gallery_id": "genrenovel",
                        "post_id": 11718097,
                        "title": "망겜힐은 오행복 박태양이 빌런이였어야돼",
                        "author": "ㅇㅇ",
                        "content": ["본문"],
                        "comments": ["아 이거 맞다", "다른 답변"],
                        "comment_metadata": [
                            {
                                "comment_id": "40479972",
                                "gallery_id": "genrenovel",
                                "author": "ㅇㅇ",
                                "ip": "123.248",
                                "reply_level": 0,
                            },
                            {
                                "comment_id": "40479973",
                                "gallery_id": "genrenovel",
                                "author": "다른유저",
                                "ip": "211.36",
                                "reply_to_comment_id": "40479972",
                                "reply_level": 1,
                            },
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            posts = load_jsonl_posts(input_path)

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].gallery_id, "genrenovel")
        self.assertEqual(posts[0].comments[0]["content"], "아 이거 맞다")
        self.assertEqual(posts[0].comments[0]["comment_id"], "40479972")
        self.assertEqual(posts[0].comments[0]["author"], "ㅇㅇ")
        self.assertEqual(posts[0].comments[0]["ip"], "123.248")
        self.assertEqual(posts[0].comments[1]["reply_to_comment_id"], "40479972")
        self.assertEqual(posts[0].comments[1]["reply_level"], 1)

    def test_load_jsonl_posts_preserves_separate_comment_rows_for_speaker_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.jsonl"
            rows = [
                {
                    "comment_id": "c2",
                    "post_id": 11718097,
                    "author": "reader",
                    "ip": "211.36",
                    "content": "reply content",
                    "reply_to_comment_id": "c1",
                    "reply_level": 1,
                },
                {
                    "gallery_id": "genrenovel",
                    "post_id": 11718097,
                    "title": "title alias with character talk",
                    "author": "writer",
                    "content": ["body text"],
                },
                {
                    "comment_id": "c1",
                    "post_id": 11718097,
                    "author": "writer",
                    "ip": "123.248",
                    "content": "post author followup",
                    "reply_level": 0,
                },
            ]
            input_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            posts = load_jsonl_posts(input_path)

        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post.gallery_id, "genrenovel")
        self.assertEqual(len(post.comments), 2)
        self.assertEqual(post.comments[0]["comment_id"], "c2")
        self.assertEqual(post.comments[0]["gallery_id"], "genrenovel")
        self.assertEqual(post.comments[0]["reply_to_comment_id"], "c1")
        self.assertEqual(post.comments[1]["comment_id"], "c1")

        meta = _public_comment_metadata(post.comments, post.author, post.gallery_id)
        lines = _public_comment_context_lines(meta)

        self.assertEqual(meta[0]["speaker"], "user1")
        self.assertEqual(meta[1]["speaker"], "post_author")
        self.assertIn("author=reader", lines[0])
        self.assertIn("reply_to=c1", lines[0])
        self.assertIn("author=writer", lines[1])
        self.assertIn("role=post_author", lines[1])
        self.assertIn("ip=123.248", lines[1])

    def test_public_comment_context_lines_are_available_for_result_rows(self):
        comments = [
            {
                "comment_id": "c1",
                "author": "글쓴이",
                "ip": "123.248",
                "content": "이거 맞다",
                "reply_level": 0,
            },
            {
                "comment_id": "c2",
                "author": "다른유저",
                "ip": "211.36",
                "content": "작품명 후보",
                "reply_level": 1,
                "reply_to_comment_id": "c1",
            },
        ]

        meta = _public_comment_metadata(comments, "글쓴이", "genrenovel")
        lines = _public_comment_context_lines(meta)
        dialogue_lines = _public_comment_dialogue_context_lines(comments, meta)

        self.assertEqual(meta[0]["speaker"], "post_author")
        self.assertTrue(meta[0]["is_post_author"])
        self.assertEqual(meta[1]["speaker"], "user1")
        self.assertIn("author=글쓴이", lines[0])
        self.assertIn("role=post_author", lines[0])
        self.assertIn("ip=123.248", lines[0])
        self.assertIn("author=다른유저", lines[1])
        self.assertIn("reply_to=c1", lines[1])
        self.assertIn("comment_id=c2", lines[1])
        self.assertIn("role=post_author", dialogue_lines[0])
        self.assertIn("text=이거 맞다", dialogue_lines[0])
        self.assertIn("author=다른유저", dialogue_lines[1])
        self.assertIn("text=작품명 후보", dialogue_lines[1])

    def test_count_nonempty_jsonl_lines_ignores_utf8_sig_on_blank_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.jsonl"
            input_path.write_text("\ufeff\n\n", encoding="utf-8")

            self.assertEqual(_count_nonempty_jsonl_lines(input_path), 0)

    def test_effective_parallel_treats_requested_parallel_as_maximum(self):
        with patch.object(expert_main_module, "_REQUESTED_PARALLEL", 36):
            cases = {
                0: 1,
                1: 1,
                5: 5,
                9: 9,
                36: 36,
                100: 36,
            }
            for post_count, expected in cases.items():
                with self.subTest(post_count=post_count):
                    self.assertEqual(_effective_parallel_for_post_count(post_count), expected)

        with patch.object(expert_main_module, "_REQUESTED_PARALLEL", 5):
            self.assertEqual(_effective_parallel_for_post_count(100), 5)

    def test_configure_mcp_endpoints_caps_small_run_auto_shards(self):
        keys = [
            "MCP_ENDPOINTS",
            "MCP_ENDPOINT",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_COUNT",
            "MCP_AUTO_SHARD_LIMIT",
            "MCP_SMALL_RUN_AUTO_SHARD_LIMIT",
            "MCP_SMALL_RUN_SHARD_THRESHOLD",
            "MCP_SHARD_BASE_PORT",
            "MCP_SHARD_SCHEME",
            "MCP_SHARD_HOST",
        ]
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            _configure_mcp_endpoints(5)

            self.assertEqual(os.environ["MCP_ENDPOINTS_AUTOGEN"], "1")
            self.assertEqual(
                os.environ["MCP_ENDPOINTS"],
                "http://127.0.0.1:3333,http://127.0.0.1:3334",
            )

    def test_configure_mcp_endpoints_respects_explicit_shard_count(self):
        keys = [
            "MCP_ENDPOINTS",
            "MCP_ENDPOINT",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_COUNT",
            "MCP_AUTO_SHARD_LIMIT",
            "MCP_SMALL_RUN_AUTO_SHARD_LIMIT",
            "MCP_SMALL_RUN_SHARD_THRESHOLD",
            "MCP_SHARD_BASE_PORT",
            "MCP_SHARD_SCHEME",
            "MCP_SHARD_HOST",
        ]
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ["MCP_SHARD_COUNT"] = "5"
            _configure_mcp_endpoints(5)

            self.assertEqual(os.environ["MCP_ENDPOINTS_AUTOGEN"], "1")
            self.assertEqual(len(os.environ["MCP_ENDPOINTS"].split(",")), 5)

    def test_shard_lifecycle_actions_default_to_explicit_opt_in(self):
        keys = ["MCP_AUTO_UP_SHARDS", "MCP_AUTO_RECREATE_SHARDS", "MCP_SMALL_RUN_SHARD_THRESHOLD"]
        default_args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            with patch.object(expert_main_module, "_CLI_ARGS", default_args), patch.object(expert_main_module, "_PARALLEL", 36):
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())

    def test_default_goal_run_does_not_enter_local_shard_management(self):
        keys = [
            "MCP_AUTO_UP_SHARDS",
            "MCP_AUTO_RECREATE_SHARDS",
            "MCP_LOCAL_SHARD_STATUS_AUDIT",
            "MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_HOST",
            "MCP_SMALL_RUN_SHARD_THRESHOLD",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
        ]
        default_args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
            "MCP_SMALL_RUN_SHARD_THRESHOLD": "10",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
            "MCP_AUTO_UP_SHARDS": "1",
            "MCP_AUTO_RECREATE_SHARDS": "1",
        }
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", default_args),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                self.assertTrue(_small_run_shard_lifecycle_blocked())
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())
                self.assertFalse(_can_auto_manage_local_shards())

            os.environ["MCP_LOCAL_SHARD_STATUS_AUDIT"] = "1"
            with (
                patch.object(expert_main_module, "_CLI_ARGS", default_args),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())
                self.assertFalse(_can_auto_manage_local_shards())

            os.environ["MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT"] = "1"
            with (
                patch.object(expert_main_module, "_CLI_ARGS", default_args),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())
                self.assertTrue(_can_auto_manage_local_shards())

    def test_missing_shard_scale_up_defaults_on_for_large_autogen_run(self):
        keys = [
            "CODEX_SHELL",
            "CODEX_THREAD_ID",
            "MCP_AUTO_SCALE_UP_MISSING_SHARDS",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_HOST",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
        ]
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 32),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 104502),
            ):
                # 대형 검증 런 + autogen 로컬 풀이면 부족 shard 증분 기동은 기본 허용.
                self.assertTrue(_allow_missing_shard_auto_scale_up())
                # 단, 기존 opt-in 전용 lifecycle 액션(auto_up/recreate)은 여전히 꺼져 있어야 한다.
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())

                os.environ["MCP_AUTO_SCALE_UP_MISSING_SHARDS"] = "0"
                self.assertFalse(_allow_missing_shard_auto_scale_up())
                os.environ.pop("MCP_AUTO_SCALE_UP_MISSING_SHARDS", None)

                os.environ["MCP_ENDPOINTS_AUTOGEN"] = "0"
                self.assertFalse(_allow_missing_shard_auto_scale_up())
                os.environ["MCP_ENDPOINTS_AUTOGEN"] = "1"

                os.environ["MCP_SHARD_HOST"] = "192.168.0.10"
                self.assertFalse(_allow_missing_shard_auto_scale_up())

    def test_missing_shard_scale_up_respects_existing_lifecycle_blocks(self):
        keys = [
            "CODEX_SHELL",
            "CODEX_THREAD_ID",
            "MCP_AUTO_SCALE_UP_MISSING_SHARDS",
            "MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_HOST",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
        ]
        base_kwargs = dict(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)

            # 소규모 goal/test 런은 기존 lifecycle 차단을 그대로 따른다.
            with (
                patch.object(expert_main_module, "_CLI_ARGS", Namespace(**base_kwargs)),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                self.assertFalse(_allow_missing_shard_auto_scale_up())

            # Codex 런은 hard opt-in 없이는 차단.
            os.environ["CODEX_SHELL"] = "1"
            os.environ["CODEX_THREAD_ID"] = "thread-test"
            with (
                patch.object(expert_main_module, "_CLI_ARGS", Namespace(**base_kwargs)),
                patch.object(expert_main_module, "_PARALLEL", 32),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 104502),
            ):
                self.assertFalse(_allow_missing_shard_auto_scale_up())

            # Codex 런: 셸 프로필에서 물려받은 stale env ack '단독'으로는 열리지
            # 않아야 한다 (env 단독 불가 불변식 유지).
            os.environ["MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE"] = "1"
            with (
                patch.object(expert_main_module, "_CLI_ARGS", Namespace(**base_kwargs)),
                patch.object(expert_main_module, "_PARALLEL", 32),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 104502),
            ):
                self.assertFalse(_allow_missing_shard_auto_scale_up())

            # 같은 env라도 현재 커맨드 opt-in(--allow-goal-shard-lifecycle)이
            # 있으면 허용.
            with (
                patch.object(
                    expert_main_module,
                    "_CLI_ARGS",
                    Namespace(**{**base_kwargs, "allow_goal_shard_lifecycle": True}),
                ),
                patch.object(expert_main_module, "_PARALLEL", 32),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 104502),
            ):
                self.assertTrue(_allow_missing_shard_auto_scale_up())
            os.environ.pop("MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE", None)
            os.environ.pop("CODEX_SHELL", None)
            os.environ.pop("CODEX_THREAD_ID", None)

            # 소규모 goal 런: 허가 플래그(--allow-goal-shard-lifecycle) '단독'으로는
            # 차단 — 기존 2-key(허가+액션) 계약 유지.
            with (
                patch.object(
                    expert_main_module,
                    "_CLI_ARGS",
                    Namespace(**{**base_kwargs, "allow_goal_shard_lifecycle": True}),
                ),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                self.assertFalse(_allow_missing_shard_auto_scale_up())

            # 허가+액션(--auto-up-shards) 결합이면 소규모 런에서도 허용.
            with (
                patch.object(
                    expert_main_module,
                    "_CLI_ARGS",
                    Namespace(
                        **{
                            **base_kwargs,
                            "allow_goal_shard_lifecycle": True,
                            "auto_up_shards": True,
                        }
                    ),
                ),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                self.assertTrue(_allow_missing_shard_auto_scale_up())

            # reuse-only / no-auto-up 명시 시 차단.
            with (
                patch.object(
                    expert_main_module,
                    "_CLI_ARGS",
                    Namespace(**{**base_kwargs, "reuse_shards_only": True}),
                ),
                patch.object(expert_main_module, "_PARALLEL", 32),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 104502),
            ):
                self.assertFalse(_allow_missing_shard_auto_scale_up())
            with (
                patch.object(
                    expert_main_module,
                    "_CLI_ARGS",
                    Namespace(**{**base_kwargs, "no_auto_up_shards": True}),
                ),
                patch.object(expert_main_module, "_PARALLEL", 32),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 104502),
            ):
                self.assertFalse(_allow_missing_shard_auto_scale_up())

    def test_missing_shard_scale_up_targets_missing_shards_without_recreate(self):
        captured = {}

        def _fake_run(cmd, cwd=None, check=None, env=None, **kwargs):
            captured["cmd"] = [str(part) for part in cmd]
            captured["env"] = env

        with patch.object(expert_main_module.subprocess, "run", _fake_run):
            expert_main_module._scale_up_missing_local_shards(
                Path("."),
                32,
                [17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32],
            )

        cmd = captured["cmd"]
        self.assertIn("up", cmd)
        self.assertIn("--shards", cmd)
        self.assertEqual(cmd[cmd.index("--shards") + 1], "17-32")
        self.assertEqual(cmd[cmd.index("--count") + 1], "32")
        # 기존 healthy 컨테이너 보호: no-recreate 강제 + orphan 제거 차단.
        self.assertEqual(captured["env"].get("WARP_SHARDS_NO_RECREATE"), "1")
        self.assertEqual(captured["env"].get("WARP_SHARDS_REMOVE_ORPHANS"), "0")

    def test_codex_goal_run_ignores_stale_env_lifecycle_even_above_threshold(self):
        keys = [
            "CODEX_SHELL",
            "CODEX_THREAD_ID",
            "MCP_AUTO_UP_SHARDS",
            "MCP_AUTO_RECREATE_SHARDS",
            "MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE",
            "MCP_LOCAL_SHARD_STATUS_AUDIT",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_HOST",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
        ]
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        env = {
            "CODEX_SHELL": "1",
            "CODEX_THREAD_ID": "thread-test",
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
            "MCP_AUTO_UP_SHARDS": "1",
            "MCP_AUTO_RECREATE_SHARDS": "1",
        }
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 36),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 1000),
            ):
                self.assertFalse(_small_run_shard_lifecycle_blocked())
                self.assertTrue(_env_shard_lifecycle_blocked_by_context())
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())
                self.assertFalse(_can_auto_manage_local_shards())

    def test_codex_goal_run_blocks_auto_flags_without_goal_lifecycle_allow(self):
        args = Namespace(
            auto_up_shards=True,
            no_auto_up_shards=False,
            auto_recreate_shards=True,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=False,
        )
        env = {
            "CODEX_SHELL": "1",
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 36),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 1000),
            ):
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())
                self.assertFalse(_can_auto_manage_local_shards())

    def test_small_goal_run_blocks_auto_flags_without_hard_opt_in(self):
        keys = [
            "CODEX_SHELL",
            "CODEX_THREAD_ID",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_HOST",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
        ]
        args = Namespace(
            auto_up_shards=True,
            no_auto_up_shards=False,
            auto_recreate_shards=True,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=False,
        )
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                self.assertTrue(_small_run_shard_lifecycle_blocked())
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())
                self.assertFalse(_can_auto_manage_local_shards())

    def test_codex_goal_run_allows_current_command_lifecycle_with_hard_opt_in(self):
        args = Namespace(
            auto_up_shards=True,
            no_auto_up_shards=False,
            auto_recreate_shards=True,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=True,
        )
        env = {
            "CODEX_SHELL": "1",
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 36),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 1000),
            ):
                self.assertTrue(_allow_local_shard_auto_up())
                self.assertTrue(_allow_local_shard_recreate())
                self.assertTrue(_can_auto_manage_local_shards())

    def test_codex_goal_run_blocks_env_lifecycle_without_command_hard_opt_in(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=False,
        )
        env = {
            "CODEX_SHELL": "1",
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
            "MCP_AUTO_UP_SHARDS": "1",
            "MCP_AUTO_RECREATE_SHARDS": "1",
            "MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 36),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 1000),
            ):
                self.assertTrue(_env_shard_lifecycle_blocked_by_context())
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())
                self.assertFalse(_can_auto_manage_local_shards())

    def test_codex_goal_run_can_allow_env_lifecycle_with_command_hard_opt_in(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=True,
        )
        env = {
            "CODEX_SHELL": "1",
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
            "MCP_AUTO_UP_SHARDS": "1",
            "MCP_AUTO_RECREATE_SHARDS": "1",
            "MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 36),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 1000),
            ):
                self.assertFalse(_env_shard_lifecycle_blocked_by_context())
                self.assertTrue(_allow_local_shard_auto_up())
                self.assertTrue(_allow_local_shard_recreate())
                self.assertTrue(_can_auto_manage_local_shards())

    def test_goal_run_caps_autogen_shards_without_lifecycle_opt_in(self):
        keys = [
            "MCP_ENDPOINTS",
            "MCP_ENDPOINT",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_COUNT",
            "MCP_AUTO_SHARD_LIMIT",
            "MCP_SMALL_RUN_AUTO_SHARD_LIMIT",
            "MCP_SMALL_RUN_SHARD_THRESHOLD",
            "MCP_GOAL_RUN_AUTO_SHARD_LIMIT",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
            "MCP_SMALL_RUN_ALLOW_SHARD_LIFECYCLE",
            "MCP_SHARD_BASE_PORT",
            "MCP_SHARD_SCHEME",
            "MCP_SHARD_HOST",
        ]
        default_args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        env = {
            "MCP_SMALL_RUN_SHARD_THRESHOLD": "10",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
            "MCP_GOAL_RUN_AUTO_SHARD_LIMIT": "8",
        }
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", default_args),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                _configure_mcp_endpoints(24)

            self.assertEqual(os.environ["MCP_ENDPOINTS_AUTOGEN"], "1")
            self.assertEqual(len(os.environ["MCP_ENDPOINTS"].split(",")), 8)

    def test_goal_run_cap_overrides_stale_explicit_shard_count_without_lifecycle_opt_in(self):
        keys = [
            "MCP_ENDPOINTS",
            "MCP_ENDPOINT",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_COUNT",
            "MCP_AUTO_SHARD_LIMIT",
            "MCP_GOAL_RUN_AUTO_SHARD_LIMIT",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
            "MCP_SMALL_RUN_ALLOW_SHARD_LIFECYCLE",
        ]
        default_args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        env = {
            "MCP_SHARD_COUNT": "36",
            "MCP_GOAL_RUN_AUTO_SHARD_LIMIT": "8",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", default_args),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                _configure_mcp_endpoints(24)

            self.assertEqual(os.environ["MCP_ENDPOINTS_AUTOGEN"], "1")
            self.assertEqual(len(os.environ["MCP_ENDPOINTS"].split(",")), 8)

    def test_stale_shard_count_36_does_not_expand_small_run_health_budget(self):
        keys = [
            "MCP_ENDPOINTS",
            "MCP_ENDPOINT",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_SHARD_COUNT",
            "MCP_AUTO_SHARD_LIMIT",
            "MCP_GOAL_RUN_AUTO_SHARD_LIMIT",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
            "MCP_HEALTH_REQUIRED_OK",
            "MCP_HEALTH_PROBE_BATCH_SIZE",
        ]
        default_args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        env = {
            "MCP_SHARD_COUNT": "36",
            "MCP_GOAL_RUN_AUTO_SHARD_LIMIT": "8",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", default_args),
                patch.object(expert_main_module, "_PARALLEL", 5),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 5),
            ):
                _configure_mcp_endpoints(5)
                endpoints = os.environ["MCP_ENDPOINTS"].split(",")
                required_ok = _mcp_health_required_ok_count(endpoints)
                batch_size = _mcp_health_probe_batch_size(
                    endpoints,
                    required_ok_count=required_ok,
                    health_workers=36,
                )

            self.assertEqual(os.environ["MCP_ENDPOINTS_AUTOGEN"], "1")
            self.assertEqual(len(endpoints), 8)
            self.assertEqual(required_ok, 5)
            self.assertEqual(batch_size, 5)

    def test_goal_run_autogen_filters_to_healthy_endpoints_by_default(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        endpoints = [
            "http://127.0.0.1:3333",
            "http://127.0.0.1:3334",
            "http://127.0.0.1:3335",
            "http://127.0.0.1:3336",
        ]
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_ENDPOINTS": ",".join(endpoints),
            "MCP_ENDPOINT": endpoints[0],
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
            "MCP_GOAL_RUN_FILTER_HEALTHY_AUTOGEN": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                filtered, meta = _apply_reuse_only_healthy_endpoint_filter(
                    endpoints,
                    {
                        endpoints[0]: {"ok": True},
                        endpoints[2]: {"ok": True},
                    },
                )

                self.assertEqual(filtered, [endpoints[0], endpoints[2]])
                self.assertEqual(expert_main_module._PARALLEL, 2)
                self.assertTrue(meta["mcp_healthy_autogen_endpoint_filter"])
                self.assertFalse(meta["mcp_reuse_shards_only_health_filtered"])
                self.assertTrue(meta["mcp_goal_run_health_filtered"])
                self.assertEqual(meta["mcp_healthy_autogen_endpoint_filter_reason"], "goal_run_lifecycle_blocked")

    def test_goal_run_filters_explicit_endpoint_list_to_healthy_subset(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=False,
        )
        endpoints = [
            "http://127.0.0.1:3333",
            "http://127.0.0.1:3334",
            "http://127.0.0.1:3335",
            "http://127.0.0.1:3336",
        ]
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "0",
            "MCP_ENDPOINTS": ",".join(endpoints),
            "MCP_ENDPOINT": endpoints[0],
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
            "MCP_GOAL_RUN_FILTER_HEALTHY_ENDPOINTS": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 24),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 24),
            ):
                self.assertEqual(_healthy_endpoint_filter_reason(), "goal_run_lifecycle_blocked")
                filtered, meta = _apply_reuse_only_healthy_endpoint_filter(
                    endpoints,
                    {
                        endpoints[0]: {"ok": True},
                        endpoints[2]: {"ok": True},
                    },
                )

                self.assertEqual(filtered, [endpoints[0], endpoints[2]])
                self.assertEqual(expert_main_module._PARALLEL, 2)
                self.assertTrue(meta["mcp_healthy_endpoint_filter"])
                self.assertFalse(meta["mcp_healthy_autogen_endpoint_filter"])
                self.assertFalse(meta["mcp_healthy_endpoint_filter_autogen"])
                self.assertTrue(meta["mcp_goal_run_health_filtered"])

    def test_small_goal_run_health_defaults_to_readyz_only(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=False,
        )
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "0",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        keys = [
            "MCP_HEALTH_INCLUDE_SEARCH",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
        ]
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 2),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 2),
            ):
                self.assertTrue(_mcp_goal_run_light_health_mode())
                self.assertFalse(_default_mcp_health_include_search())

    def test_health_light_mode_env_can_force_full_probe_for_small_goal_run(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=False,
        )
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "0",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
            "MCP_HEALTH_LIGHT_MODE": "0",
        }
        keys = [
            "MCP_HEALTH_INCLUDE_SEARCH",
            "MCP_HEALTH_LIGHT_MODE",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
        ]
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 2),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 2),
            ):
                self.assertFalse(_mcp_goal_run_light_health_mode())
                self.assertTrue(_default_mcp_health_include_search())

    def test_large_validation_keeps_search_health_default_when_not_auto_managed(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=False,
        )
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "0",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        keys = [
            "MCP_HEALTH_INCLUDE_SEARCH",
            "MCP_ENDPOINTS_AUTOGEN",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
        ]
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 36),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 1000),
            ):
                self.assertFalse(_mcp_goal_run_light_health_mode())
                self.assertTrue(_default_mcp_health_include_search())

    def test_reuse_only_explicit_endpoint_health_budget_uses_effective_parallel(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=True,
            allow_goal_shard_lifecycle=False,
        )
        endpoints = [f"http://127.0.0.1:{3333 + idx}" for idx in range(36)]
        keys = [
            "MCP_HEALTH_REQUIRED_OK",
            "MCP_HEALTH_PROBE_BATCH_SIZE",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD",
        ]
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ["MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD"] = "36"
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 2),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 2),
            ):
                required_ok = _mcp_health_required_ok_count(endpoints)
                batch_size = _mcp_health_probe_batch_size(
                    endpoints,
                    required_ok_count=required_ok,
                    health_workers=12,
                )

                self.assertEqual(required_ok, 2)
                self.assertEqual(batch_size, 2)

    def test_large_explicit_endpoint_list_keeps_failures_visible_without_reuse_only(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=False,
        )
        endpoints = [
            "http://127.0.0.1:3333",
            "http://127.0.0.1:3334",
        ]
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "0",
            "MCP_ENDPOINTS": ",".join(endpoints),
            "MCP_ENDPOINT": endpoints[0],
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 100),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 100),
            ):
                self.assertIsNone(_healthy_endpoint_filter_reason())
                filtered, meta = _apply_reuse_only_healthy_endpoint_filter(
                    endpoints,
                    {endpoints[0]: {"ok": True}},
                )

                self.assertEqual(filtered, endpoints)
                self.assertFalse(meta["mcp_healthy_endpoint_filter"])

    def test_shard_lifecycle_actions_can_be_enabled_by_cli_or_explicit_env_ack(self):
        keys = [
            "CODEX_SHELL",
            "CODEX_THREAD_ID",
            "MCP_AUTO_UP_SHARDS",
            "MCP_AUTO_RECREATE_SHARDS",
            "MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE",
            "MCP_ALLOW_ENV_SHARD_LIFECYCLE",
        ]
        cli_args = Namespace(
            auto_up_shards=True,
            no_auto_up_shards=False,
            auto_recreate_shards=True,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", cli_args),
                patch.object(expert_main_module, "_PARALLEL", 36),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 1000),
            ):
                self.assertTrue(_allow_local_shard_auto_up())
                self.assertTrue(_allow_local_shard_recreate())

        env_args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(
                {
                    "MCP_ALLOW_ENV_SHARD_LIFECYCLE": "1",
                    "MCP_AUTO_UP_SHARDS": "1",
                    "MCP_AUTO_RECREATE_SHARDS": "1",
                }
            )
            with (
                patch.object(expert_main_module, "_CLI_ARGS", env_args),
                patch.object(expert_main_module, "_PARALLEL", 36),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 1000),
            ):
                self.assertTrue(_allow_local_shard_auto_up())
                self.assertTrue(_allow_local_shard_recreate())

    def test_env_lifecycle_vars_alone_are_ignored(self):
        keys = [
            "CODEX_SHELL",
            "CODEX_THREAD_ID",
            "MCP_AUTO_UP_SHARDS",
            "MCP_AUTO_RECREATE_SHARDS",
            "MCP_ALLOW_ENV_SHARD_LIFECYCLE",
        ]
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        env = {"MCP_AUTO_UP_SHARDS": "1", "MCP_AUTO_RECREATE_SHARDS": "1"}
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False):
            for key in keys:
                os.environ.pop(key, None)
            os.environ.update(env)
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 36),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 1000),
            ):
                self.assertTrue(_env_shard_lifecycle_blocked_by_context())
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())
                self.assertFalse(_can_auto_manage_local_shards())

    def test_small_targeted_run_ignores_env_lifecycle_opt_in_without_command_allow(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
        )
        env = {
            "MCP_AUTO_UP_SHARDS": "1",
            "MCP_AUTO_RECREATE_SHARDS": "1",
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SMALL_RUN_SHARD_THRESHOLD": "10",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
            "MCP_SMALL_RUN_ALLOW_SHARD_LIFECYCLE": "1",
            "MCP_ALLOW_ENV_SHARD_LIFECYCLE": "1",
            "MCP_SHARD_HOST": "127.0.0.1",
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 5),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 5),
            ):
                self.assertTrue(_small_run_shard_lifecycle_blocked())
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())
                self.assertFalse(_can_auto_manage_local_shards())

    def test_small_targeted_run_allows_command_level_lifecycle_opt_in(self):
        args = Namespace(
            auto_up_shards=True,
            no_auto_up_shards=False,
            auto_recreate_shards=True,
            no_auto_recreate_shards=False,
            reuse_shards_only=False,
            allow_goal_shard_lifecycle=True,
        )
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_SMALL_RUN_SHARD_THRESHOLD": "10",
            "MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD": "36",
            "MCP_SHARD_HOST": "127.0.0.1",
        }
        with patch.dict(os.environ, env, clear=False):
            with (
                patch.object(expert_main_module, "_CLI_ARGS", args),
                patch.object(expert_main_module, "_PARALLEL", 5),
                patch.object(expert_main_module, "_INPUT_POST_COUNT", 5),
            ):
                self.assertFalse(_small_run_shard_lifecycle_blocked())
                self.assertTrue(_allow_local_shard_auto_up())
                self.assertTrue(_allow_local_shard_recreate())
                self.assertTrue(_can_auto_manage_local_shards())

    def test_reuse_shards_only_overrides_lifecycle_opt_in(self):
        args = Namespace(
            auto_up_shards=True,
            no_auto_up_shards=False,
            auto_recreate_shards=True,
            no_auto_recreate_shards=False,
            reuse_shards_only=True,
        )
        with patch.dict(os.environ, {"MCP_AUTO_UP_SHARDS": "1", "MCP_AUTO_RECREATE_SHARDS": "1"}, clear=False):
            with patch.object(expert_main_module, "_CLI_ARGS", args):
                self.assertFalse(_allow_local_shard_auto_up())
                self.assertFalse(_allow_local_shard_recreate())

    def test_reuse_shards_only_autogen_filters_to_healthy_endpoints(self):
        args = Namespace(
            auto_up_shards=False,
            no_auto_up_shards=False,
            auto_recreate_shards=False,
            no_auto_recreate_shards=False,
            reuse_shards_only=True,
        )
        endpoints = [
            "http://127.0.0.1:3333",
            "http://127.0.0.1:3334",
            "http://127.0.0.1:3335",
        ]
        env = {
            "MCP_ENDPOINTS_AUTOGEN": "1",
            "MCP_ENDPOINTS": ",".join(endpoints),
            "MCP_ENDPOINT": endpoints[0],
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(expert_main_module, "_CLI_ARGS", args), patch.object(expert_main_module, "_PARALLEL", 24):
                filtered, meta = _apply_reuse_only_healthy_endpoint_filter(
                    endpoints,
                    {
                        endpoints[0]: {"ok": True},
                        endpoints[2]: {"ok": True},
                    },
                )

                self.assertEqual(filtered, [endpoints[0], endpoints[2]])
                self.assertEqual(expert_main_module._PARALLEL, 2)
                self.assertEqual(os.environ["MCP_ENDPOINTS"], ",".join(filtered))
                self.assertEqual(os.environ["MCP_ENDPOINT"], endpoints[0])
                self.assertTrue(meta["mcp_reuse_shards_only_health_filtered"])
                self.assertEqual(meta["mcp_requested_endpoint_count_before_health_filter"], 3)
                self.assertEqual(meta["mcp_healthy_endpoint_count"], 2)
                self.assertEqual(meta["mcp_parallel_before_health_filter"], 24)
                self.assertEqual(meta["mcp_parallel_after_health_filter"], 2)


if __name__ == "__main__":
    unittest.main()
