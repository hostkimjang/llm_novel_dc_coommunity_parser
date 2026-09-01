from __future__ import annotations

"""Append-only review recovery sidecar bound to authoritative publication WAL.

The sidecar is deliberately outside the serialized result, candidate ledger,
publish ledger, and checkpoint.  A proposal can therefore be audited without
changing the already-committed public projection or any publication hash.
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.parse import parse_qs, urlsplit, urlunsplit

from .publication_commit import (
    PublicationCommitError,
    PublicationDecisionCommit,
    validate_publication_result_commit,
)


RECOVERY_ACTIVATION_LEDGER_SCHEMA = "recovery_activation_ledger_v2"
RECOVERY_ACTIVATION_EVENT_TYPE = "PROPOSAL_AUTHORIZED"
RECOVERY_PROPOSAL_KIND = "title_recovery_review"
RECOVERY_OVERLAY_SCHEMA = "title_recovery_review_overlay_v1"
RECOVERY_CAPABILITY_SCOPE = "proposal_authorization_only"
RECOVERY_MODE = "AUDIT_ONLY"
RECOVERY_GENESIS_EVENT_SHA256 = "GENESIS"
RECOVERY_ACTIVATION_TAIL_REPAIR_SCHEMA = "recovery_activation_tail_repair_v1"
DIRECT_OCR_REVIEW_RULE_VERSION = "direct_ocr_review_shadow_v2"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_PROCESS_LOCK_TIMEOUT_SECONDS = 30.0


class RecoveryActivationError(ValueError):
    """Raised when a recovery proposal cannot be safely appended or replayed."""


def _canonical_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_payload(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _sha256(value: Any) -> str:
    raw = json.dumps(
        _canonical_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _hmac_sha256(key: bytes, value: Any) -> str:
    raw = json.dumps(
        _canonical_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hmac.new(key, raw, hashlib.sha256).hexdigest()


def _normalize_hmac_key(value: Any) -> bytes:
    if isinstance(value, bytearray):
        value = bytes(value)
    if not isinstance(value, bytes) or len(value) < 32:
        raise RecoveryActivationError("recovery activation HMAC key must be at least 32 bytes")
    return value


def _normalize_hex64(value: Any, *, field_name: str, optional: bool = False) -> Optional[str]:
    if optional and value in (None, ""):
        return None
    text = str(value or "").strip().lower()
    if not _HEX64.fullmatch(text):
        raise RecoveryActivationError(f"{field_name} must be a lowercase sha256")
    return text


def _normalize_nonempty(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RecoveryActivationError(f"{field_name} must be non-empty")
    return text


def _normalize_post_id(value: Any) -> int | str:
    if isinstance(value, bool) or value in (None, ""):
        raise RecoveryActivationError("post_id must be non-empty")
    if isinstance(value, int):
        if value <= 0:
            raise RecoveryActivationError("post_id must be positive")
        return value
    text = str(value).strip()
    try:
        number = int(text)
    except ValueError:
        return _normalize_nonempty(text, field_name="post_id")
    if number <= 0:
        raise RecoveryActivationError("post_id must be positive")
    return number


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def load_or_create_recovery_activation_hmac_key(path: Path | str) -> bytes:
    """Load or atomically create a scope-local 0600 HMAC key.

    The key is never placed in the result, publication WAL, checkpoint,
    recovery journal, or manifest. Losing the key disables proposal
    verification but cannot affect the base public decision.
    """

    key_path = Path(path)
    try:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(key_path):
            if key_path.exists():
                raw = key_path.read_text(encoding="ascii").strip().lower()
                if not re.fullmatch(r"[0-9a-f]{64}", raw):
                    raise RecoveryActivationError(
                        "recovery activation HMAC key file is invalid"
                    )
                os.chmod(key_path, 0o600)
                if stat.S_IMODE(key_path.stat().st_mode) != 0o600:
                    raise RecoveryActivationError(
                        "recovery activation HMAC key mode must be 0600"
                    )
                return bytes.fromhex(raw)

            key = os.urandom(32)
            payload = (key.hex() + "\n").encode("ascii")
            temporary = key_path.with_name(
                f".{key_path.name}.{os.getpid()}.{threading.get_ident()}."
                f"{time.time_ns()}.tmp"
            )
            descriptor = None
            try:
                descriptor = os.open(
                    str(temporary),
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                written = 0
                while written < len(payload):
                    count = os.write(descriptor, payload[written:])
                    if count <= 0:
                        raise OSError("short recovery HMAC key write")
                    written += count
                os.fsync(descriptor)
                os.close(descriptor)
                descriptor = None
                os.chmod(temporary, 0o600)
                if stat.S_IMODE(temporary.stat().st_mode) != 0o600:
                    raise RecoveryActivationError(
                        "temporary recovery HMAC key mode must be 0600"
                    )
                os.replace(temporary, key_path)
                _fsync_directory(key_path.parent)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            os.chmod(key_path, 0o600)
            if stat.S_IMODE(key_path.stat().st_mode) != 0o600:
                raise RecoveryActivationError(
                    "recovery activation HMAC key mode must be 0600"
                )
            return key
    except RecoveryActivationError:
        raise
    except OSError as exc:
        raise RecoveryActivationError(
            f"recovery activation HMAC key I/O failed: {exc}"
        ) from exc


@contextmanager
def _exclusive_file_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        deadline = time.monotonic() + _PROCESS_LOCK_TIMEOUT_SECONDS
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise RecoveryActivationError(
                            f"recovery activation journal lock timeout: {lock_path}"
                        ) from exc
                    time.sleep(0.01)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise RecoveryActivationError(
                            f"recovery activation journal lock timeout: {lock_path}"
                        ) from exc
                    time.sleep(0.01)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@dataclass(frozen=True, slots=True)
class RecoveryProposal:
    producer: str
    rule_version: str
    activation_reason: str
    raw_candidate_title: str
    canonical_title: str = ""
    candidate_url: str = ""
    canonical_work_id: str = ""
    source_kind: str = ""
    source_locator: str = ""
    source_payload_sha256: Optional[str] = None
    relation_role: str = ""
    evidence_status: str = ""
    media_domain_class: str = ""
    primary_work_status: str = ""
    conflict_count: int = 0
    search_health: str = ""
    legacy_fallback_used: bool = False
    blocker_codes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for field_name in ("producer", "rule_version", "activation_reason"):
            object.__setattr__(
                self,
                field_name,
                _normalize_nonempty(getattr(self, field_name), field_name=field_name),
            )
        if not isinstance(self.raw_candidate_title, str):
            raise RecoveryActivationError("raw_candidate_title must be a string")
        if not isinstance(self.canonical_title, str):
            raise RecoveryActivationError("canonical_title must be a string")
        if not (self.raw_candidate_title.strip() or self.canonical_title.strip()):
            raise RecoveryActivationError("a raw or canonical candidate title is required")
        for field_name in (
            "candidate_url",
            "canonical_work_id",
            "source_kind",
            "source_locator",
            "relation_role",
            "evidence_status",
            "media_domain_class",
            "primary_work_status",
            "search_health",
        ):
            if not isinstance(getattr(self, field_name), str):
                raise RecoveryActivationError(f"{field_name} must be a string")
        object.__setattr__(
            self,
            "source_payload_sha256",
            _normalize_hex64(
                self.source_payload_sha256,
                field_name="source_payload_sha256",
                optional=True,
            ),
        )
        if (
            isinstance(self.conflict_count, bool)
            or not isinstance(self.conflict_count, int)
            or self.conflict_count < 0
        ):
            raise RecoveryActivationError("conflict_count must be a nonnegative int")
        if not isinstance(self.legacy_fallback_used, bool):
            raise RecoveryActivationError("legacy_fallback_used must be boolean")
        object.__setattr__(
            self,
            "blocker_codes",
            tuple(
                dict.fromkeys(
                    str(code or "").strip()
                    for code in self.blocker_codes
                    if str(code or "").strip()
                )
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["blocker_codes"] = list(self.blocker_codes)
        return payload

    @classmethod
    def from_dict(cls, value: Any) -> "RecoveryProposal":
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise RecoveryActivationError("recovery proposal must be an object")
        expected = set(cls.__dataclass_fields__)
        actual = set(value)
        if actual != expected:
            raise RecoveryActivationError(
                "recovery proposal fields mismatch: "
                f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
            )
        payload = dict(value)
        payload["blocker_codes"] = tuple(payload.get("blocker_codes") or ())
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class RecoveryActivationEvent:
    schema_version: str
    event_type: str
    sequence: int
    prev_event_sha256: str
    proposal_id: str
    proposal_kind: str
    overlay_schema: str
    publication_scope_id: str
    input_index: int
    post_id: int | str
    base_decision_id: str
    base_commit_sha256: str
    base_result_sha256: str
    base_stable_result_sha256: str
    base_public_projection_sha256: str
    base_contract_input_fingerprint: Optional[str]
    mode: str
    public_apply: bool
    proposal: RecoveryProposal
    capability_scope: str
    capability_commitment_sha256: str
    authorization_binding_sha256: str
    authorization_signature_sha256: str
    event_sha256: str

    def material_without_event_sha256(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["proposal"] = self.proposal.to_dict()
        payload.pop("event_sha256", None)
        return payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.material_without_event_sha256(),
            "event_sha256": self.event_sha256,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "RecoveryActivationEvent":
        if isinstance(value, cls):
            value.validate()
            return value
        if not isinstance(value, Mapping):
            raise RecoveryActivationError("recovery activation event must be an object")
        expected = set(cls.__dataclass_fields__)
        actual = set(value)
        if actual != expected:
            raise RecoveryActivationError(
                "recovery activation event fields mismatch: "
                f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
            )
        payload = dict(value)
        payload["proposal"] = RecoveryProposal.from_dict(payload.get("proposal"))
        event = cls(**payload)
        event.validate()
        return event

    def validate(self) -> None:
        if self.schema_version != RECOVERY_ACTIVATION_LEDGER_SCHEMA:
            raise RecoveryActivationError("recovery activation schema mismatch")
        if self.event_type != RECOVERY_ACTIVATION_EVENT_TYPE:
            raise RecoveryActivationError("recovery activation event type mismatch")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise RecoveryActivationError("recovery activation sequence must be positive")
        if self.prev_event_sha256 != RECOVERY_GENESIS_EVENT_SHA256:
            _normalize_hex64(self.prev_event_sha256, field_name="prev_event_sha256")
        _normalize_hex64(self.proposal_id, field_name="proposal_id")
        if self.proposal_kind != RECOVERY_PROPOSAL_KIND:
            raise RecoveryActivationError("recovery proposal kind mismatch")
        if self.overlay_schema != RECOVERY_OVERLAY_SCHEMA:
            raise RecoveryActivationError("recovery overlay schema mismatch")
        _normalize_hex64(self.publication_scope_id, field_name="publication_scope_id")
        if isinstance(self.input_index, bool) or not isinstance(self.input_index, int) or self.input_index < 1:
            raise RecoveryActivationError("input_index must be positive")
        _normalize_post_id(self.post_id)
        for field_name in (
            "base_decision_id",
            "base_commit_sha256",
            "base_result_sha256",
            "base_stable_result_sha256",
            "base_public_projection_sha256",
            "capability_commitment_sha256",
            "authorization_binding_sha256",
            "authorization_signature_sha256",
            "event_sha256",
        ):
            _normalize_hex64(getattr(self, field_name), field_name=field_name)
        _normalize_hex64(
            self.base_contract_input_fingerprint,
            field_name="base_contract_input_fingerprint",
            optional=True,
        )
        if self.mode != RECOVERY_MODE or self.public_apply is not False:
            raise RecoveryActivationError("recovery activation must remain AUDIT_ONLY")
        if self.capability_scope != RECOVERY_CAPABILITY_SCOPE:
            raise RecoveryActivationError("recovery capability scope mismatch")
        expected_proposal_id = _sha256(
            {
                "publication_scope_id": self.publication_scope_id,
                "base_decision_id": self.base_decision_id,
                "base_commit_sha256": self.base_commit_sha256,
                "base_result_sha256": self.base_result_sha256,
                "base_stable_result_sha256": self.base_stable_result_sha256,
                "base_public_projection_sha256": self.base_public_projection_sha256,
                "base_contract_input_fingerprint": self.base_contract_input_fingerprint,
                "proposal_kind": self.proposal_kind,
                "overlay_schema": self.overlay_schema,
                "proposal": self.proposal.to_dict(),
            }
        )
        if self.proposal_id != expected_proposal_id:
            raise RecoveryActivationError("recovery proposal id mismatch")
        expected_binding = _sha256(
            {
                "capability_scope": self.capability_scope,
                "capability_commitment_sha256": self.capability_commitment_sha256,
                "proposal_id": self.proposal_id,
                "base_decision_id": self.base_decision_id,
                "base_commit_sha256": self.base_commit_sha256,
                "public_apply": False,
            }
        )
        if self.authorization_binding_sha256 != expected_binding:
            raise RecoveryActivationError("recovery authorization binding mismatch")
        if self.event_sha256 != _sha256(self.material_without_event_sha256()):
            raise RecoveryActivationError("recovery activation event hash mismatch")

    def verify_authorization(self, hmac_key: bytes) -> None:
        key = _normalize_hmac_key(hmac_key)
        expected_signature = _hmac_sha256(
            key,
            {
                "domain": "recovery-activation-authorization-v1",
                "authorization_binding_sha256": self.authorization_binding_sha256,
                "capability_commitment_sha256": self.capability_commitment_sha256,
                "proposal_id": self.proposal_id,
                "base_commit_sha256": self.base_commit_sha256,
            },
        )
        if not hmac.compare_digest(
            self.authorization_signature_sha256,
            expected_signature,
        ):
            raise RecoveryActivationError("recovery authorization signature mismatch")


def verify_recovery_capability(
    event: RecoveryActivationEvent | Mapping[str, Any],
    raw_capability: str,
    *,
    hmac_key: bytes,
) -> bool:
    parsed = RecoveryActivationEvent.from_dict(event)
    if not isinstance(raw_capability, str) or not raw_capability:
        return False
    try:
        parsed.verify_authorization(hmac_key)
    except RecoveryActivationError:
        return False
    return hmac.compare_digest(
        hashlib.sha256(raw_capability.encode("utf-8")).hexdigest(),
        parsed.capability_commitment_sha256,
    )


def derive_review_recovery_capability(
    receipt: PublicationDecisionCommit | Mapping[str, Any],
    proposal: RecoveryProposal | Mapping[str, Any],
    *,
    hmac_key: bytes,
) -> str:
    """Derive a replay-stable token whose scope can only authorize sidecar append.

    This is an integrity capability, not a public-writer credential.  Its
    deterministic derivation makes crash reconciliation idempotent; the raw
    value is never stored in the journal.
    """

    authoritative = (
        receipt
        if isinstance(receipt, PublicationDecisionCommit)
        else PublicationDecisionCommit.from_dict(receipt)
    )
    proposal_value = RecoveryProposal.from_dict(proposal)
    return _hmac_sha256(
        _normalize_hmac_key(hmac_key),
        {
            "domain": "review-recovery-sidecar-capability-v1",
            "capability_scope": RECOVERY_CAPABILITY_SCOPE,
            "publication_scope_id": authoritative.publication_scope_id,
            "base_decision_id": authoritative.decision_id,
            "base_commit_sha256": authoritative.commit_sha256,
            "proposal": proposal_value.to_dict(),
            "public_apply": False,
        }
    )


def _result_identity(result: Mapping[str, Any]) -> Mapping[str, Any]:
    analysis = result.get("analysis_result")
    if isinstance(analysis, Mapping) and isinstance(analysis.get("identity"), Mapping):
        return analysis["identity"]
    identity = result.get("identity")
    return identity if isinstance(identity, Mapping) else {}


def _title_key(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value or "").lower())


def _canonical_detail_identity(value: Any) -> tuple[str, str] | None:
    """Derive a stable platform identity from serialized official detail URLs.

    This is intentionally a parser, not a resolver: no URL is fetched and
    slugs, listing pages, hashes, and unknown hosts never become identities.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme.lower() != "https":
        return None
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if host == "page.kakao.com":
        match = re.fullmatch(r"/content/(\d+)", path)
        if not match:
            return None
        return f"kakao:{match.group(1)}", urlunsplit(("https", host, path, "", ""))
    if host == "series.naver.com" and path == "/novel/detail.series":
        query = parse_qs(parsed.query, keep_blank_values=False)
        values = query.get("productNo")
        if not values or len(values) != 1 or not re.fullmatch(r"\d+", values[0]):
            return None
        canonical = f"https://{host}{path}?productNo={values[0]}"
        return f"naver:{values[0]}", canonical
    if host == "novelpia.com":
        match = re.fullmatch(r"/novel/(\d+)", path)
        if not match:
            return None
        return f"novelpia:{match.group(1)}", urlunsplit(("https", host, path, "", ""))
    return None


def _verified_detail_candidate(candidate: Mapping[str, Any]) -> tuple[str, str] | None:
    if (
        str(candidate.get("source_tier") or "").strip().lower().replace("-", "_")
        != "official_detail"
        or str(candidate.get("page_type") or "").strip().lower()
        not in {"novel_page", "novel", "novel_detail", "detail"}
        or str(candidate.get("content_status") or "").strip().lower()
        not in {"active", "available", "published", "ok", "live", "not_deleted", "not-deleted"}
    ):
        return None
    for field_name in ("heretic_url", "official_url", "canonical_url", "url"):
        identity = _canonical_detail_identity(candidate.get(field_name))
        if identity is not None:
            return identity
    return None


def extract_direct_ocr_review_proposals(
    canonical_result: Mapping[str, Any],
) -> Tuple[RecoveryProposal, ...]:
    """Build review-only proposals from already-serialized explicit OCR evidence.

    Existing PUBLISH rows are immutable to this recovery lane.  The extractor
    also refuses suppressed/background-listing image titles.  It only records
    evidence already present in the canonical WAL result and never performs a
    search, canonical rewrite, or public title selection.
    """

    if not isinstance(canonical_result, Mapping) or canonical_result.get("error"):
        return ()
    identity = _result_identity(canonical_result)
    ledger = identity.get("candidate_ledger")
    ledger = ledger if isinstance(ledger, Mapping) else {}
    decision = identity.get("promotion_decision")
    if not isinstance(decision, Mapping):
        decision = ledger.get("promotion_decision")
    if not isinstance(decision, Mapping) or decision.get("publish_allowed") is not False:
        return ()
    novel_identity = identity.get("novel_identity")
    novel_identity = novel_identity if isinstance(novel_identity, Mapping) else {}
    if (
        identity.get("title_resolution_allowed") is True
        or str(novel_identity.get("official_title") or "").strip()
        or str(novel_identity.get("heretic_url") or "").strip()
    ):
        return ()

    image_catalog = identity.get("image_evidence_catalog")
    if not isinstance(image_catalog, list):
        return ()
    eligible_items: list[tuple[Mapping[str, Any], str, str]] = []
    distinct_keys: set[str] = set()
    for item in image_catalog:
        if not isinstance(item, Mapping):
            continue
        if item.get("background_listing_only") is True:
            continue
        if str(item.get("suppressed_explicit_work_title") or "").strip():
            continue
        title = str(item.get("explicit_work_title") or "").strip()
        title_key = _title_key(title)
        if (
            not title_key
            or item.get("promotion_eligible") is not True
            or str(item.get("evidence_type") or "").strip().lower() != "explicit_text"
            or str(item.get("title_role") or "").strip().lower() != "work_title"
        ):
            continue
        eligible_items.append((item, title, title_key))
        distinct_keys.add(title_key)
    if not eligible_items:
        return ()

    candidates = identity.get("title_candidates")
    candidates = candidates if isinstance(candidates, list) else []
    candidates_by_key: Dict[str, list[Mapping[str, Any]]] = {}
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        key = _title_key(candidate.get("official_title"))
        if key:
            candidates_by_key.setdefault(key, []).append(candidate)

    semantic = identity.get("promotion_gate_state")
    if not isinstance(semantic, Mapping):
        semantic = ledger.get("promotion_gate_state")
    semantic = semantic if isinstance(semantic, Mapping) else {}
    semantic_publication = semantic.get("semantic_publication")
    semantic_publication = (
        semantic_publication if isinstance(semantic_publication, Mapping) else {}
    )
    search_health = identity.get("search_health")
    search_health = search_health if isinstance(search_health, Mapping) else {}
    search_status = str(search_health.get("status") or "UNKNOWN").strip().upper()
    base_reason_codes = [
        str(code or "").strip()
        for code in (decision.get("reason_codes") or [])
        if str(code or "").strip()
    ]
    if search_status == "SEARCH_DEGRADED" and "search_degraded" not in base_reason_codes:
        base_reason_codes.append("search_degraded")
    if len(distinct_keys) > 1 and "multiple_explicit_ocr_titles" not in base_reason_codes:
        base_reason_codes.append("multiple_explicit_ocr_titles")

    proposals: list[RecoveryProposal] = []
    seen_keys: set[str] = set()
    for item, title, title_key in eligible_items:
        if title_key in seen_keys:
            continue
        seen_keys.add(title_key)
        matching_candidates = candidates_by_key.get(title_key, [])
        verified = []
        for candidate in matching_candidates:
            identity = _verified_detail_candidate(candidate)
            if identity is not None:
                verified.append((identity, candidate))
        verified_ids = {identity for identity, _ in verified}
        identity_is_ambiguous = len(verified_ids) > 1
        identity_is_unverified = (
            not matching_candidates
            or not verified
            or any(_verified_detail_candidate(candidate) is None for candidate in matching_candidates)
        )
        if identity_is_ambiguous and "canonical_identity_ambiguous" not in base_reason_codes:
            proposal_blockers = [*base_reason_codes, "canonical_identity_ambiguous"]
        else:
            proposal_blockers = list(base_reason_codes)
        if identity_is_unverified and "canonical_identity_unverified" not in proposal_blockers:
            proposal_blockers.append("canonical_identity_unverified")
        canonical_work_id = ""
        candidate_url = ""
        if (
            not identity_is_ambiguous
            and not identity_is_unverified
            and len(verified_ids) == 1
            and len(verified) == len(matching_candidates)
        ):
            canonical_work_id, candidate_url = sorted(verified_ids)[0]
        relation_roles = sorted(
            {
                str(candidate.get("reference_role") or "candidate").strip()
                for candidate in matching_candidates
            }
        )
        relation_role = (
            relation_roles[0]
            if len(relation_roles) == 1
            else "ambiguous"
            if relation_roles
            else "candidate"
        )
        source_locator = str(item.get("eid") or "").strip()
        if not source_locator:
            block_index = item.get("block_index")
            source_locator = (
                f"image:{block_index}"
                if isinstance(block_index, int) and not isinstance(block_index, bool)
                else "image:unknown"
            )
        proposals.append(
            RecoveryProposal(
                producer="direct_ocr_review_shadow",
                rule_version=DIRECT_OCR_REVIEW_RULE_VERSION,
                activation_reason="hold_with_explicit_direct_ocr_title",
                raw_candidate_title=title,
                canonical_title="",
                candidate_url=candidate_url,
                canonical_work_id=canonical_work_id,
                source_kind="direct_image_ocr",
                source_locator=source_locator,
                source_payload_sha256=_sha256(item),
                relation_role=relation_role,
                evidence_status=str(
                    semantic_publication.get("evidence_status") or "unresolved"
                ).strip(),
                media_domain_class=str(
                    semantic_publication.get("media_domain_class") or ""
                ).strip(),
                primary_work_status=str(
                    semantic_publication.get("primary_work_status") or "unresolved"
                ).strip(),
                conflict_count=max(0, len(distinct_keys) - 1),
                search_health=search_status,
                legacy_fallback_used=False,
                blocker_codes=tuple(proposal_blockers),
            )
        )
    return tuple(proposals)


def _create_event(
    *,
    receipt: PublicationDecisionCommit,
    proposal: RecoveryProposal,
    raw_capability: str,
    hmac_key: bytes,
    sequence: int,
    prev_event_sha256: str,
) -> RecoveryActivationEvent:
    if not isinstance(raw_capability, str) or not raw_capability:
        raise RecoveryActivationError("raw recovery capability must be non-empty")
    proposal_id = _sha256(
        {
            "publication_scope_id": receipt.publication_scope_id,
            "base_decision_id": receipt.decision_id,
            "base_commit_sha256": receipt.commit_sha256,
            "base_result_sha256": receipt.result_sha256,
            "base_stable_result_sha256": receipt.stable_result_sha256,
            "base_public_projection_sha256": receipt.public_projection_sha256,
            "base_contract_input_fingerprint": receipt.contract_input_fingerprint,
            "proposal_kind": RECOVERY_PROPOSAL_KIND,
            "overlay_schema": RECOVERY_OVERLAY_SCHEMA,
            "proposal": proposal.to_dict(),
        }
    )
    capability_commitment = hashlib.sha256(raw_capability.encode("utf-8")).hexdigest()
    authorization_binding = _sha256(
        {
            "capability_scope": RECOVERY_CAPABILITY_SCOPE,
            "capability_commitment_sha256": capability_commitment,
            "proposal_id": proposal_id,
            "base_decision_id": receipt.decision_id,
            "base_commit_sha256": receipt.commit_sha256,
            "public_apply": False,
        }
    )
    authorization_signature = _hmac_sha256(
        _normalize_hmac_key(hmac_key),
        {
            "domain": "recovery-activation-authorization-v1",
            "authorization_binding_sha256": authorization_binding,
            "capability_commitment_sha256": capability_commitment,
            "proposal_id": proposal_id,
            "base_commit_sha256": receipt.commit_sha256,
        },
    )
    material = {
        "schema_version": RECOVERY_ACTIVATION_LEDGER_SCHEMA,
        "event_type": RECOVERY_ACTIVATION_EVENT_TYPE,
        "sequence": sequence,
        "prev_event_sha256": prev_event_sha256,
        "proposal_id": proposal_id,
        "proposal_kind": RECOVERY_PROPOSAL_KIND,
        "overlay_schema": RECOVERY_OVERLAY_SCHEMA,
        "publication_scope_id": receipt.publication_scope_id,
        "input_index": receipt.input_index,
        "post_id": receipt.post_id,
        "base_decision_id": receipt.decision_id,
        "base_commit_sha256": receipt.commit_sha256,
        "base_result_sha256": receipt.result_sha256,
        "base_stable_result_sha256": receipt.stable_result_sha256,
        "base_public_projection_sha256": receipt.public_projection_sha256,
        "base_contract_input_fingerprint": receipt.contract_input_fingerprint,
        "mode": RECOVERY_MODE,
        "public_apply": False,
        "proposal": proposal.to_dict(),
        "capability_scope": RECOVERY_CAPABILITY_SCOPE,
        "capability_commitment_sha256": capability_commitment,
        "authorization_binding_sha256": authorization_binding,
        "authorization_signature_sha256": authorization_signature,
    }
    event = RecoveryActivationEvent(
        **{key: value for key, value in material.items() if key != "proposal"},
        proposal=proposal,
        event_sha256=_sha256(material),
    )
    event.validate()
    return event


def _activation_key(
    *,
    publication_scope_id: str,
    input_index: int,
    post_id: int | str,
    proposal: RecoveryProposal,
) -> str:
    return _sha256(
        {
            "publication_scope_id": publication_scope_id,
            "input_index": input_index,
            "post_id": post_id,
            "proposal_kind": RECOVERY_PROPOSAL_KIND,
            "overlay_schema": RECOVERY_OVERLAY_SCHEMA,
            "proposal": proposal.to_dict(),
        }
    )


class RecoveryActivationRegistry:
    """Process-safe append-only CAS journal for audit-only recovery proposals."""

    def __init__(
        self,
        path: Path | str,
        *,
        publication_scope_id: str,
        hmac_key: bytes,
    ) -> None:
        self.path = Path(path)
        self.publication_scope_id = str(
            _normalize_hex64(publication_scope_id, field_name="publication_scope_id")
        )
        self.hmac_key = _normalize_hmac_key(hmac_key)
        self.tail_repair_path = self.path.with_name(
            self.path.name + ".tail_repair.jsonl"
        )
        self._tail_repair_count = 0
        self._events: list[RecoveryActivationEvent] = []
        self._by_proposal_id: Dict[str, RecoveryActivationEvent] = {}
        self._by_activation_key: Dict[str, RecoveryActivationEvent] = {}
        try:
            with _exclusive_file_lock(self.path):
                self._load(repair_unterminated_tail=True)
        except RecoveryActivationError:
            raise
        except OSError as exc:
            raise RecoveryActivationError(
                f"recovery activation journal I/O failed: {exc}"
            ) from exc

    def _parse_events(self, payload: bytes) -> list[RecoveryActivationEvent]:
        events: list[RecoveryActivationEvent] = []
        if not payload:
            return events
        if not payload.endswith(b"\n"):
            raise RecoveryActivationError(
                "recovery activation journal has an unterminated tail"
            )
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RecoveryActivationError(
                "recovery activation journal is not UTF-8"
            ) from exc
        for line_number, raw_line in enumerate(text.splitlines(), 1):
            line = raw_line.strip()
            if not line:
                raise RecoveryActivationError(
                    f"blank recovery activation journal line: {line_number}"
                )
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RecoveryActivationError(
                    f"invalid recovery activation JSON line: {line_number}"
                ) from exc
            event = RecoveryActivationEvent.from_dict(row)
            event.verify_authorization(self.hmac_key)
            events.append(event)
        expected_prev = RECOVERY_GENESIS_EVENT_SHA256
        proposal_ids: set[str] = set()
        for expected_sequence, event in enumerate(events, 1):
            if event.publication_scope_id != self.publication_scope_id:
                raise RecoveryActivationError("recovery activation scope mismatch")
            if event.sequence != expected_sequence:
                raise RecoveryActivationError("recovery activation sequence gap")
            if event.prev_event_sha256 != expected_prev:
                raise RecoveryActivationError("recovery activation hash chain mismatch")
            if event.proposal_id in proposal_ids:
                raise RecoveryActivationError("duplicate recovery proposal id")
            proposal_ids.add(event.proposal_id)
            expected_prev = event.event_sha256
        return events

    def _record_tail_repair(
        self,
        *,
        original_payload: bytes,
        repaired_payload: bytes,
        removed_tail: bytes,
    ) -> None:
        material = {
            "schema_version": RECOVERY_ACTIVATION_TAIL_REPAIR_SCHEMA,
            "journal": str(self.path),
            "original_size_bytes": len(original_payload),
            "repaired_size_bytes": len(repaired_payload),
            "removed_tail_size_bytes": len(removed_tail),
            "original_sha256": hashlib.sha256(original_payload).hexdigest(),
            "repaired_sha256": hashlib.sha256(repaired_payload).hexdigest(),
            "removed_tail_sha256": hashlib.sha256(removed_tail).hexdigest(),
        }
        receipt = {**material, "repair_sha256": _sha256(material)}
        self.tail_repair_path.parent.mkdir(parents=True, exist_ok=True)
        with self.tail_repair_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    receipt,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(self.tail_repair_path.parent)
        self._tail_repair_count += 1

    def _repair_unterminated_tail(self) -> None:
        if not self.path.exists():
            return
        payload = self.path.read_bytes()
        if not payload or payload.endswith(b"\n"):
            return
        prefix_end = payload.rfind(b"\n") + 1
        repaired_payload = payload[:prefix_end]
        removed_tail = payload[prefix_end:]
        # Validate every completed frame before mutating the file. A corrupt
        # middle frame or completed invalid line is never repaired.
        self._parse_events(repaired_payload)
        with self.path.open("r+b") as handle:
            handle.truncate(prefix_end)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(self.path.parent)
        self._record_tail_repair(
            original_payload=payload,
            repaired_payload=repaired_payload,
            removed_tail=removed_tail,
        )

    def _load(self, *, repair_unterminated_tail: bool = False) -> None:
        if repair_unterminated_tail:
            self._repair_unterminated_tail()
        payload = self.path.read_bytes() if self.path.exists() else b""
        events = self._parse_events(payload)
        self._events = events
        self._by_proposal_id = {event.proposal_id: event for event in events}
        by_activation_key: Dict[str, RecoveryActivationEvent] = {}
        for event in events:
            activation_key = _activation_key(
                publication_scope_id=event.publication_scope_id,
                input_index=event.input_index,
                post_id=event.post_id,
                proposal=event.proposal,
            )
            if activation_key in by_activation_key:
                raise RecoveryActivationError("duplicate recovery activation key")
            by_activation_key[activation_key] = event
        self._by_activation_key = by_activation_key

    def events(self) -> Tuple[RecoveryActivationEvent, ...]:
        return tuple(self._events)

    @property
    def tail_repair_count(self) -> int:
        return self._tail_repair_count

    @staticmethod
    def _assert_event_matches_authoritative_base(
        event: RecoveryActivationEvent,
        receipt: PublicationDecisionCommit,
        proposal: RecoveryProposal,
    ) -> None:
        exact = {
            "publication_scope_id": receipt.publication_scope_id,
            "input_index": receipt.input_index,
            "post_id": receipt.post_id,
            "base_decision_id": receipt.decision_id,
            "base_commit_sha256": receipt.commit_sha256,
            "base_result_sha256": receipt.result_sha256,
            "base_stable_result_sha256": receipt.stable_result_sha256,
            "base_public_projection_sha256": receipt.public_projection_sha256,
            "base_contract_input_fingerprint": receipt.contract_input_fingerprint,
        }
        for field_name, expected in exact.items():
            if getattr(event, field_name) != expected:
                raise RecoveryActivationError(
                    f"existing recovery proposal base mismatch: {field_name}"
                )
        if event.proposal.to_dict() != proposal.to_dict():
            raise RecoveryActivationError("existing recovery proposal payload mismatch")

    def ensure_proposal(
        self,
        *,
        receipt: PublicationDecisionCommit | Mapping[str, Any],
        canonical_result: Mapping[str, Any],
        proposal: RecoveryProposal | Mapping[str, Any],
        raw_capability: str,
    ) -> Tuple[RecoveryActivationEvent, bool]:
        authoritative = (
            receipt
            if isinstance(receipt, PublicationDecisionCommit)
            else PublicationDecisionCommit.from_dict(receipt)
        )
        try:
            validate_publication_result_commit(
                canonical_result,
                authoritative,
                expected_scope_id=self.publication_scope_id,
                expected_input_index=authoritative.input_index,
                expected_post_id=authoritative.post_id,
            )
        except PublicationCommitError as exc:
            raise RecoveryActivationError(
                "recovery proposal base publication validation failed"
            ) from exc
        proposal_value = RecoveryProposal.from_dict(proposal)
        preview = _create_event(
            receipt=authoritative,
            proposal=proposal_value,
            raw_capability=raw_capability,
            hmac_key=self.hmac_key,
            sequence=1,
            prev_event_sha256=RECOVERY_GENESIS_EVENT_SHA256,
        )
        try:
            with _exclusive_file_lock(self.path):
                self._load(repair_unterminated_tail=True)
                activation_key = _activation_key(
                    publication_scope_id=authoritative.publication_scope_id,
                    input_index=authoritative.input_index,
                    post_id=authoritative.post_id,
                    proposal=proposal_value,
                )
                existing = self._by_activation_key.get(activation_key)
                if existing is not None:
                    self._assert_event_matches_authoritative_base(
                        existing,
                        authoritative,
                        proposal_value,
                    )
                    if not verify_recovery_capability(
                        existing,
                        raw_capability,
                        hmac_key=self.hmac_key,
                    ):
                        raise RecoveryActivationError(
                            "existing recovery proposal capability mismatch"
                        )
                    return existing, False
                sequence = len(self._events) + 1
                prev_event_sha256 = (
                    self._events[-1].event_sha256
                    if self._events
                    else RECOVERY_GENESIS_EVENT_SHA256
                )
                event = _create_event(
                    receipt=authoritative,
                    proposal=proposal_value,
                    raw_capability=raw_capability,
                    hmac_key=self.hmac_key,
                    sequence=sequence,
                    prev_event_sha256=prev_event_sha256,
                )
                self.path.parent.mkdir(parents=True, exist_ok=True)
                serialized = (
                    json.dumps(
                        event.to_dict(),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(serialized)
                    handle.flush()
                    os.fsync(handle.fileno())
                _fsync_directory(self.path.parent)
                self._load(repair_unterminated_tail=True)
                appended = self._by_proposal_id.get(event.proposal_id)
                if appended is None or appended.event_sha256 != event.event_sha256:
                    raise RecoveryActivationError(
                        "recovery activation append readback mismatch"
                    )
                return appended, True
        except RecoveryActivationError:
            raise
        except OSError as exc:
            raise RecoveryActivationError(
                f"recovery activation journal I/O failed: {exc}"
            ) from exc
