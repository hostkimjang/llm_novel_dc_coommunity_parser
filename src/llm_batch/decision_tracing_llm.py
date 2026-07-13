"""Non-invasive physical LLM-call tracing for decision rows.

Only canonical digests and provider metadata cross the boundary into the
append-only ledger.  Tracing failures are deliberately isolated from model
call results and make the affected row non-estimable instead.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from .decision_call_events import DecisionCallLedgerRegistry, RowAttemptScope
from .llm.client import LLMClient, RetryAttemptObservation, observe_llm_retry_attempts


T = TypeVar("T")


def _digest(value: Any) -> str:
    def safe(item: Any) -> Any:
        if isinstance(item, dict):
            normalized: Dict[str, Any] = {}
            for key, val in item.items():
                text_key = str(key)
                if text_key in normalized:
                    raise TypeError(
                        f"request mapping key collision after string coercion: {text_key!r}"
                    )
                normalized[text_key] = safe(val)
            return {key: normalized[key] for key in sorted(normalized)}
        if isinstance(item, (list, tuple)):
            return [safe(val) for val in item]
        if isinstance(item, bytes):
            return {"bytes_sha256": hashlib.sha256(item).hexdigest(), "size": len(item)}
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("non-finite float cannot be canonically hashed")
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        raise TypeError(f"unsupported request hash value: {type(item).__name__}")

    encoded = json.dumps(
        safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class DecisionTracingLLMClient(LLMClient):
    """LLMClient preserving base behavior while recording physical attempts."""

    def __init__(
        self,
        *args: Any,
        decision_call_ledger: Optional[DecisionCallLedgerRegistry] = None,
        ledger_registry: Optional[DecisionCallLedgerRegistry] = None,
        **kwargs: Any,
    ) -> None:
        if decision_call_ledger is not None and ledger_registry is not None:
            raise ValueError("provide only one decision call ledger")
        # The base client exposes call metadata as instance attributes.  Mirror
        # those attributes per thread so concurrent expert calls cannot bind a
        # neighbour call's usage/model to the wrong physical terminal.
        self._trace_call_meta = threading.local()
        self._last_usage_global: Optional[Dict[str, Any]] = None
        self._last_usage_provenance_global: Optional[str] = None
        self._last_model_global: Optional[str] = None
        super().__init__(*args, **kwargs)
        self.decision_call_ledger = decision_call_ledger or ledger_registry or DecisionCallLedgerRegistry()
        self._trace_lock = threading.RLock()
        self._active_row: Optional[RowAttemptScope] = None
        self._row_closed = False
        self._row_closing = False
        self._trace_inflight = 0
        self._row_trace_failed = False
        self._trace_errors: List[Dict[str, str]] = []

    @property
    def last_usage(self) -> Optional[Dict[str, Any]]:
        return getattr(self._trace_call_meta, "last_usage", self._last_usage_global)

    @last_usage.setter
    def last_usage(self, value: Optional[Dict[str, Any]]) -> None:
        self._last_usage_global = value
        self._trace_call_meta.last_usage = value

    @property
    def last_usage_provenance(self) -> Optional[str]:
        return getattr(
            self._trace_call_meta,
            "last_usage_provenance",
            self._last_usage_provenance_global,
        )

    @last_usage_provenance.setter
    def last_usage_provenance(self, value: Optional[str]) -> None:
        self._last_usage_provenance_global = value
        self._trace_call_meta.last_usage_provenance = value

    @property
    def last_model(self) -> Optional[str]:
        return getattr(self._trace_call_meta, "last_model", self._last_model_global)

    @last_model.setter
    def last_model(self, value: Optional[str]) -> None:
        self._last_model_global = value
        self._trace_call_meta.last_model = value

    @property
    def trace_errors(self) -> Tuple[Dict[str, str], ...]:
        with self._trace_lock:
            return tuple(dict(item) for item in self._trace_errors)

    def begin_row_attempt(
        self,
        attempt_run_id: str,
        row_attempt_id: str,
        input_index: int,
        post_id: Any,
    ) -> RowAttemptScope:
        with self._trace_lock:
            if self._active_row is not None and not self._row_closed:
                raise RuntimeError("a decision row attempt is already active")
            row = self.decision_call_ledger.row_attempt(
                attempt_run_id=attempt_run_id,
                row_attempt_id=row_attempt_id,
                input_index=input_index,
                post_id=post_id,
            )
            self._active_row = row
            self._row_closed = False
            self._row_closing = False
            self._trace_inflight = 0
            self._row_trace_failed = False
            self._trace_errors = []
            return row

    def seal_row_attempt(self) -> Any:
        with self._trace_lock:
            row = self._require_active_row()
            if self._row_closed or self._row_closing:
                raise RuntimeError("decision row attempt is already closed")
            # Close admission before touching the ledger.  An in-flight
            # provider invocation is not allowed to race a seal; abort it so
            # a late success/fallback cannot become publication evidence.
            self._row_closing = True
            try:
                if self._trace_inflight or self._row_trace_failed:
                    result = self._safe_close_abort(
                        row,
                        "DECISION_TRACE_IN_FLIGHT"
                        if self._trace_inflight
                        else "DECISION_TRACE_NOT_ESTIMABLE",
                    )
                else:
                    try:
                        result = self.decision_call_ledger.seal_row(row)
                    except Exception as exc:
                        self._remember_trace_error(exc, "ROW_SEAL")
                        result = self._safe_close_abort(row, "DECISION_TRACE_WRITE_ERROR")
                self._row_closed = True
                return result
            finally:
                self._row_closing = False

    def abort_row_attempt(self, reason_code: str) -> Any:
        with self._trace_lock:
            row = self._require_active_row()
            if self._row_closed or self._row_closing:
                raise RuntimeError("decision row attempt is already closed")
            self._row_closing = True
            try:
                result = self._safe_close_abort(row, reason_code)
                self._row_closed = True
                return result
            finally:
                self._row_closing = False

    def link_row_publication(self, receipt: Any, decision_id: str) -> Any:
        del receipt  # Receipt ownership stays with the publication WAL.
        with self._trace_lock:
            row = self._require_active_row()
            if not self._row_closed or self._row_closing or self._row_trace_failed:
                raise RuntimeError("publication requires a successfully sealed traced row")
            try:
                return self.decision_call_ledger.link_publication(
                    row, publication_decision_id=decision_id
                )
            except Exception as exc:
                self._remember_trace_error(exc, "PUBLICATION_LINK")
                return None

    def _require_active_row(self) -> RowAttemptScope:
        if self._active_row is None:
            raise RuntimeError("begin_row_attempt must be called before tracing")
        return self._active_row

    def _remember_trace_error(self, exc: Exception, operation: str) -> None:
        material = f"{type(exc).__name__}:{exc}"
        self._trace_errors.append(
            {
                "operation": operation,
                "error_type": type(exc).__name__,
                "error_sha256": hashlib.sha256(material.encode("utf-8", "replace")).hexdigest(),
            }
        )
        self._row_trace_failed = True

    def _safe_close_abort(self, row: RowAttemptScope, reason_code: str) -> Any:
        try:
            return self.decision_call_ledger.abort_row(row, reason_code=reason_code)
        except Exception as exc:
            self._remember_trace_error(exc, "ROW_ABORT")
            return None

    @staticmethod
    def _normalize_stage(tag: str, modality: str) -> Tuple[str, bool]:
        if modality == "VLM":
            return "VLM_OCR", True
        raw = str(tag or "").strip().lower().replace("-", "_").replace(" ", "_")
        # Prefix checks are anchored to a complete known pattern; arbitrary
        # substring matches (e.g. ``not_reason_review``) are intentionally
        # rejected as unknown stages.
        if raw == "reason_review" or raw.startswith("reason_review_"):
            return "REASON_REVIEW", True
        if raw == "page_alive_check" or raw.startswith("page_alive_check_"):
            return "PAGE_ALIVE_CHECK", True
        if raw == "final_semantic_reread" or raw.startswith("final_semantic_reread_"):
            return "FINAL_SEMANTIC_REREAD", True
        if raw == "jury_deliberation" or raw.startswith("jury_deliberation_"):
            return "DELIBERATION", True
        if raw == "arbiter_jury" or raw.startswith("arbiter_jury_"):
            return "DELIBERATION", True
        if raw.startswith("debate_") and raw[len("debate_"):].strip("_"):
            return "DELIBERATION", True
        if raw == "snippet_analyzer":
            return "SNIPPET_ANALYZER", True
        if raw == "page_analyzer":
            return "PAGE_ANALYZER", True
        for name in (
            "gatekeeper", "decoder", "verifier", "arbiter", "critic",
            "discourse", "synthesizer", "deliberation",
        ):
            if raw == name or raw.startswith(name + "_"):
                return name.upper(), True
        # Keep the ledger schema-valid while marking the row non-estimable.
        return "DELIBERATION", False

    @staticmethod
    def _validated_usage(
        value: Any,
        provenance: Any,
    ) -> Tuple[str, Optional[int], Optional[int], Optional[int]]:
        normalized_provenance = str(provenance or "").strip().upper()
        if normalized_provenance not in {"PROVIDER_REPORTED", "ESTIMATED"}:
            return "UNAVAILABLE", None, None, None
        if not isinstance(value, dict):
            return "UNAVAILABLE", None, None, None
        prompt = value.get("prompt_tokens")
        completion = value.get("completion_tokens")
        total = value.get("total_tokens")
        values = (prompt, completion, total)
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in values):
            return "UNAVAILABLE", None, None, None
        if total != prompt + completion:
            return "UNAVAILABLE", None, None, None
        # Some base HTTP paths synthesize an all-zero dictionary when the
        # provider omitted usage.  It is not provider evidence.
        if prompt == completion == total == 0:
            return "UNAVAILABLE", None, None, None
        return normalized_provenance, prompt, completion, total

    @staticmethod
    def _response_is_semantically_valid(
        value: Any,
        modality: str,
        stage: str,
    ) -> bool:
        """Reject provider-success-looking empty/fallback payloads."""
        if value is None:
            return False
        if modality == "VLM":
            return isinstance(value, dict) and bool(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return False
            # Common JSON fallbacks ("{}", "[]") are not expert evidence.
            if text in {"{}", "[]"}:
                return False
            return True
        if isinstance(value, dict):
            if (
                stage == "REASON_REVIEW"
                and str(value.get("llm_review_note") or "").strip()
                == "LLM reason review 실패"
                and not value.get("selected_ids")
                and not str(value.get("primary_reason") or "").strip()
                and not str(value.get("merged_reason") or "").strip()
            ):
                return False
            return bool(value)
        if isinstance(value, (list, tuple, bytes)):
            return bool(value)
        return True

    def _requested_model(self) -> str:
        # Keep requested model provenance explicit even when a caller supplied
        # an empty/None model; provider-reported resolution remains optional.
        value = str(getattr(self, "model", "") or "").strip()
        return value or "UNSPECIFIED_MODEL"

    def _trace_call(
        self,
        *,
        stage_tag: str,
        modality: str,
        request_value: Any,
        invoke: Callable[[], T],
    ) -> T:
        with self._trace_lock:
            row = self._require_active_row()
            if self._row_closed or self._row_closing:
                raise RuntimeError("late model call after decision row closure")
            stage, known_stage = self._normalize_stage(stage_tag, modality)
            if not known_stage:
                self._remember_trace_error(ValueError("unknown decision stage"), "STAGE_NORMALIZATION")
            self._trace_inflight += 1

        # A local/direct provider path may not populate any call metadata.  Do
        # not let it inherit a previous call's thread/global fallback values.
        self._trace_call_meta.last_usage = None
        self._trace_call_meta.last_usage_provenance = None
        self._trace_call_meta.last_model = None

        logical_call_id = f"logical-{uuid.uuid4().hex}"
        try:
            request_sha256 = _digest(request_value)
        except Exception as exc:
            with self._trace_lock:
                self._remember_trace_error(exc, "REQUEST_HASH")
            try:
                return invoke()
            finally:
                with self._trace_lock:
                    self._trace_inflight = max(0, self._trace_inflight - 1)
        calls: Dict[Tuple[str, int], Dict[str, Any]] = {}
        operations: Dict[str, Dict[str, Any]] = {}
        pending_successes: List[Dict[str, Any]] = []
        observed = 0

        def observer(event: RetryAttemptObservation) -> None:
            nonlocal observed
            observed += 1
            operation_id = event.retry_operation_id or "synthetic"
            event_key = (operation_id, event.attempt_number)
            try:
                with self._trace_lock:
                    if self._row_closed or self._row_closing or self._active_row != row:
                        raise RuntimeError("late or cross-row retry observation")
                    if event.event == "ATTEMPT_STARTED":
                        if event_key in calls:
                            raise RuntimeError("duplicate retry operation/attempt start")
                        if isinstance(event.attempt_number, bool) or event.attempt_number <= 0:
                            raise RuntimeError("retry attempt number must be positive")
                        state = operations.setdefault(
                            operation_id,
                            {
                                "logical_call_id": f"logical-{uuid.uuid4().hex}",
                                "next_ordinal": 0,
                                "last_call_id": None,
                            },
                        )
                        ordinal = event.attempt_number - 1
                        if ordinal != state["next_ordinal"]:
                            raise RuntimeError("retry operation ordinal is not contiguous")
                        call_id = f"call-{uuid.uuid4().hex}"
                        calls[event_key] = {
                            "call_id": call_id,
                            "retry_ordinal": ordinal,
                            "logical_call_id": state["logical_call_id"],
                            "operation_id": operation_id,
                        }
                        self._trace_call_meta.last_usage = None
                        self._trace_call_meta.last_usage_provenance = None
                        self._trace_call_meta.last_model = None
                        self.decision_call_ledger.record_dispatch_intent(
                            row,
                            logical_call_id=state["logical_call_id"],
                            call_id=call_id,
                            retry_ordinal=ordinal,
                            retry_of_call_id=state["last_call_id"] if ordinal > 0 else None,
                            stage=stage,
                            modality=modality,
                            requested_model=self._requested_model(),
                            resolved_model=None,
                            endpoint=str(self.endpoint),
                            backend=str(self.backend),
                            request_sha256=request_sha256,
                        )
                        state["next_ordinal"] = ordinal + 1
                        return
                    call_meta = calls.get(event_key)
                    if call_meta is None:
                        raise RuntimeError("retry terminal without dispatch")
                    call_id = str(call_meta["call_id"])
                    if event.event == "ATTEMPT_FAILED":
                        error_sha = (
                            hashlib.sha256(event.error_message.encode("utf-8", "replace")).hexdigest()
                            if event.error_message is not None else None
                        )
                        self.decision_call_ledger.record_terminal(
                            row, call_id=call_id, terminal_status="FAILED",
                            resolved_model=self.last_model or None, response_sha256=None,
                            usage_provenance="UNAVAILABLE", prompt_tokens=None,
                            completion_tokens=None, total_tokens=None,
                            error_type=event.error_type, error_message_sha256=error_sha,
                        )
                        operations[operation_id]["last_call_id"] = call_id
                    elif event.event == "ATTEMPT_SUCCEEDED":
                        # Defer successful terminal frames until invoke returns
                        # so empty fallback payloads can be rejected.  The
                        # observer carries only a hash, never the raw result.
                        pending_successes.append(
                            {
                                "event_key": event_key,
                                "call_id": call_id,
                                "response_sha256": event.result_sha256,
                                "usage": self.last_usage,
                                "usage_provenance": self.last_usage_provenance,
                                "model": self.last_model,
                            }
                        )
            except Exception as exc:
                with self._trace_lock:
                    self._remember_trace_error(exc, event.event)

        try:
            with observe_llm_retry_attempts(observer):
                value = invoke()
        except Exception as exc:
            if observed == 0:
                observer(RetryAttemptObservation("ATTEMPT_STARTED", 1, 1, None))
                observer(RetryAttemptObservation("ATTEMPT_FAILED", 1, 1, False, type(exc).__name__, str(exc)))
            with self._trace_lock:
                self._trace_inflight = max(0, self._trace_inflight - 1)
            raise
        try:
            if observed == 0:
                usage_snapshot = self.last_usage
                usage_provenance_snapshot = self.last_usage_provenance
                model_snapshot = self.last_model
                observer(RetryAttemptObservation("ATTEMPT_STARTED", 1, 1, None))
                self.last_usage = usage_snapshot
                self.last_usage_provenance = usage_provenance_snapshot
                self.last_model = model_snapshot
                observer(
                    RetryAttemptObservation(
                        "ATTEMPT_SUCCEEDED",
                        1,
                        1,
                        None,
                        result_sha256=_digest(value),
                    )
                )
            with self._trace_lock:
                # Re-check after provider invocation and before any terminal
                # append.  A seal/abort or observer error wins the race.
                if self._row_closed or self._row_closing or self._row_trace_failed:
                    self._remember_trace_error(
                        RuntimeError("row closed or trace failed after provider invocation"),
                        "POST_INVOKE_RECHECK",
                    )
                    return value
                digest = _digest(value)
                valid = self._response_is_semantically_valid(value, modality, stage)
                empty_hashes = {_digest({}), _digest([]), _digest("")}
                for pending in pending_successes:
                    response_sha = pending["response_sha256"] or digest
                    call_id = str(pending["call_id"])
                    usage_prov, prompt, completion, total = self._validated_usage(
                        pending["usage"], pending["usage_provenance"]
                    )
                    if not valid or response_sha in empty_hashes:
                        self.decision_call_ledger.record_terminal(
                            row,
                            call_id=call_id,
                            terminal_status="FAILED",
                            resolved_model=pending["model"] or None,
                            response_sha256=None,
                            usage_provenance="UNAVAILABLE",
                            prompt_tokens=None,
                            completion_tokens=None,
                            total_tokens=None,
                            error_type="InvalidProviderResponse",
                            error_message_sha256=hashlib.sha256(
                                b"invalid provider response"
                            ).hexdigest(),
                        )
                    else:
                        self.decision_call_ledger.record_terminal(
                            row,
                            call_id=call_id,
                            terminal_status="SUCCEEDED",
                            resolved_model=pending["model"] or None,
                            response_sha256=response_sha,
                            usage_provenance=usage_prov,
                            prompt_tokens=prompt,
                            completion_tokens=completion,
                            total_tokens=total,
                        )
        except Exception as exc:
            with self._trace_lock:
                self._remember_trace_error(exc, "ATTEMPT_SUCCEEDED")
        finally:
            with self._trace_lock:
                self._trace_inflight = max(0, self._trace_inflight - 1)
        return value

    def _stream_chat_http(
        self, messages: List[Dict[str, Any]], tag: str = "expert", use_grammar: bool = True,
        max_tokens: Optional[int] = None, quiet: bool = False,
        temperature: Optional[float] = None,
    ) -> str:
        request = {
            "messages": messages, "tag": tag, "use_grammar": use_grammar,
            "max_tokens": max_tokens, "quiet": quiet, "temperature": temperature,
        }
        return self._trace_call(
            stage_tag=tag, modality="TEXT", request_value=request,
            invoke=lambda: super(DecisionTracingLLMClient, self)._stream_chat_http(
                messages, tag=tag, use_grammar=use_grammar, max_tokens=max_tokens,
                quiet=quiet, temperature=temperature,
            ),
        )

    def complete_multimodal_json(
        self, system_prompt: str, user_text: str, images: List[Dict[str, Any]], *,
        tag: str = "complete_multimodal_json", max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        # The base client returns immediately for unsupported local/non-vLLM
        # configurations, so there is no physical provider call to count.
        if self.backend == "local" or self.server_type != "vllm":
            return super().complete_multimodal_json(
                system_prompt,
                user_text,
                images,
                tag=tag,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        request = {
            "system_prompt": system_prompt, "user_text": user_text, "images": images,
            "tag": tag, "max_tokens": max_tokens, "temperature": temperature,
        }
        return self._trace_call(
            stage_tag=tag, modality="VLM", request_value=request,
            invoke=lambda: super(DecisionTracingLLMClient, self).complete_multimodal_json(
                system_prompt, user_text, images, tag=tag,
                max_tokens=max_tokens, temperature=temperature,
            ),
        )

    def review_reason_candidates(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._trace_call(
            stage_tag="reason_review", modality="TEXT", request_value=payload,
            invoke=lambda: super(DecisionTracingLLMClient, self).review_reason_candidates(payload),
        )


__all__ = ["DecisionTracingLLMClient"]
