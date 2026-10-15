"""명시적으로 결속한 저부하 paired 실행의 시작·행·종료 관측."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import threading
from typing import Mapping

from ..measurement.paired_execution_policy import (
    canonical_sha256, capture_execution_observation, endpoint_pool_fingerprint,
    execution_config_projection, read_execution_policy, validate_execution_observation_pair, PARALLEL12_POLICY_SCHEMA,
)


def generation_fingerprint(client, environment: Mapping[str, str]) -> str:
    """실제 client 기본값과 동적 sampling override만 지문화한다. 비밀값은 출력하지 않는다."""
    attributes = ('backend', 'server_type', 'profile', 'chat_format', 'temperature', 'top_p',
                  'min_p', 'repeat_penalty', 'max_tokens', 'json_grammar', 'think_stream',
                  'enable_thinking', 'stream', 'timeout_s', 'max_retries', 'retry_base_delay')
    dynamic_keys = ('LLM_VLLM_TOP_K', 'LLM_VLLM_PRESENCE_PENALTY', 'LLM_REASON_REVIEW_MAX_TOKENS',
                    'LLM_CONTEXT_LIMIT_TOKENS', 'LLM_N_CTX', 'LLM_ABORT_AFTER_JSON',
                    'LLM_POST_JSON_PIECE_CAP', 'LLM_POST_JSON_CHAR_CAP', 'LLM_ACC_HARD_CAP')
    dynamic = {key: environment.get(key) for key in dynamic_keys}
    dynamic.update({key: value for key, value in environment.items() if key.startswith('LLM_TEMP_')})
    return canonical_sha256({'schema_version': 'paired_generation_settings_v1',
                             'client': {key: getattr(client, key) for key in attributes}, 'dynamic': dynamic})


def prompt_fingerprint(root: Path) -> str:
    paths = sorted((root / 'src/llm_batch/prompts').glob('*.py'))
    if not paths:
        raise ValueError('paired prompt source files missing')
    return canonical_sha256({path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in paths})


class FreshHealthProbe:
    """고정 endpoint pool을 직렬 재검사한다. 과거 관측의 시각만 갱신하지 않는다."""
    def __init__(self, *, endpoints, checker, max_age_seconds):
        self._endpoints = endpoints
        self._checker = checker
        self._max_age = max_age_seconds
        self._health = None
        self._lock = threading.RLock()

    def __call__(self):
        with self._lock:
            endpoints = list(self._endpoints())
            pool_sha = endpoint_pool_fingerprint(endpoints)
            now = datetime.now(timezone.utc)
            if self._health is not None:
                age = (now - datetime.fromisoformat(self._health['observed_at'])).total_seconds()
                if self._health['endpoint_pool_sha256'] != pool_sha:
                    raise ValueError('paired endpoint pool changed')
                if 0 <= age < max(0, self._max_age - 5):
                    return deepcopy(self._health)
            passed = 0
            for endpoint in endpoints:
                result = self._checker(endpoint)
                if not isinstance(result, Mapping) or result.get('ok') is not True or result.get('search_skipped') is True:
                    raise ValueError('paired fresh search health failed')
                passed += 1
            if not passed:
                raise ValueError('paired health pool empty')
            self._health = {'observed_at': now.isoformat(),
                            'endpoint_pool_sha256': pool_sha, 'ok_count': passed,
                            'failure_count': 0, 'checked_count': passed}
            return deepcopy(self._health)


class PairedExecutionSession:
    """정책과 각 행을 결속하며 오류를 완료로 바꾸지 않는다. 모델 호출은 하지 않는다."""
    def __init__(self, *, measurement, run_id, input_sha256, publication_scope_id,
                 execution_config, runtime_fields, health, input_post_ids=None):
        binding = measurement.get('execution_policy_binding')
        if not isinstance(binding, dict):
            raise ValueError('paired execution policy binding missing')
        loaded = read_execution_policy(binding['path'], expected_sha256=binding['file_sha256'],
                                       expected_policy_sha256=binding['policy_sha256'])
        self.policy = loaded['policy']
        self._parallel12 = self.policy['schema_version'] == PARALLEL12_POLICY_SCHEMA
        self._post_ids = None
        if self._parallel12:
            count = self.policy['config_projection']['input_post_count']
            if (type(input_post_ids) is not list or len(input_post_ids) != count
                    or any(type(pid) not in (int, str) or (type(pid) is int and pid < 0)
                           or (type(pid) is str and (not pid.strip() or pid != pid.strip())) for pid in input_post_ids)
                    or len({canonical_sha256(pid) for pid in input_post_ids}) != count
                    or len({str(pid) for pid in input_post_ids}) != count):
                raise ValueError('parallel12 typed input coverage invalid')
            self._post_ids = tuple(deepcopy(input_post_ids))
        self._file_binding = deepcopy(binding)
        self._binding = {'pair_id': measurement['pair_id'], 'arm': measurement['arm'],
                         'run_id': run_id, 'attempt_id': run_id, 'input_sha256': input_sha256,
                         'publication_scope_id': publication_scope_id}
        self._config, self._runtime, self._health = execution_config, runtime_fields, health
        self._start = self._end = None
        self._rows = {}
        self._completed_rows = set()
        self._used_attempts = set()
        self._lock = threading.RLock()

    def _capture(self, phase, binding, prior=None):
        # 명시 정책 파일을 바꾼 실행은 오래된 메모리 본문으로 계속 통과시키지 않는다.
        read_execution_policy(self._file_binding['path'], expected_sha256=self._file_binding['file_sha256'],
                              expected_policy_sha256=self._file_binding['policy_sha256'])
        health = self._health()
        config, runtime = self._config(), self._runtime()
        receipt = capture_execution_observation(self.policy, config, runtime_fields=runtime,
            binding=binding, phase=phase, health=health, start_observation=prior)
        return receipt, config, runtime

    def start(self):
        with self._lock:
            if self._start is not None:
                raise ValueError('paired run already started')
            self._start, _, _ = self._capture('START', self._binding)

    def start_row(self, *, input_index, post_id, attempt_id):
        with self._lock:
            if self._start is None or self._end is not None:
                raise ValueError('paired run is not active')
            if type(input_index) is not int or input_index < 1 or input_index in self._rows or input_index in self._completed_rows:
                raise ValueError('paired row index already used or invalid')
            if self._parallel12:
                if input_index > len(self._post_ids):
                    raise ValueError('parallel12 row index outside input')
                expected_post = self._post_ids[input_index - 1]
                if type(expected_post) is not type(post_id) or expected_post != post_id:
                    raise ValueError('parallel12 row typed post mismatch')
                if len(self._rows) >= self.policy['config_projection']['effective_parallel']:
                    raise ValueError('parallel12 active row limit exceeded')
            elif self._rows:
                raise ValueError('low-load paired rows must execute sequentially')
            if not isinstance(attempt_id, str) or not attempt_id.strip() or attempt_id in self._used_attempts or attempt_id == self._binding['run_id']:
                raise ValueError('paired row attempt ID invalid or already used')
            binding = {**self._binding, 'attempt_id': attempt_id}
            receipt, _, _ = self._capture('START', binding)
            self._rows[input_index] = (deepcopy(post_id), binding, receipt)
            self._used_attempts.add(attempt_id)

    def finish_row(self, *, input_index, post_id):
        with self._lock:
            if type(input_index) is not int or input_index not in self._rows:
                raise ValueError('paired row was not started')
            expected_post, binding, start = self._rows[input_index]
            if type(expected_post) is not type(post_id) or expected_post != post_id:
                raise ValueError('paired row post mismatch')
            end, config, runtime = self._capture('END', binding, start)
            validate_execution_observation_pair(self.policy, start, end, binding=binding)
            result = {'execution_config': config, 'paired_execution_runtime_fields': runtime,
                      'paired_execution_observation': {
                          'schema_version': 'paired_measurement_row_execution_observation_v1',
                          'input_index': input_index, 'post_id': post_id, 'start': start, 'end': end}}
            del self._rows[input_index]
            self._completed_rows.add(input_index)
            return deepcopy(result)

    def finish(self):
        with self._lock:
            if self._start is None or self._end is not None or self._rows:
                raise ValueError('paired run not started, already ended, or rows unfinished')
            if self._parallel12 and len(self._completed_rows) != len(self._post_ids):
                raise ValueError('parallel12 input rows incomplete')
            end, _, _ = self._capture('END', self._binding, self._start)
            validate_execution_observation_pair(self.policy, self._start, end, binding=self._binding)
            self._end = end

    def manifest_fields(self):
        with self._lock:
            config, runtime = self._config(), self._runtime()
            if canonical_sha256(execution_config_projection(config, runtime_fields=runtime,
                    projection_schema=self.policy['config_projection']['schema_version'],
                    input_post_count=self.policy['config_projection'].get('input_post_count'))) != self.policy['config_projection_sha256']:
                raise ValueError('paired current execution projection changed')
            return {'paired_execution_runtime_fields': deepcopy(runtime),
                    'paired_execution_observation': {'schema_version': 'paired_measurement_execution_observation_bundle_v1',
                        'start': deepcopy(self._start), 'end': deepcopy(self._end)}}
