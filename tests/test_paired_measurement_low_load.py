"""합성 v3 계약 검증: 실제 모델·서비스·비용 측정 자료가 아니다."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.llm_batch.measurement import paired_measurement_readback as reader
import tests.test_paired_measurement_readback as legacy_fixture
from src.llm_batch.measurement.paired_execution_policy import (
    build_low_load_policy, execution_config_projection, endpoint_pool_fingerprint,
    seal_execution_observation, validate_execution_observation_pair, write_execution_policy,
)
from tests.test_paired_measurement_readback import (
    PAIR_ID, PUBLICATION_CONFIG_SHA,
    DECISION_ENVIRONMENT_SHA, _claimed_input_path, _self_hash,
)
from tools.run_paired_measurement_readback import _parser, _exclusive_write_run_spec, render_korean_report


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _synthetic_low_load(root):
    config = {
        "schema_version": "expert_execution_config_v1", "profile": "low-load-validation",
        "settings": {name: {"value": value, "source": "SYNTHETIC_CONTRACT_ONLY"} for name, value in
                     {"vlm": False, "ocr": False, "ledger_mode": "REQUIRED", "context_diagnostics": True,
                      "requested_parallel": 1}.items()},
        "requested_parallel": 1, "effective_parallel": 1, "dashboard": {"enabled": True},
        "compression": {"status": "OFF_NOT_REQUESTED"}, "image_review": {"ready": True},
        "source": {"entry_sha256": "a" * 64, "runtime_source_sha256": "b" * 64,
                   "source_scope": "SELECTED_RUNTIME_FILES"},
    }
    runtime = {
        "llm_model": "paired-test-model", "llm_endpoint": "http://provider",
        "generation_config_sha256": "1" * 64, "prompt_sha256": "2" * 64,
        "publication_config_sha256": PUBLICATION_CONFIG_SHA,
        "publication_decision_environment_sha256": DECISION_ENVIRONMENT_SHA,
        "mcp_endpoint_pool_sha256": endpoint_pool_fingerprint(["http://synthetic-search"]),
        "mcp_health_workers": 1, "mcp_health_probe_batch_size": 1, "mcp_health_required_ok_count": 1,
        "mcp_health_include_search": True, "mcp_health_light_mode": False, "mcp_reuse_shards_only": True,
        "mcp_auto_up_shards": False, "mcp_auto_recreate_shards": False, "mcp_auto_scale_up_missing_shards": False,
        "mutable_context_mode": "FROZEN_OFF", "batch_context_enabled": False,
        "central_slang_db_write_allowed": False, "slang_mode": "OFF", "slang_snapshot_sha256": None,
        "candidate_retrieval_mode": "OFF", "community_knowledge_mode": "OFF", "candidate_reranker_mode": "OFF",
    }
    policy = build_low_load_policy(policy_id="SYNTHETIC_CONTRACT_ONLY",
                                  config_projection=execution_config_projection(config, runtime_fields=runtime))
    ref = write_execution_policy(policy, root / "low_load_policy.json")
    binding = {"schema_version": reader.EXECUTION_POLICY_BINDING_SCHEMA_VERSION,
               "path": ref["path"], "file_sha256": ref["file_sha256"], "policy_sha256": ref["policy_sha256"]}

    def observations(arm, run_id, descriptor, *, index=None, post_id=None):
        origin = datetime(2026, 7, 12, 1, tzinfo=timezone.utc)
        start_at = origin + timedelta(milliseconds=0 if index is None else index * 100)
        end_at = origin + timedelta(milliseconds=1000 if index is None else index * 100 + 50)
        observation_binding = {"pair_id": PAIR_ID, "arm": arm, "run_id": run_id,
            "attempt_id": run_id if index is None else f"{run_id}-row-{index}",
            "input_sha256": descriptor.input_file_sha256, "publication_scope_id": descriptor.publication_scope_id}
        base = {"schema_version": "paired_execution_observation_v1", "binding": observation_binding,
                "policy_sha256": policy["policy_sha256"], "config_projection": policy["config_projection"],
                "config_projection_sha256": policy["config_projection_sha256"],
                "resources": {**policy["resources"], "pid": 1234, "status": "OBSERVED"},
                "health": {"observed_at": "2026-07-12T01:00:00+00:00",
                    "endpoint_pool_sha256": runtime["mcp_endpoint_pool_sha256"],
                    "ok_count": 1, "checked_count": 1, "failure_count": 0}}
        start = seal_execution_observation({**deepcopy(base), "phase": "START",
            "observed_at": start_at.isoformat(), "monotonic_ns": 100 if index is None else 100 + index * 100,
            "start_observation_sha256": None})
        end = seal_execution_observation({**deepcopy(base), "phase": "END",
            "observed_at": end_at.isoformat(), "monotonic_ns": 1000 if index is None else 150 + index * 100,
            "start_observation_sha256": start["observation_sha256"]})
        if index is None:
            return {"schema_version": reader.EXECUTION_OBSERVATION_BUNDLE_SCHEMA_VERSION, "start": start, "end": end}
        return {"schema_version": reader.ROW_EXECUTION_OBSERVATION_SCHEMA_VERSION,
                "input_index": index, "post_id": post_id, "start": start, "end": end}

    return {"execution_config": config, "runtime_fields": runtime, "policy_binding": binding,
            "policy": policy, "observation_factory": observations}


class PairedMeasurementLowLoadTests(unittest.TestCase):
    def _fixture(self, root, *, attempt_id_for=None):
        low = _synthetic_low_load(root)
        if attempt_id_for is None:
            before, after, wal, spec = legacy_fixture.PairedMeasurementReadbackTests()._fixture(root, low_load=low)
        else:
            original_row = legacy_fixture.DecisionCallLedgerRegistry.row_attempt
            original_observations = low["observation_factory"]
            def row_attempt(registry, **kwargs):
                kwargs["row_attempt_id"] = attempt_id_for(kwargs["attempt_run_id"], kwargs["input_index"])
                return original_row(registry, **kwargs)
            def observations(arm, run_id, descriptor, *, index=None, post_id=None):
                bundle = original_observations(arm, run_id, descriptor, index=index, post_id=post_id)
                if index is not None:
                    for phase in ("start", "end"):
                        bundle[phase]["binding"]["attempt_id"] = attempt_id_for(run_id, index)
                    self._reseal_row_observation(bundle)
                return bundle
            low["observation_factory"] = observations
            # 결속을 사후 무시하지 않는다. 실제 writer가 새 row identity/frame/seal/link SHA를 생성한다.
            with patch.object(legacy_fixture.DecisionCallLedgerRegistry, "row_attempt", new=row_attempt):
                before, after, wal, spec = legacy_fixture.PairedMeasurementReadbackTests()._fixture(root, low_load=low)
        return before, after, wal, spec, low

    def _reseal_row_observation(self, bundle):
        bundle["start"] = seal_execution_observation(bundle["start"])
        bundle["end"]["start_observation_sha256"] = bundle["start"]["observation_sha256"]
        bundle["end"] = seal_execution_observation(bundle["end"])

    def _assert_bound_artifacts(self, manifest_path, low):
        manifest = _load(manifest_path)
        ledger = legacy_fixture.read_decision_call_ledger(Path(manifest["decision_call_ledger_path"]))
        self.assertEqual(ledger["gate_status"], "GO")
        self.assertTrue(reader.verify_readback_report_sha256(ledger))
        ledger_rows = {(row["input_index"], row["post_id"]): row for row in ledger["rows"]}
        wal_rows, _ = reader._read_publication_wal(Path(manifest["publication_commit_journal"]),
            publication_scope_id=manifest["publication_scope_id"])
        for index, row in enumerate(_load(manifest["output_file"]), 1):
            coordinate = (index, row["post_id"])
            bundle = row["run_meta"]["paired_execution_observation"]
            binding = {**bundle["start"]["binding"], "attempt_id": ledger_rows[coordinate]["row_attempt_id"]}
            validate_execution_observation_pair(low["policy"], bundle["start"], bundle["end"], binding=binding)
            reader.validate_publication_result_decision(row, wal_rows[coordinate].receipt,
                expected_scope_id=manifest["publication_scope_id"], expected_input_index=index, expected_post_id=row["post_id"])

    def _read(self, before, after, spec):
        return reader.build_paired_measurement_readback(run_spec_path=spec, before_manifest_path=before,
                                                       after_manifest_path=after)

    def test_v3_complete_source_replay_preserves_reference_copy_and_unestimated_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            before, after, wal, spec, low = self._fixture(Path(tmp))
            wal_before = wal.read_bytes()
            with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
                report = self._read(before, after, spec)
                reader.validate_paired_measurement_readback(report, run_spec_path=spec,
                    before_manifest_path=before, after_manifest_path=after)
            self.assertEqual(report["schema_version"], reader.LOW_LOAD_SCHEMA_VERSION)
            self.assertEqual(report["execution_protocol"]["requested_parallel"], 1)
            self.assertEqual(report["execution_protocol"]["observed_row_count_per_arm"], 2)
            self.assertEqual(report["gates"]["low_load_policy_and_start_end_observations"], "GO")
            self.assertEqual(report["counterfactual_reference_copy_cost"]["row_count"], 1)
            self.assertFalse(report["counterfactual_reference_copy_cost"]["production_savings_kpi_eligible"])
            self.assertIsNone(report["non_cost_metrics"]["frozen_actual_accuracy"]["value"])
            self.assertIsNone(report["non_cost_metrics"]["money_cost"]["value"])
            self.assertEqual(wal_before, wal.read_bytes())
            self.assertIn("START_END_OBSERVED", render_korean_report(report))

    def test_v3_resealed_row_attempt_cannot_reuse_another_row_or_run_id(self):
        for arm in ("BEFORE", "AFTER"):
            for fault in ("duplicate", "run_id"):
                with self.subTest(arm=arm, fault=fault), tempfile.TemporaryDirectory() as tmp:
                    target_run = "run-" + arm.lower()
                    def attempt_id_for(run_id, index):
                        if run_id != target_run:
                            return f"{run_id}-row-{index}"
                        return f"{run_id}-row-1" if fault == "duplicate" else run_id
                    before, after, wal, spec, low = self._fixture(Path(tmp), attempt_id_for=attempt_id_for)
                    self._assert_bound_artifacts(before if arm == "BEFORE" else after, low)
                    wal_bytes = wal.read_bytes()
                    message = "row attempt reused" if fault == "duplicate" else "row attempt must differ from run_id"
                    with self.assertRaisesRegex(ValueError, message):
                        self._read(before, after, spec)
                    self.assertEqual(wal_bytes, wal.read_bytes())

    def test_v3_resealed_row_intervals_must_follow_input_order_in_both_clocks(self):
        for arm in ("BEFORE", "AFTER"):
            for clock in ("monotonic", "UTC"):
                with self.subTest(arm=arm, clock=clock), tempfile.TemporaryDirectory() as tmp:
                    before, after, wal, spec, low = self._fixture(Path(tmp))
                    target = before if arm == "BEFORE" else after
                    output_path = Path(_load(target)["output_file"])
                    rows = _load(output_path)
                    first = rows[0]["run_meta"]["paired_execution_observation"]
                    second = rows[1]["run_meta"]["paired_execution_observation"]
                    if clock == "monotonic":
                        second["start"]["monotonic_ns"] = first["end"]["monotonic_ns"] - 1
                    else:
                        second["start"]["observed_at"] = first["start"]["observed_at"]
                    self._reseal_row_observation(second)
                    _save(output_path, rows)
                    self._assert_bound_artifacts(target, low)
                    wal_bytes = wal.read_bytes()
                    with self.assertRaisesRegex(ValueError, "row intervals overlap or reorder by " + clock):
                        self._read(before, after, spec)
                    self.assertEqual(wal_bytes, wal.read_bytes())

    def test_v3_adjacent_rows_allow_equal_end_start_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, spec, low = self._fixture(Path(tmp))
            for target in (before, after):
                output_path = Path(_load(target)["output_file"])
                rows = _load(output_path)
                first_end = rows[0]["run_meta"]["paired_execution_observation"]["end"]
                second = rows[1]["run_meta"]["paired_execution_observation"]
                for field in ("monotonic_ns", "observed_at"):
                    second["start"][field] = first_end[field]
                self._reseal_row_observation(second)
                _save(output_path, rows)
                self._assert_bound_artifacts(target, low)
            report = self._read(before, after, spec)
            self.assertEqual(report["gates"]["low_load_policy_and_start_end_observations"], "GO")

    def test_v3_freeze_and_prebound_require_file_and_policy_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            before, _, _, _, low = self._fixture(Path(tmp))
            value = reader.build_paired_measurement_run_spec(input_path=_claimed_input_path(before),
                source_manifest_path=before, pair_id="new-low-pair", run_spec_schema_version=reader.LOW_LOAD_RUN_SPEC_SCHEMA_VERSION,
                execution_policy_path=low["policy_binding"]["path"])
            path = Path(tmp) / "new_spec.json"
            _exclusive_write_run_spec(path, value)
            with self.assertRaises(FileExistsError):
                _exclusive_write_run_spec(path, value)
            args = dict(run_spec_path=path, file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        self_sha256=value["run_spec_sha256"], pair_id="new-low-pair", arm="BEFORE")
            bound = reader.read_prebound_execution_measurement(**args)
            self.assertEqual(bound["execution_policy"], low["policy"])
            self.assertEqual(bound["expected_measurement_fields"]["execution_policy_binding"], low["policy_binding"])
            for field, bad in (("file_sha256", "0" * 64), ("self_sha256", "0" * 64), ("pair_id", "wrong"), ("arm", "UNKNOWN")):
                with self.subTest(field=field), self.assertRaises(ValueError):
                    reader.read_prebound_execution_measurement(**{**args, field: bad})
            with Path(low["policy_binding"]["path"]).open("ab") as stream:
                stream.write(b" ")
            with self.assertRaises(ValueError):
                reader.read_prebound_execution_measurement(**args)

    def test_builder_is_explicit_and_keeps_cli_default_v1(self):
        self.assertEqual(_parser().parse_args([]).run_spec_schema, reader.LEGACY_RUN_SPEC_SCHEMA_VERSION)
        with tempfile.TemporaryDirectory() as tmp:
            before, _, _, _, low = self._fixture(Path(tmp))
            args = dict(input_path=_claimed_input_path(before), source_manifest_path=before, pair_id=PAIR_ID)
            for schema, policy in ((reader.RUN_SPEC_SCHEMA_VERSION, low["policy_binding"]["path"]),
                                   (reader.LEGACY_RUN_SPEC_SCHEMA_VERSION, low["policy_binding"]["path"]),
                                   (reader.LOW_LOAD_RUN_SPEC_SCHEMA_VERSION, None)):
                with self.subTest(schema=schema), self.assertRaisesRegex(ValueError, "required exclusively"):
                    reader.build_paired_measurement_run_spec(**args, run_spec_schema_version=schema, execution_policy_path=policy)

    def test_reference_source_does_not_require_a_circular_preexisting_paired_arm(self):
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, spec, low = self._fixture(Path(tmp))
            source = _load(before)
            for field in ("execution_config", "paired_execution_runtime_fields", "paired_execution_observation"):
                source.pop(field)
            _save(before, source)
            frozen = reader.build_paired_measurement_run_spec(input_path=_claimed_input_path(before),
                source_manifest_path=before, pair_id="new-pair", run_spec_schema_version=reader.LOW_LOAD_RUN_SPEC_SCHEMA_VERSION,
                execution_policy_path=low["policy_binding"]["path"])
            self.assertEqual(frozen["schema_version"], reader.LOW_LOAD_RUN_SPEC_SCHEMA_VERSION)
            with self.assertRaises(ValueError):
                self._read(before, after, spec)

    def test_builder_source_completion_and_bound_inference_fields_are_not_relaxed(self):
        for field, bad in (("pending_count", 1), ("failed_count", 1), ("flushed_count", 1),
                           ("llm_model", "wrong-model"), ("publication_decision_environment_sha256", "0" * 64),
                           ("requested_parallel", 16)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                before, _, _, _, low = self._fixture(Path(tmp))
                source = _load(before)
                source[field] = bad
                _save(before, source)
                with self.assertRaises(ValueError):
                    reader.build_paired_measurement_run_spec(input_path=_claimed_input_path(before),
                        source_manifest_path=before, pair_id="new-pair", run_spec_schema_version=reader.LOW_LOAD_RUN_SPEC_SCHEMA_VERSION,
                        execution_policy_path=low["policy_binding"]["path"])

    def test_legacy_parallel_one_and_v3_parallel_sixteen_are_rejected_even_after_rehash(self):
        for schema in (reader.LEGACY_RUN_SPEC_SCHEMA_VERSION, reader.RUN_SPEC_SCHEMA_VERSION, reader.LOW_LOAD_RUN_SPEC_SCHEMA_VERSION):
            with self.subTest(schema=schema), tempfile.TemporaryDirectory() as tmp:
                _, _, _, spec, _ = self._fixture(Path(tmp))
                value = _load(spec)
                value["schema_version"] = schema
                if schema != reader.LOW_LOAD_RUN_SPEC_SCHEMA_VERSION:
                    value.pop("execution_policy")
                    value["frozen_conditions"]["shared_measurement_fields"].pop("execution_policy_binding")
                else:
                    value["frozen_conditions"]["runtime_manifest_fields"].update(requested_parallel=16, effective_parallel=2)
                value["run_spec_sha256"] = _self_hash(value, "run_spec_sha256")
                _save(spec, value)
                with self.assertRaisesRegex(ValueError, "requested_parallel"):
                    reader.validate_paired_measurement_run_spec(spec)

    def test_manifest_or_row_missing_observation_and_config_drift_fail_closed(self):
        for owner_kind in ("manifest", "row"):
            for fault in ("missing", "profile", "threads", "end_missing", "policy", "health_stale", "attempt", "phase_reuse"):
                with self.subTest(owner=owner_kind, fault=fault), tempfile.TemporaryDirectory() as tmp:
                    before, after, _, spec, _ = self._fixture(Path(tmp))
                    target = before if owner_kind == "manifest" else Path(_load(before)["output_file"])
                    value = _load(target)
                    owner = value if owner_kind == "manifest" else value[0]["run_meta"]
                    if fault == "missing":
                        owner.pop("paired_execution_observation")
                    elif fault == "profile":
                        owner["execution_config"]["profile"] = "general"
                    else:
                        bundle = owner["paired_execution_observation"]
                        if fault == "end_missing":
                            bundle.pop("end")
                        elif fault == "phase_reuse":
                            bundle["end"] = seal_execution_observation({**bundle["start"], "phase": "END",
                                "start_observation_sha256": bundle["start"]["observation_sha256"]})
                        else:
                            end = bundle["end"]
                            if fault == "threads": end["resources"]["numeric_threads"]["VECLIB_MAXIMUM_THREADS"] = "2"
                            elif fault == "policy": end["policy_sha256"] = "0" * 64
                            elif fault == "health_stale": end["health"]["observed_at"] = "2020-01-01T00:00:00+00:00"
                            elif fault == "attempt": end["binding"]["attempt_id"] = "different-attempt"
                            bundle["end"] = seal_execution_observation(end)
                    _save(target, value)
                    with self.assertRaises(ValueError):
                        self._read(before, after, spec)

    def test_claim_pid_and_row_ledger_coordinate_or_parent_interval_are_bound(self):
        for fault in ("claim_pid", "row_pid", "input_index", "post_id", "row_interval", "runtime_fields"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                before, after, _, spec, _ = self._fixture(Path(tmp))
                manifest = _load(before)
                if fault == "claim_pid":
                    claim_path = Path(manifest["output_attempt_claim"])
                    claim = _load(claim_path)
                    claim["pid"] = 54321
                    _save(claim_path, claim)
                    manifest["output_attempt_claim_sha256"] = hashlib.sha256(claim_path.read_bytes()).hexdigest()
                    _save(before, manifest)
                else:
                    path = Path(manifest["output_file"])
                    rows = _load(path)
                    owner = rows[0]["run_meta"]
                    bundle = owner["paired_execution_observation"]
                    if fault == "runtime_fields":
                        owner["paired_execution_runtime_fields"]["mcp_health_workers"] = 16
                    elif fault in ("input_index", "post_id"):
                        bundle[fault] = 999
                    else:
                        if fault == "row_pid":
                            for phase in ("start", "end"):
                                bundle[phase]["resources"]["pid"] = 54321
                        else:
                            bundle["end"]["monotonic_ns"] = 2000
                        bundle["start"] = seal_execution_observation(bundle["start"])
                        bundle["end"]["start_observation_sha256"] = bundle["start"]["observation_sha256"]
                        bundle["end"] = seal_execution_observation(bundle["end"])
                    _save(path, rows)
                with self.assertRaises(ValueError):
                    self._read(before, after, spec)

    def test_frozen_policy_shape_shared_binding_and_terminal_source_checks_remain_strict(self):
        for fault in ("binding_key", "shared_binding", "source_vlm", "source_health", "source_pending"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                before, after, _, spec, _ = self._fixture(Path(tmp))
                if fault in ("binding_key", "shared_binding"):
                    value = _load(spec)
                    if fault == "binding_key": value["execution_policy"]["extra"] = True
                    else: value["frozen_conditions"]["shared_measurement_fields"]["execution_policy_binding"]["policy_sha256"] = "0" * 64
                    value["run_spec_sha256"] = _self_hash(value, "run_spec_sha256")
                    _save(spec, value)
                else:
                    value = _load(before)
                    field, bad = {"source_vlm": ("vlm_enabled", True), "source_health": ("mcp_health_failure_count", 1),
                                  "source_pending": ("pending_count", 1)}[fault]
                    value[field] = bad
                    _save(before, value)
                with self.assertRaises(ValueError):
                    self._read(before, after, spec)

    def test_policy_mutation_at_final_readback_recheck_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            before, after, _, spec, low = self._fixture(Path(tmp))
            original = reader._assert_ledger_replay_unchanged
            def mutate(arm):
                original(arm)
                if arm.arm == "AFTER":
                    with Path(low["policy_binding"]["path"]).open("ab") as stream:
                        stream.write(b" ")
            with patch.object(reader, "_assert_ledger_replay_unchanged", side_effect=mutate), self.assertRaisesRegex(ValueError, "execution policy changed"):
                self._read(before, after, spec)

    def test_unavailable_or_estimated_provider_usage_never_becomes_actual_cost(self):
        for provenance in ("UNAVAILABLE", "ESTIMATED"):
            with self.subTest(provenance=provenance), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                low = _synthetic_low_load(root)
                before, after, _, spec = legacy_fixture.PairedMeasurementReadbackTests()._fixture(
                    root, low_load=low, usage_provenance=provenance)
                with self.assertRaises(ValueError):
                    self._read(before, after, spec)

    def test_recovery_cannot_invent_a_missing_original_resource_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, after, _, spec, _ = self._fixture(root)
            manifest = _load(before)
            original_bundle = manifest.pop("paired_execution_observation")
            _save(before, manifest)
            artifacts = legacy_fixture.PairedMeasurementReadbackTests()._publish_recovered_arm(
                source_manifest_path=before, run_spec_path=spec, root=root)
            recovered = _load(artifacts["recovered_manifest"])
            recovered["paired_execution_observation"] = original_bundle
            _save(artifacts["recovered_manifest"], recovered)
            with self.assertRaisesRegex(ValueError, "recovered low-load paired_execution_observation"):
                self._read(artifacts["recovered_manifest"], after, spec)
