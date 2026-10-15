from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from llm_batch.grounding import p0_actual_registry_contract as registry_contract
from llm_batch.grounding import p0_actual_route_contract as route_contract


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "p0_actual_contract_example_v1"
SNAPSHOT_PATH = FIXTURE_DIR / "p0_source_snapshot_registry_example_v1.jsonl"
CLAIM_PATH = FIXTURE_DIR / "p0_source_claim_example_v1.jsonl"


def _payload_text(profile: str, sequence: int) -> str:
    base_name = (
        "p0_payload_generic_fallback_example_05_v1.txt"
        if profile == "GENERIC_FALLBACK"
        else "p0_payload_official_structured_example_01_v1.txt"
    )
    base = (FIXTURE_DIR / base_name).read_text(encoding="utf-8")
    return f"{base}route-source-{sequence:02d}\n"


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rehash_snapshot(row: dict[str, object]) -> dict[str, object]:
    row["capture_receipt_sha256"] = registry_contract._capture_receipt(row)
    row["registry_record_sha256"] = registry_contract._record_sha(
        row, "registry_record_sha256"
    )
    return registry_contract.with_row_hash(row)


def _snapshot(
    template: dict[str, object], profile: str, profile_index: int, sequence: int
) -> dict[str, object]:
    row = deepcopy(template)
    suffix = f"{profile}:{profile_index:02d}"
    registry_id = f"EXAMPLE:ROUTE:REGISTRY:{suffix}"
    payload_text = _payload_text(profile, sequence)
    payload_raw = payload_text.encode("utf-8")
    row.update(
        {
            "registry_record_id": registry_id,
            "source_id": f"EXAMPLE:ROUTE:SOURCE:{suffix}",
            "snapshot_id": f"EXAMPLE:ROUTE:SNAPSHOT:{suffix}",
            "canonical_url": f"https://official-example.invalid/route/{sequence:02d}",
            "locator": f"route:{sequence:02d}",
            "response_bytes": len(payload_raw),
            "response_sha256": hashlib.sha256(payload_raw).hexdigest(),
            "normalized_text_sha256": hashlib.sha256(payload_raw).hexdigest(),
            "payload_ref": f"route_payload_{sequence:02d}.txt",
            "lineage_root_id": registry_id,
            "parent_registry_record_id": None,
            "derivation_kind": "ORIGINAL",
            "independence_group_id": f"EXAMPLE:ROUTE:GROUP:{suffix}",
            "independence_status": "ELIGIBLE_ROOT",
            "lineage_review_status": "VERIFIED",
            "lineage_reason_codes": ["lineage_original_verified"],
            "source_profile": profile,
            "parser_route": (
                "generic_queue"
                if profile == "GENERIC_FALLBACK"
                else "structured_profile"
            ),
        }
    )
    return _rehash_snapshot(row)


def _claim(
    template: dict[str, object],
    source: dict[str, object],
    claim_id: str,
) -> dict[str, object]:
    row = deepcopy(template)
    row.update(
        {
            "claim_id": claim_id,
            "registry_record_id": source["registry_record_id"],
            "registry_record_sha256": source["registry_record_sha256"],
            "snapshot_id": source["snapshot_id"],
            "parser_profile": str(source["source_profile"]).lower(),
            "parser_run_id": "EXAMPLE:ROUTE:PARSER:01",
        }
    )
    row["claim_evidence_receipt_sha256"] = registry_contract._claim_receipt(
        row, str(source["response_sha256"])
    )
    return registry_contract.with_row_hash(row)


def _plan(
    sources: list[dict[str, object]],
    *,
    origin: str = route_contract.EXAMPLE_ORIGIN,
) -> dict[str, object]:
    selected = route_contract.selected_input_projection(
        sources, expected_origin=origin
    )
    return route_contract.with_artifact_hash(
        {
            "schema_version": route_contract.SOURCE_INPUT_PLAN_SCHEMA,
            "record_origin": origin,
            "plan_id": "EXAMPLE:ROUTE:PLAN:01",
            "selection_method": "CALLER_PRECOMMITTED_PROFILE_10X4_V1",
            "selection_seed_sha256": route_contract.canonical_sha256(
                "example route selection seed"
            ),
            "required_profiles": list(route_contract.SOURCE_PROFILES),
            "per_profile_quota": 10,
            "input_count": 40,
            "selected_inputs": selected,
            "selected_input_set_sha256": route_contract.canonical_sha256(selected),
            "sampling_frame_sha256": route_contract.canonical_sha256(
                {
                    "selection_seed_sha256": route_contract.canonical_sha256(
                        "example route selection seed"
                    ),
                    "selected_inputs": selected,
                }
            ),
            "created_at": "2025-12-01T00:00:00Z",
            "labels_observed": False,
            "action_applied": False,
            "operational_effect": route_contract.OPERATIONAL_EFFECT,
        }
    )


def _seal(
    plan: dict[str, object],
    sources: list[dict[str, object]],
    claims: list[dict[str, object]],
    *,
    origin: str = route_contract.EXAMPLE_ORIGIN,
    schema_version: str = route_contract.LABEL_BLIND_SEAL_SCHEMA,
    selection_algorithm: str = route_contract.SELECTION_ALGORITHM,
) -> dict[str, object]:
    seed = route_contract.canonical_sha256("example blind claim selection seed")
    source_by_id = {row["registry_record_id"]: row for row in sources}
    candidates = [
        route_contract._blind_claim_projection(
            claim, source_by_id[claim["registry_record_id"]], seed
        )
        for claim in claims
    ]
    selected: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    for profile in route_contract.SOURCE_PROFILES:
        profile_rows = [
            row for row in candidates if row["source_profile"] == profile
        ]
        if selection_algorithm == route_contract.SELECTION_ALGORITHM:
            by_input: dict[str, list[dict[str, object]]] = {}
            for row in profile_rows:
                by_input.setdefault(str(row["registry_record_id"]), []).append(row)
            representatives = [
                min(rows, key=lambda row: str(row["selection_rank_sha256"]))
                for rows in by_input.values()
            ]
        else:
            representatives = profile_rows
        ranked = sorted(
            representatives,
            key=lambda row: row["selection_rank_sha256"],
        )
        chosen = ranked[:10]
        selected.extend(chosen)
        counts[profile] = len(chosen)
    complete = all(count == 10 for count in counts.values())
    return route_contract.with_artifact_hash(
        {
            "schema_version": schema_version,
            "record_origin": origin,
            "seal_id": "EXAMPLE:ROUTE:SEAL:01",
            "source_input_plan_sha256": plan["artifact_sha256"],
            "sampling_frame_sha256": plan["sampling_frame_sha256"],
            "captured_source_registry_sha256": route_contract.canonical_sha256(
                sources
            ),
            "selected_input_set_sha256": plan["selected_input_set_sha256"],
            "claim_selection_policy_sha256": route_contract.canonical_sha256(
                "example claim selection policy"
            ),
            "claim_selection_seed_sha256": seed,
            "selection_algorithm": selection_algorithm,
            "selection_basis_fields": list(route_contract.SELECTION_BASIS_FIELDS),
            "forbidden_label_fields_sha256": (
                route_contract.FORBIDDEN_LABEL_FIELDS_SHA256
            ),
            "observed_claim_unit_count": len(candidates),
            "selected_claim_count": len(selected),
            "selected_claim_units": selected,
            "selected_claim_units_sha256": route_contract.canonical_sha256(selected),
            "selected_profile_counts": counts,
            "selection_complete": complete,
            "labels_observed": False,
            "gold_artifact_sha256": None,
            "annotation_artifact_sha256": None,
            "sealed_at": "2026-09-02T00:01:00Z",
            "action_applied": False,
            "operational_effect": route_contract.OPERATIONAL_EFFECT,
        }
    )


def _terminal(
    source: dict[str, object],
    plan: dict[str, object],
    *,
    disposition: str,
    index: int,
    origin: str = route_contract.EXAMPLE_ORIGIN,
) -> dict[str, object]:
    is_error = disposition == "PARSER_ERROR"
    return route_contract.with_row_hash(
        {
            "schema_version": route_contract.TERMINAL_QUEUE_SCHEMA,
            "record_origin": origin,
            "terminal_id": f"EXAMPLE:ROUTE:TERMINAL:{index:02d}",
            "parser_run_id": "EXAMPLE:ROUTE:PARSER:01",
            "source_input_plan_sha256": plan["artifact_sha256"],
            "registry_record_id": source["registry_record_id"],
            "registry_record_sha256": source["registry_record_sha256"],
            "snapshot_id": source["snapshot_id"],
            "source_profile": source["source_profile"],
            "response_sha256": source["response_sha256"],
            "terminal_disposition": disposition,
            "reason_code": (
                "parser_schema_error"
                if is_error
                else "generic_profile_requires_manual_queue"
            ),
            "error_class": "BoundedParserSchemaError" if is_error else None,
            "error_detail_sha256": (
                route_contract.canonical_sha256(f"error:{index}")
                if is_error
                else None
            ),
            "action_applied": False,
            "operational_effect": route_contract.OPERATIONAL_EFFECT,
        }
    )


class P0ActualRouteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        templates = _jsonl(SNAPSHOT_PATH)
        claims = _jsonl(CLAIM_PATH)
        cls.sources = [
            _snapshot(templates[0], profile, profile_index, sequence)
            for sequence, (profile, profile_index) in enumerate(
                (
                    (profile, profile_index)
                    for profile in route_contract.SOURCE_PROFILES
                    for profile_index in range(1, 11)
                ),
                start=1,
            )
        ]
        cls.plan = _plan(cls.sources)
        structured = [
            row
            for row in cls.sources
            if row["source_profile"] != "GENERIC_FALLBACK"
        ]
        cls.claims = [
            _claim(claims[0], source, f"EXAMPLE:ROUTE:CLAIM:{index:02d}")
            for index, source in enumerate(structured, start=1)
        ]
        # 첫 입력은 1:N 출력을 내므로 typed_input_count와 claim_row_count가 다르다.
        cls.claims.append(
            _claim(claims[1], structured[0], "EXAMPLE:ROUTE:CLAIM:01:B")
        )
        generic = [
            row
            for row in cls.sources
            if row["source_profile"] == "GENERIC_FALLBACK"
        ]
        cls.claims.extend(
            _claim(
                claims[4], source, f"EXAMPLE:ROUTE:CLAIM:GENERIC:{index:02d}"
            )
            for index, source in enumerate(generic, start=1)
        )
        cls.seal = _seal(cls.plan, cls.sources, cls.claims)
        cls.terminals = [
            _terminal(
                source,
                cls.plan,
                disposition="GENERIC_PENDING",
                index=index,
            )
            for index, source in enumerate(generic, start=1)
        ]

    def _bundle(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "source_snapshots": self.sources,
            "input_plan": self.plan,
            "selection_seal": self.seal,
            "source_claims": self.claims,
            "terminal_rows": self.terminals,
            "expected_origin": route_contract.EXAMPLE_ORIGIN,
        }
        values.update(overrides)
        return route_contract.validate_route_bundle(**values)  # type: ignore[arg-type]

    def _actual_materials(self) -> dict[str, object]:
        sources: list[dict[str, object]] = []
        for index, source in enumerate(self.sources, start=1):
            actual = deepcopy(source)
            actual["record_origin"] = route_contract.ACTUAL_ORIGIN
            actual["canonical_url"] = (
                f"https://novelpia.com/route-contract-test/{index:02d}"
            )
            sources.append(_rehash_snapshot(actual))
        source_by_id = {row["registry_record_id"]: row for row in sources}

        claims: list[dict[str, object]] = []
        for claim in self.claims:
            actual = deepcopy(claim)
            source = source_by_id[actual["registry_record_id"]]
            actual["record_origin"] = route_contract.ACTUAL_ORIGIN
            actual["registry_record_sha256"] = source["registry_record_sha256"]
            actual["claim_evidence_receipt_sha256"] = (
                registry_contract._claim_receipt(
                    actual, str(source["response_sha256"])
                )
            )
            claims.append(registry_contract.with_row_hash(actual))

        plan = _plan(sources, origin=route_contract.ACTUAL_ORIGIN)
        seal = _seal(
            plan,
            sources,
            claims,
            origin=route_contract.ACTUAL_ORIGIN,
        )
        generic = [
            row for row in sources if row["source_profile"] == "GENERIC_FALLBACK"
        ]
        terminals = [
            _terminal(
                source,
                plan,
                disposition="GENERIC_PENDING",
                index=index,
                origin=route_contract.ACTUAL_ORIGIN,
            )
            for index, source in enumerate(generic, start=1)
        ]
        return {
            "source_snapshots": sources,
            "input_plan": plan,
            "selection_seal": seal,
            "source_claims": claims,
            "terminal_rows": terminals,
            "expected_origin": route_contract.ACTUAL_ORIGIN,
        }

    def _actual_parser_receipt(
        self,
        materials: dict[str, object],
    ) -> dict[str, object]:
        claims = materials["source_claims"]
        terminals = materials["terminal_rows"]
        seal = materials["selection_seal"]
        assert isinstance(claims, list)
        assert isinstance(terminals, list)
        assert isinstance(seal, dict)
        typed_claims = [row for row in claims if row["claim_kind"] != "UNKNOWN"]
        return route_contract.authority_contract.with_artifact_hash(
            {
                "schema_version": (
                    route_contract.authority_contract.PARSER_RECEIPT_SCHEMA
                ),
                "record_origin": route_contract.authority_contract.ACTUAL_ORIGIN,
                "parser_run_id": "EXAMPLE:ROUTE:PARSER:01",
                "launch_sha256": route_contract.canonical_sha256(
                    "actual route launch"
                ),
                "runtime_status": "COMPLETE",
                "started_at": "2026-08-01T00:00:00Z",
                "completed_at": "2026-08-01T01:00:00Z",
                "capture_manifest_sha256": route_contract.canonical_sha256(
                    "actual route capture"
                ),
                "input_registry_sha256": seal[
                    "captured_source_registry_sha256"
                ],
                "output_claims_sha256": route_contract.canonical_sha256(
                    typed_claims
                ),
                "generic_queue_sha256": route_contract.canonical_sha256(
                    {
                        "terminal_rows": terminals,
                        "generic_claim_rows": [
                            row for row in claims if row["claim_kind"] == "UNKNOWN"
                        ],
                    }
                ),
                "input_count": 40,
                "processed_count": 40,
                "typed_input_count": 30,
                "claim_row_count": 31,
                "generic_count": 10,
                "error_count": 0,
                "network_deny_verified": True,
                "run_root_containment_verified": True,
                "exact_accounting_verified": True,
                "runtime_noninterference_verified": True,
                "action_applied": False,
                "operational_effect": route_contract.OPERATIONAL_EFFECT,
            }
        )

    def test_exact_profile_quota_is_derived_from_source_snapshots(self) -> None:
        self.assertEqual(
            route_contract.validate_exact_profile_quota(
                self.sources, expected_origin=route_contract.EXAMPLE_ORIGIN
            ),
            {profile: 10 for profile in route_contract.SOURCE_PROFILES},
        )

    def test_profile_quota_rejects_39_or_skewed_inputs(self) -> None:
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "exact 10x4"):
            route_contract.validate_exact_profile_quota(
                self.sources[:-1], expected_origin=route_contract.EXAMPLE_ORIGIN
            )

    def test_duplicate_response_content_cannot_launder_independent_roots(self) -> None:
        sources = deepcopy(self.sources)
        sources[-1]["response_sha256"] = sources[0]["response_sha256"]
        sources[-1] = _rehash_snapshot(sources[-1])
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "content hashes"):
            route_contract.validate_exact_profile_quota(
                sources, expected_origin=route_contract.EXAMPLE_ORIGIN
            )

    def test_duplicate_normalized_content_cannot_launder_independent_roots(self) -> None:
        sources = deepcopy(self.sources)
        sources[-1]["normalized_text_sha256"] = sources[0][
            "normalized_text_sha256"
        ]
        sources[-1] = _rehash_snapshot(sources[-1])
        with self.assertRaisesRegex(
            route_contract.P0ActualRouteError, "normalized content hashes"
        ):
            route_contract.validate_exact_profile_quota(
                sources, expected_origin=route_contract.EXAMPLE_ORIGIN
            )

    def test_plan_strictly_binds_snapshot_projection_and_order(self) -> None:
        reordered = deepcopy(self.plan)
        reordered["selected_inputs"][0], reordered["selected_inputs"][1] = (
            reordered["selected_inputs"][1],
            reordered["selected_inputs"][0],
        )
        reordered = route_contract.with_artifact_hash(reordered)
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "sequence"):
            route_contract.validate_source_input_plan(
                reordered, self.sources, expected_origin=route_contract.EXAMPLE_ORIGIN
            )

    def test_plan_rejects_extra_fields(self) -> None:
        plan = {**self.plan, "production_approval": True}
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "fields mismatch"):
            route_contract.validate_source_input_plan(
                plan, self.sources, expected_origin=route_contract.EXAMPLE_ORIGIN
            )

    def test_plan_seed_is_materially_bound_to_sampling_frame(self) -> None:
        plan = deepcopy(self.plan)
        plan["selection_seed_sha256"] = route_contract.canonical_sha256("new seed")
        plan = route_contract.with_artifact_hash(plan)
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "sampling frame"):
            route_contract.validate_source_input_plan(
                plan, self.sources, expected_origin=route_contract.EXAMPLE_ORIGIN
            )

    def test_pre_capture_plan_cannot_be_created_after_capture(self) -> None:
        plan = deepcopy(self.plan)
        plan["created_at"] = "2026-12-01T00:00:00Z"
        plan = route_contract.with_artifact_hash(plan)
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "predate"):
            route_contract.validate_source_input_plan(
                plan, self.sources, expected_origin=route_contract.EXAMPLE_ORIGIN
            )

    def test_selection_seal_rejects_any_label_visibility(self) -> None:
        seal = deepcopy(self.seal)
        seal["labels_observed"] = True
        seal["gold_artifact_sha256"] = route_contract.canonical_sha256("gold")
        seal = route_contract.with_artifact_hash(seal)
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "label blind"):
            route_contract.validate_label_blind_selection_seal(
                seal,
                input_plan=self.plan,
                source_snapshots=self.sources,
                source_claims=self.claims,
                expected_origin=route_contract.EXAMPLE_ORIGIN,
            )

    def test_claim_selection_is_deterministic_and_tamper_evident(self) -> None:
        seal = deepcopy(self.seal)
        seal["selected_claim_units"][0], seal["selected_claim_units"][1] = (
            seal["selected_claim_units"][1],
            seal["selected_claim_units"][0],
        )
        seal["selected_claim_units_sha256"] = route_contract.canonical_sha256(
            seal["selected_claim_units"]
        )
        seal = route_contract.with_artifact_hash(seal)
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "deterministic"):
            route_contract.validate_label_blind_selection_seal(
                seal,
                input_plan=self.plan,
                source_snapshots=self.sources,
                source_claims=self.claims,
                expected_origin=route_contract.EXAMPLE_ORIGIN,
            )

    def test_v1_seal_remains_archivally_valid_but_cannot_complete_v2_route(self) -> None:
        archived = _seal(
            self.plan,
            self.sources,
            self.claims,
            schema_version=route_contract.LABEL_BLIND_SEAL_SCHEMA_V1,
            selection_algorithm=route_contract.SELECTION_ALGORITHM_V1,
        )
        validated = route_contract.validate_label_blind_selection_seal_v1(
            archived,
            input_plan=self.plan,
            source_snapshots=self.sources,
            source_claims=self.claims,
            expected_origin=route_contract.EXAMPLE_ORIGIN,
        )
        self.assertEqual(
            validated["schema_version"], route_contract.LABEL_BLIND_SEAL_SCHEMA_V1
        )
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "schema"):
            route_contract.validate_label_blind_selection_seal(
                archived,
                input_plan=self.plan,
                source_snapshots=self.sources,
                source_claims=self.claims,
                expected_origin=route_contract.EXAMPLE_ORIGIN,
            )
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "schema"):
            self._bundle(selection_seal=archived)

    def test_v1_v2_schema_algorithm_swaps_are_rejected(self) -> None:
        v2_with_v1_algorithm = deepcopy(self.seal)
        v2_with_v1_algorithm["selection_algorithm"] = (
            route_contract.SELECTION_ALGORITHM_V1
        )
        v2_with_v1_algorithm = route_contract.with_artifact_hash(
            v2_with_v1_algorithm
        )
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "algorithm"):
            route_contract.validate_label_blind_selection_seal(
                v2_with_v1_algorithm,
                input_plan=self.plan,
                source_snapshots=self.sources,
                source_claims=self.claims,
                expected_origin=route_contract.EXAMPLE_ORIGIN,
            )

        v1_with_v2_algorithm = _seal(
            self.plan,
            self.sources,
            self.claims,
            schema_version=route_contract.LABEL_BLIND_SEAL_SCHEMA_V1,
            selection_algorithm=route_contract.SELECTION_ALGORITHM_V1,
        )
        v1_with_v2_algorithm["selection_algorithm"] = (
            route_contract.SELECTION_ALGORITHM
        )
        v1_with_v2_algorithm = route_contract.with_artifact_hash(
            v1_with_v2_algorithm
        )
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "algorithm"):
            route_contract.validate_label_blind_selection_seal_v1(
                v1_with_v2_algorithm,
                input_plan=self.plan,
                source_snapshots=self.sources,
                source_claims=self.claims,
                expected_origin=route_contract.EXAMPLE_ORIGIN,
            )

    def test_claim_id_rename_does_not_change_blind_rank_or_selection(self) -> None:
        renamed: list[dict[str, object]] = []
        for index, claim in enumerate(self.claims, start=1):
            copy = deepcopy(claim)
            copy["claim_id"] = f"EXAMPLE:RENAMED:CLAIM:{index:02d}"
            renamed.append(registry_contract.with_row_hash(copy))
        renamed_seal = _seal(self.plan, self.sources, renamed)
        original_units = [
            (row["blind_claim_unit_sha256"], row["selection_rank_sha256"])
            for row in self.seal["selected_claim_units"]
        ]
        renamed_units = [
            (row["blind_claim_unit_sha256"], row["selection_rank_sha256"])
            for row in renamed_seal["selected_claim_units"]
        ]
        self.assertEqual(original_units, renamed_units)

    def test_selected_claim_quota_is_recomputed_through_snapshots(self) -> None:
        self.assertEqual(
            route_contract.validate_exact_claim_profile_quota(
                self.seal["selected_claim_units"],
                self.sources,
                expected_origin=route_contract.EXAMPLE_ORIGIN,
            ),
            {profile: 10 for profile in route_contract.SOURCE_PROFILES},
        )
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "exact 10x4"):
            route_contract.validate_exact_claim_profile_quota(
                self.seal["selected_claim_units"][:-1],
                self.sources,
                expected_origin=route_contract.EXAMPLE_ORIGIN,
            )

    def test_one_prolific_source_cannot_fill_a_profile_selection_quota(self) -> None:
        official_source = next(
            row
            for row in self.sources
            if row["source_profile"] == "OFFICIAL_STRUCTURED"
        )
        retained = [
            deepcopy(row)
            for row in self.claims
            if row["registry_record_id"] != official_source["registry_record_id"]
            and row["parser_profile"] != "official_structured"
        ]
        prolific: list[dict[str, object]] = []
        for index in range(10):
            claim = deepcopy(self.claims[0])
            surface = f"prolific-{index:02d}"
            claim.update(
                {
                    "claim_id": f"EXAMPLE:PROLIFIC:{index:02d}",
                    "registry_record_id": official_source["registry_record_id"],
                    "registry_record_sha256": official_source[
                        "registry_record_sha256"
                    ],
                    "snapshot_id": official_source["snapshot_id"],
                    "span_start": index * 20,
                    "span_end": index * 20 + len(surface),
                    "span_text": surface,
                    "span_sha256": registry_contract.canonical_sha256(surface),
                    "surface_text": surface,
                    "normalized_surface": surface,
                    "target_work_id": f"EXAMPLE:PROLIFIC:WORK:{index:02d}",
                }
            )
            claim["claim_evidence_receipt_sha256"] = (
                registry_contract._claim_receipt(
                    claim, str(official_source["response_sha256"])
                )
            )
            prolific.append(registry_contract.with_row_hash(claim))
        attacked_claims = [*retained, *prolific]
        attacked_seal = _seal(self.plan, self.sources, attacked_claims)

        self.assertFalse(attacked_seal["selection_complete"])
        self.assertEqual(
            attacked_seal["selected_profile_counts"]["OFFICIAL_STRUCTURED"], 1
        )
        selected_ids = {
            row["registry_record_id"]
            for row in attacked_seal["selected_claim_units"]
        }
        self.assertEqual(len(selected_ids), 31)

        seed = str(attacked_seal["claim_selection_seed_sha256"])
        manual_duplicate_credit = [
            route_contract._blind_claim_projection(claim, official_source, seed)
            for claim in prolific
        ]
        manual_duplicate_credit.extend(
            row
            for row in self.seal["selected_claim_units"]
            if row["source_profile"] != "OFFICIAL_STRUCTURED"
        )
        self.assertEqual(
            route_contract.validate_exact_claim_profile_quota(
                manual_duplicate_credit,
                self.sources,
                expected_origin=route_contract.EXAMPLE_ORIGIN,
            ),
            {profile: 10 for profile in route_contract.SOURCE_PROFILES},
        )
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "at most once"):
            route_contract.validate_exact_claim_profile_quota(
                manual_duplicate_credit,
                self.sources,
                expected_origin=route_contract.EXAMPLE_ORIGIN,
                require_distinct_inputs=True,
            )

    def test_exact_one_route_and_one_to_many_claim_accounting(self) -> None:
        receipt = self._bundle()
        self.assertEqual(receipt["input_count"], 40)
        self.assertEqual(receipt["typed_input_count"], 30)
        self.assertEqual(receipt["claim_row_count"], 31)
        self.assertEqual(receipt["observed_claim_unit_count"], 41)
        self.assertEqual(receipt["selected_claim_count"], 40)
        self.assertTrue(receipt["selection_complete"])
        self.assertEqual(
            receipt["selection_seal_schema_version"],
            route_contract.LABEL_BLIND_SEAL_SCHEMA,
        )
        self.assertEqual(
            receipt["selection_algorithm"], route_contract.SELECTION_ALGORITHM
        )
        self.assertEqual(receipt["generic_count"], 10)
        self.assertEqual(receipt["error_count"], 0)
        self.assertTrue(receipt["exact_accounting_verified"])

    def test_missing_route_is_rejected(self) -> None:
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "exactly one"):
            self._bundle(terminal_rows=self.terminals[:-1])

    def test_typed_and_terminal_overlap_is_rejected(self) -> None:
        overlap = _terminal(
            self.sources[0],
            self.plan,
            disposition="PARSER_ERROR",
            index=99,
        )
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "exactly one"):
            self._bundle(terminal_rows=[*self.terminals, overlap])

    def test_claim_sampling_unit_duplicate_cannot_hide_behind_new_id(self) -> None:
        duplicate = deepcopy(self.claims[0])
        duplicate["claim_id"] = "EXAMPLE:ROUTE:CLAIM:DUPLICATE"
        duplicate = registry_contract.with_row_hash(duplicate)
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "sampling unit"):
            self._bundle(source_claims=[*self.claims, duplicate])

    def test_parser_error_receipt_is_valid_but_selection_is_incomplete(self) -> None:
        error_source = self.sources[-1]
        claims = [
            row
            for row in self.claims
            if row["registry_record_id"] != error_source["registry_record_id"]
        ]
        terminals = [*self.terminals[:-1]]
        terminals.append(
            _terminal(
                error_source,
                self.plan,
                disposition="PARSER_ERROR",
                index=10,
            )
        )
        seal = _seal(self.plan, self.sources, claims)
        receipt = self._bundle(
            source_claims=claims,
            terminal_rows=terminals,
            selection_seal=seal,
        )
        self.assertEqual(receipt["error_count"], 1)
        self.assertEqual(receipt["selected_claim_count"], 39)
        self.assertFalse(receipt["selection_complete"])

    def test_generic_terminal_cannot_accept_structured_profile(self) -> None:
        terminal = _terminal(
            self.sources[0],
            self.plan,
            disposition="GENERIC_PENDING",
            index=98,
        )
        with self.assertRaisesRegex(route_contract.P0ActualRouteError, "generic terminal"):
            route_contract.validate_terminal_queue_row(
                terminal, expected_origin=route_contract.EXAMPLE_ORIGIN
            )

    def test_receipt_never_grants_authority_or_production(self) -> None:
        receipt = self._bundle()
        self.assertEqual(receipt["gate_status"], "NO_GO_ROUTE_CONTRACT_ONLY")
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertFalse(receipt["production_approval"])
        self.assertFalse(receipt["full_scan_approval"])
        self.assertFalse(receipt["route_accounting_packet_complete"])
        self.assertIsNone(receipt["parser_launch_sha256"])
        self.assertIsNone(receipt["parser_capture_manifest_sha256"])
        self.assertFalse(receipt["action_applied"])
        self.assertEqual(receipt["operational_effect"], "NONE_SHADOW_ONLY")

    def test_parser_receipt_exposes_launch_capture_and_keeps_witness_fail_closed(
        self,
    ) -> None:
        typed_claims = [
            row for row in self.claims if row["claim_kind"] != "UNKNOWN"
        ]
        generic_claims = [
            row for row in self.claims if row["claim_kind"] == "UNKNOWN"
        ]
        launch_sha = route_contract.canonical_sha256("route launch")
        capture_sha = route_contract.canonical_sha256("route capture")
        runtime = {
            "parser_run_id": "EXAMPLE:ROUTE:PARSER:01",
            "runtime_status": "COMPLETE",
            "completed_at": "2026-08-01T00:00:00Z",
            "launch_sha256": launch_sha,
            "capture_manifest_sha256": capture_sha,
            "input_registry_sha256": self.seal[
                "captured_source_registry_sha256"
            ],
            "output_claims_sha256": route_contract.canonical_sha256(typed_claims),
            "generic_queue_sha256": route_contract.canonical_sha256(
                {
                    "terminal_rows": self.terminals,
                    "generic_claim_rows": generic_claims,
                }
            ),
            "input_count": 40,
            "processed_count": 40,
            "typed_input_count": 30,
            "claim_row_count": 31,
            "generic_count": 10,
            "error_count": 0,
            "exact_accounting_verified": True,
            "runtime_noninterference_verified": False,
        }
        with patch.object(
            route_contract.authority_contract,
            "validate_parser_receipt",
            return_value=runtime,
        ):
            receipt = self._bundle(parser_receipt={})
        self.assertEqual(receipt["parser_launch_sha256"], launch_sha)
        self.assertEqual(receipt["parser_capture_manifest_sha256"], capture_sha)
        self.assertFalse(receipt["parser_runtime_noninterference_verified"])
        self.assertFalse(receipt["route_accounting_packet_complete"])

        runtime["runtime_noninterference_verified"] = True
        with patch.object(
            route_contract.authority_contract,
            "validate_parser_receipt",
            return_value=runtime,
        ):
            receipt = self._bundle(parser_receipt={})
        self.assertTrue(receipt["route_accounting_packet_complete"])
        self.assertEqual(receipt["gate_status"], "NO_GO_ROUTE_CONTRACT_ONLY")

    def test_actual_bundle_requires_parser_receipt_v2(self) -> None:
        materials = self._actual_materials()
        with self.assertRaisesRegex(
            route_contract.P0ActualRouteError,
            "actual route bundle requires parser receipt v2",
        ):
            route_contract.validate_route_bundle(**materials)  # type: ignore[arg-type]

    def test_actual_complete_parser_receipt_verifies_route_not_authority(self) -> None:
        materials = self._actual_materials()
        parser_receipt = self._actual_parser_receipt(materials)
        receipt = route_contract.validate_route_bundle(  # type: ignore[arg-type]
            **materials,
            parser_receipt=parser_receipt,
        )
        self.assertTrue(receipt["parser_receipt_verified"])
        self.assertEqual(receipt["parser_runtime_status"], "COMPLETE")
        self.assertTrue(receipt["parser_runtime_noninterference_verified"])
        self.assertEqual(receipt["input_count"], 40)
        self.assertEqual(receipt["typed_input_count"], 30)
        self.assertEqual(receipt["claim_row_count"], 31)
        self.assertEqual(receipt["generic_count"], 10)
        self.assertEqual(receipt["error_count"], 0)
        self.assertTrue(receipt["exact_accounting_verified"])
        self.assertTrue(receipt["route_accounting_packet_complete"])
        self.assertEqual(receipt["gate_status"], "NO_GO_ROUTE_CONTRACT_ONLY")
        self.assertFalse(receipt["actual_authority_granted"])
        self.assertFalse(receipt["production_approval"])
        self.assertFalse(receipt["full_scan_approval"])

    def test_actual_parser_receipt_hash_tampering_is_rejected(self) -> None:
        materials = self._actual_materials()
        for field in (
            "launch_sha256",
            "capture_manifest_sha256",
            "input_registry_sha256",
            "output_claims_sha256",
        ):
            with self.subTest(field=field):
                parser_receipt = self._actual_parser_receipt(materials)
                parser_receipt[field] = route_contract.canonical_sha256(
                    f"tampered {field}"
                )
                with self.assertRaisesRegex(
                    route_contract.P0ActualRouteError,
                    "parser receipt invalid: parser runtime receipt artifact hash mismatch",
                ):
                    route_contract.validate_route_bundle(  # type: ignore[arg-type]
                        **materials,
                        parser_receipt=parser_receipt,
                    )

        # input/output commitments are also cross-bound after a would-be attacker
        # recomputes the receipt self-hash; this is stronger than self-hash failure.
        for field in ("input_registry_sha256", "output_claims_sha256"):
            with self.subTest(field=f"resealed-{field}"):
                parser_receipt = self._actual_parser_receipt(materials)
                parser_receipt[field] = route_contract.canonical_sha256(
                    f"resealed tampered {field}"
                )
                parser_receipt = (
                    route_contract.authority_contract.with_artifact_hash(
                        parser_receipt
                    )
                )
                with self.assertRaisesRegex(
                    route_contract.P0ActualRouteError,
                    "parser receipt/route artifact binding mismatch",
                ):
                    route_contract.validate_route_bundle(  # type: ignore[arg-type]
                        **materials,
                        parser_receipt=parser_receipt,
                    )

    def test_actual_parser_must_start_after_every_source_capture(self) -> None:
        materials = self._actual_materials()
        parser_receipt = self._actual_parser_receipt(materials)
        parser_receipt["started_at"] = "2025-12-02T00:00:00Z"
        parser_receipt = route_contract.authority_contract.with_artifact_hash(
            parser_receipt
        )
        with self.assertRaisesRegex(
            route_contract.P0ActualRouteError,
            "parser cannot start before every source capture",
        ):
            route_contract.validate_route_bundle(  # type: ignore[arg-type]
                **materials,
                parser_receipt=parser_receipt,
            )

    def test_actual_parser_receipt_binds_generic_claim_rows(self) -> None:
        materials = self._actual_materials()
        parser_receipt = self._actual_parser_receipt(materials)
        claims = deepcopy(materials["source_claims"])
        generic_index = next(
            index
            for index, row in enumerate(claims)
            if row["claim_kind"] == "UNKNOWN"
        )
        generic = claims[generic_index]
        generic["claim_id"] = f'{generic["claim_id"]}:REISSUED'
        generic = registry_contract.with_row_hash(generic)
        claims[generic_index] = generic
        materials["source_claims"] = claims
        materials["selection_seal"] = _seal(
            materials["input_plan"],
            materials["source_snapshots"],
            claims,
            origin=route_contract.ACTUAL_ORIGIN,
        )
        with self.assertRaisesRegex(
            route_contract.P0ActualRouteError,
            "parser receipt/route artifact binding mismatch",
        ):
            route_contract.validate_route_bundle(  # type: ignore[arg-type]
                **materials,
                parser_receipt=parser_receipt,
            )

    def test_route_rejects_claim_level_parser_manifest_substitution(self) -> None:
        materials = self._actual_materials()
        parser_receipt = self._actual_parser_receipt(materials)
        claims = deepcopy(materials["source_claims"])
        claims[0]["parser_manifest_sha256"] = route_contract.canonical_sha256(
            "substituted parser manifest"
        )
        claims[0] = registry_contract.with_row_hash(claims[0])
        materials["source_claims"] = claims
        materials["selection_seal"] = _seal(
            materials["input_plan"],
            materials["source_snapshots"],
            claims,
            origin=route_contract.ACTUAL_ORIGIN,
        )
        typed_claims = [row for row in claims if row["claim_kind"] != "UNKNOWN"]
        parser_receipt["output_claims_sha256"] = route_contract.canonical_sha256(
            typed_claims
        )
        parser_receipt = route_contract.authority_contract.with_artifact_hash(
            parser_receipt
        )
        with self.assertRaisesRegex(
            route_contract.P0ActualRouteError,
            "share one parser manifest and version",
        ):
            route_contract.validate_route_bundle(  # type: ignore[arg-type]
                **materials,
                parser_receipt=parser_receipt,
            )

    def test_selection_seal_must_strictly_follow_parser_completion(self) -> None:
        materials = self._actual_materials()
        parser_receipt = self._actual_parser_receipt(materials)
        parser_receipt["completed_at"] = materials["selection_seal"]["sealed_at"]
        parser_receipt = route_contract.authority_contract.with_artifact_hash(
            parser_receipt
        )
        with self.assertRaisesRegex(
            route_contract.P0ActualRouteError,
            "strictly follow parser completion",
        ):
            route_contract.validate_route_bundle(  # type: ignore[arg-type]
                **materials,
                parser_receipt=parser_receipt,
            )


if __name__ == "__main__":
    unittest.main()
