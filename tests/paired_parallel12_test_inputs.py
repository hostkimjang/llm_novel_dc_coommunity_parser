"""v4 합성 계약 입력. 실제80·provider 결과·품질 정답을 만들지 않는다."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path

from llm_batch.measurement import paired_execution_policy as policy
from llm_batch.measurement import paired_measurement_readback as reader
from tests import test_paired_measurement_low_load as original
from tests import test_paired_measurement_readback as legacy


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reseal_bundle(bundle):
    bundle["start"] = policy.seal_execution_observation(bundle["start"])
    bundle["end"]["start_observation_sha256"] = bundle["start"]["observation_sha256"]
    bundle["end"] = policy.seal_execution_observation(bundle["end"])


def low12(root, *, count=2, overlap=True):
    low = original._synthetic_low_load(root)
    original_observations = low["observation_factory"]
    config = low["execution_config"]
    config["settings"]["requested_parallel"]["value"] = 12
    config.update(requested_parallel=12, effective_parallel=min(12, count))
    frozen = policy.build_low_load_policy(policy_id="SYNTHETIC_PARALLEL12_ONLY",
        config_projection=policy.execution_config_projection(config, runtime_fields=low["runtime_fields"],
            projection_schema=policy.PARALLEL12_PROJECTION_SCHEMA, input_post_count=count))
    ref = policy.write_execution_policy(frozen, root / "parallel12_policy.json")
    low["policy"] = frozen
    low["policy_binding"] = {"schema_version": reader.EXECUTION_POLICY_BINDING_SCHEMA_VERSION,
        **{key: ref[key] for key in ("path", "file_sha256", "policy_sha256")}}
    low["run_spec_schema"] = reader.PARALLEL12_RUN_SPEC_SCHEMA_VERSION

    def observations(arm, run_id, descriptor, *, index=None, post_id=None):
        bundle = original_observations(arm, run_id, descriptor, index=index, post_id=post_id)
        for phase in ("start", "end"):
            bundle[phase].update(policy_sha256=frozen["policy_sha256"],
                config_projection=deepcopy(frozen["config_projection"]),
                config_projection_sha256=frozen["config_projection_sha256"])
        if overlap and index == 1:
            # 첫 행이 두 번째 행보다 늦게 끝나며, 두 행이 실제로 겹치는 합성 관측.
            bundle["end"]["monotonic_ns"] += 200
            instant = datetime.fromisoformat(bundle["end"]["observed_at"])
            bundle["end"]["observed_at"] = (instant + timedelta(milliseconds=200)).isoformat()
        reseal_bundle(bundle)
        return bundle

    low["observation_factory"] = observations
    return low


def paired12(root, *, overlap=True):
    low = low12(root, overlap=overlap)
    before, after, wal, spec = legacy.PairedMeasurementReadbackTests()._fixture(root, low_load=low)
    return before, after, wal, spec, low
