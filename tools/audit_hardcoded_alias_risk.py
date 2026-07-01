from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


TARGET_NAME_RE = re.compile(
    r"(?:ABBREV|ABBREVIATION|ALIAS|BLOCKLIST|QUARANTINE|RESCUE|SLANG|DICTIONARY|STOPLIST|NOISE|PLATFORM|GENERIC_TERM|LOW_INFORMATION|TROPE)",
    re.IGNORECASE,
)
PROMPT_HINT_NAME_RE = re.compile(r"(?:PROMPT|HINT|MAP|ABBREVIATION_MAP)", re.IGNORECASE)

CURATED_REGISTRY_RISK_CLASSES = {
    "KNOWN_ABBREVIATIONS": "positive_resolution",
    "KNOWN_TITLE_ABBREVIATIONS": "positive_resolution",
    "SLANG_DICTIONARY": "positive_resolution",
    "PLATFORM_ABBREVIATION_MAP": "prompt_hint",
    "PLATFORM_ABBREVIATIONS": "prompt_hint",
    "NOISE_TERMS": "quarantine",
    "_COMMUNITY_SLANG": "quarantine",
    "_GENRE_TROPE_KEYWORDS": "quarantine",
    "_GENERIC_TERM_STOPLIST": "quarantine",
    "_LOW_INFORMATION_ALIAS_SURFACES": "quarantine",
}

POSITIVE_REGISTRY_NAMES = {
    "KNOWN_ABBREVIATIONS",
    "KNOWN_TITLE_ABBREVIATIONS",
    "SLANG_DICTIONARY",
}

QUARANTINE_NAME_MARKERS = (
    "BLOCKLIST",
    "QUARANTINE",
    "DENYLIST",
    "STOPLIST",
    "STOPWORDS",
    "LOW_INFORMATION",
    "POISON",
    "COMMON_WORDS_NOT",
)
BOOTSTRAP_NAME_MARKERS = (
    "SEED",
    "BOOTSTRAP",
    "RESCUE",
)
TOOLING_MARKER_NAME_MARKERS = (
    "MARKER",
    "MARKERS",
)

POSITIVE_USAGE_RE = re.compile(
    r"(?:"
    r"resolved_abbreviations|"
    r"official_title\s*=\s*(?!None\b|null\b|[\"']{2})|"
    r"title\s*(?:유지|승격|확정|복구)|"
    r"return\s*\(\s*full_title|"
    r"LLM\s*판단\s*무시|"
    r"최우선|가장\s*신뢰|강한\s*신호|"
    r"매칭\s*면제|화이트리스트|"
    r"register_abbreviation\(|"
    r"known_abbr|known_abbreviation|"
    r"batch_memory_exact_alias_rescued|"
    r"title_surface_primary_candidate_rescued"
    r")",
    re.IGNORECASE,
)

GUARD_OR_EVIDENCE_RE = re.compile(
    r"(?:"
    r"guard|가드|차단|보류|held|pending|quarantine|"
    r"evidence|근거|support|지원|"
    r"official|공식|verified|검증|anchor|앵커|"
    r"final_semantic_reread|semantic_reread|"
    r"nullify|review|검토|"
    r"explicit_alias_bridge|official_detail"
    r")",
    re.IGNORECASE,
)

USAGE_KIND_PATTERNS = {
    "direct_positive_return": re.compile(
        r"(?:return\s*\(\s*full_title|official_title\s*=\s*(?!None\b|null\b|[\"']{2})|confidence.*High|High.*known_abbr|title\s*(?:유지|승격|확정|복구))",
        re.IGNORECASE,
    ),
    "guard_exception_or_lock": re.compile(
        r"(?:exempt|exception|whitelist|화이트리스트|면제|우회|bypass|lock|보호|correction|막|skip.*guard)",
        re.IGNORECASE,
    ),
    "prompt_pressure": re.compile(
        r"(?:prompt|system-verified|확정적|abbreviation_match|가중치|reasoning)",
        re.IGNORECASE,
    ),
    "search_context": re.compile(
        r"(?:search|query|검색|snippet|url|candidate)",
        re.IGNORECASE,
    ),
    "quarantine_support": re.compile(
        r"(?:blocklist|quarantine|stoplist|noise|generic|차단|보류|prune)",
        re.IGNORECASE,
    ),
}

SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    ".venv",
    ".venv312",
    "venv",
    ".tmpvenv",
    "out",
    "logs",
    "qualitative_review",
    "server-poc",
}
SKIP_FILES = {
    "tools/audit_hardcoded_alias_risk.py",
}


@dataclass(frozen=True)
class UsageOccurrence:
    file: str
    line: int
    text: str
    window_excerpt: str
    usage_kinds: tuple[str, ...]
    positive_usage: bool
    guard_usage: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "text": self.text[:220],
            "window_excerpt": self.window_excerpt[:800],
            "usage_kinds": list(self.usage_kinds),
            "positive_usage": self.positive_usage,
            "guard_usage": self.guard_usage,
        }


@dataclass(frozen=True)
class RegistryFinding:
    registry_name: str
    file: str
    line: int
    scope: str
    entry_count: int | None
    risk_class: str
    value_kind: str
    positive_usage: bool
    guard_evidence_support_required: bool
    gate_status: str
    usage_count: int
    positive_usage_count: int
    guard_usage_count: int
    usage_kind_counts: dict[str, int]
    usage_samples: tuple[UsageOccurrence, ...]
    sample_entries: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "registry_name": self.registry_name,
            "file": self.file,
            "line": self.line,
            "scope": self.scope,
            "entry_count": self.entry_count,
            "risk_class": self.risk_class,
            "value_kind": self.value_kind,
            "positive_usage": self.positive_usage,
            "guard_evidence_support_required": self.guard_evidence_support_required,
            "gate_status": self.gate_status,
            "usage_count": self.usage_count,
            "positive_usage_count": self.positive_usage_count,
            "guard_usage_count": self.guard_usage_count,
            "usage_kind_counts": dict(sorted(self.usage_kind_counts.items())),
            "usage_samples": [sample.as_dict() for sample in self.usage_samples],
            "sample_entries": list(self.sample_entries),
        }


@dataclass(frozen=True)
class UsageSummary:
    usage_count: int
    positive_usage_count: int
    guard_usage_count: int
    usage_kind_counts: dict[str, int]
    samples: tuple[UsageOccurrence, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_python_files(root: Path, scan_paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for raw_path in scan_paths:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        if not path.exists():
            continue
        if path.is_file() and path.suffix == ".py":
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in path.rglob("*.py"):
            try:
                relative_parts = child.relative_to(root).parts
                relative_display = child.relative_to(root).as_posix()
            except ValueError:
                relative_parts = child.parts
                relative_display = child.as_posix()
            if relative_display in SKIP_FILES:
                continue
            if any(part in SKIP_DIRS for part in relative_parts):
                continue
            files.append(child)
    return sorted(dict.fromkeys(files))


def _target_name(target: ast.AST) -> str | None:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def _literal_entry_count(value: ast.AST) -> int | None:
    if isinstance(value, ast.Dict):
        return len(value.keys)
    if isinstance(value, (ast.Set, ast.List, ast.Tuple)):
        return len(value.elts)
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return _string_entry_count(value.value)
    return None


def _value_kind(value: ast.AST) -> str:
    if isinstance(value, ast.Dict):
        return "dict"
    if isinstance(value, ast.Set):
        return "set"
    if isinstance(value, ast.List):
        return "list"
    if isinstance(value, ast.Tuple):
        return "tuple"
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return "string"
    return type(value).__name__


def _string_entry_count(text: str) -> int:
    lines = [line.strip() for line in text.splitlines()]
    count = 0
    for line in lines:
        if not line or line.startswith(("#", "//")):
            continue
        if "->" in line or "→" in line or ":" in line or line.startswith(("-", "*")):
            count += 1
    return count


def _safe_literal_sample(value: ast.AST, limit: int = 5) -> tuple[str, ...]:
    samples: list[str] = []
    try:
        literal = ast.literal_eval(value)
    except Exception:
        return ()

    if isinstance(literal, dict):
        items = list(literal.items())[:limit]
        samples = [f"{key!s} -> {val!s}" for key, val in items]
    elif isinstance(literal, (set, list, tuple)):
        items = list(literal)[:limit]
        samples = [str(item) for item in items]
    elif isinstance(literal, str):
        lines = [line.strip() for line in literal.splitlines() if line.strip()]
        samples = lines[:limit]
    return tuple(sample[:160] for sample in samples)


def _risk_class(name: str, file_display: str, value: ast.AST, scope: str) -> str:
    bare = name.split(".")[-1]
    upper = bare.upper()
    file_lower = file_display.lower()
    if bare in CURATED_REGISTRY_RISK_CLASSES:
        return CURATED_REGISTRY_RISK_CLASSES[bare]
    if file_lower.startswith("tools/") and any(marker in upper for marker in TOOLING_MARKER_NAME_MARKERS):
        return "tooling_marker"
    if any(marker in upper for marker in QUARANTINE_NAME_MARKERS):
        return "quarantine"
    if scope == "function" and not bare.isupper():
        return "local_runtime_literal"
    if bare in POSITIVE_REGISTRY_NAMES:
        return "positive_resolution"
    if "PLATFORM" in upper:
        return "prompt_hint"
    if any(marker in upper for marker in BOOTSTRAP_NAME_MARKERS):
        return "bootstrap"
    if "prompts/" in file_lower or "prompts\\" in file_lower or (
        isinstance(value, ast.Constant)
        and isinstance(value.value, str)
        and PROMPT_HINT_NAME_RE.search(bare)
    ):
        return "prompt_hint"
    if "ABBREV" in upper or "ALIAS" in upper:
        return "positive_resolution"
    return "unknown"


def _is_registry_assignment(name: str, value: ast.AST) -> bool:
    bare = name.split(".")[-1]
    if bare not in CURATED_REGISTRY_RISK_CLASSES and not TARGET_NAME_RE.search(bare):
        return False
    entry_count = _literal_entry_count(value)
    if entry_count is None or entry_count <= 0:
        return False
    if isinstance(value, (ast.Dict, ast.Set, ast.List, ast.Tuple)):
        return True
    return isinstance(value, ast.Constant) and isinstance(value.value, str) and PROMPT_HINT_NAME_RE.search(bare)


class _RegistryVisitor(ast.NodeVisitor):
    def __init__(self, file_display: str) -> None:
        self.file_display = file_display
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []
        self.registries: list[tuple[str, ast.AST, int, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> Any:
        for target in node.targets:
            self._record(target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        if node.value is not None:
            self._record(node.target, node.value, node.lineno)
        self.generic_visit(node)

    def _record(self, target: ast.AST, value: ast.AST, line: int) -> None:
        name = _target_name(target)
        if not name:
            return
        if self.function_stack:
            scope = "function"
            if self.class_stack and isinstance(target, ast.Name):
                name = ".".join([*self.class_stack, *self.function_stack[-1:], name])
        elif self.class_stack:
            scope = "class"
            if isinstance(target, ast.Name):
                name = ".".join([*self.class_stack, name])
        else:
            scope = "module"
        if _is_registry_assignment(name, value):
            self.registries.append((name, value, line, scope))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def discover_registries(root: Path, files: Iterable[Path]) -> list[dict[str, Any]]:
    registries: list[dict[str, Any]] = []
    for path in files:
        file_display = _display_path(path, root)
        try:
            tree = ast.parse(_read_text(path), filename=file_display)
        except SyntaxError:
            continue
        visitor = _RegistryVisitor(file_display)
        visitor.visit(tree)
        for name, value, line, scope in visitor.registries:
            registries.append(
                {
                    "registry_name": name,
                    "bare_name": name.split(".")[-1],
                    "file": file_display,
                    "line": line,
                    "scope": scope,
                    "entry_count": _literal_entry_count(value),
                    "value_kind": _value_kind(value),
                    "risk_class": _risk_class(name, file_display, value, scope),
                    "sample_entries": _safe_literal_sample(value),
                }
            )
    return registries


def _line_window(lines: list[str], line_index: int, radius: int = 2) -> str:
    start = max(0, line_index - radius)
    end = min(len(lines), line_index + radius + 1)
    return "\n".join(lines[start:end])


def _usage_occurrence_priority(item: UsageOccurrence) -> tuple[int, int]:
    text = item.text.strip()
    import_penalty = 20 if text.startswith(("from ", "import ")) else 0
    kinds = set(item.usage_kinds)
    if "direct_positive_return" in kinds:
        base = 0
    elif "guard_exception_or_lock" in kinds:
        base = 1
    elif "prompt_pressure" in kinds:
        base = 2
    elif item.positive_usage:
        base = 3
    elif "search_context" in kinds:
        base = 4
    elif item.guard_usage:
        base = 5
    else:
        base = 6
    return base + import_penalty, item.line


def _is_import_only_registry_usage(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("from ", "import "))


def _is_provenance_only_registry_tuple(name: str, line: str, window: str) -> bool:
    if name not in POSITIVE_REGISTRY_NAMES:
        return False
    stripped = line.strip()
    if name not in stripped:
        return False
    return "registries = (" in window and (
        "known_abbreviation" in stripped
        or "known_title_abbreviation" in stripped
        or "slang_dictionary" in stripped
    )


def _is_tooling_registry_metadata_usage(
    name: str,
    file_display: str,
    line: str,
    window: str,
) -> bool:
    if name not in POSITIVE_REGISTRY_NAMES:
        return False
    if not file_display.startswith("tools/"):
        return False
    if name not in line:
        return False
    return "REGISTRY_SOURCES" in window or "REGISTRY_MARKERS" in window


def summarize_usage(
    root: Path,
    files: Iterable[Path],
    registry_bare_names: Iterable[str],
    *,
    sample_limit: int = 8,
) -> dict[str, UsageSummary]:
    names = sorted(set(registry_bare_names), key=len, reverse=True)
    counters: dict[str, Counter[str]] = {name: Counter() for name in names}
    samples: dict[str, list[UsageOccurrence]] = {name: [] for name in names}
    if not names:
        return {}

    patterns = {
        name: re.compile(rf"\b{re.escape(name)}\b")
        for name in names
    }
    for path in files:
        file_display = _display_path(path, root)
        try:
            lines = _read_text(path).splitlines()
        except UnicodeDecodeError:
            continue
        for idx, line in enumerate(lines):
            stripped = line.strip()
            definition_line_names = {
                name
                for name in names
                if re.match(rf"^(?:[\w\.]+\.)?{re.escape(name)}\s*(?::[^=]+)?=", stripped)
            }
            for name, pattern in patterns.items():
                if name in definition_line_names:
                    continue
                if not pattern.search(line):
                    continue
                window = _line_window(lines, idx, radius=8)
                usage_kinds = tuple(
                    usage_kind
                    for usage_kind, usage_pattern in USAGE_KIND_PATTERNS.items()
                    if usage_pattern.search(window)
                )
                counters[name]["usage"] += 1
                positive_usage = bool(POSITIVE_USAGE_RE.search(window))
                if _is_import_only_registry_usage(line) or _is_provenance_only_registry_tuple(name, line, window):
                    positive_usage = False
                    usage_kinds = tuple(
                        usage_kind for usage_kind in usage_kinds if usage_kind != "direct_positive_return"
                    )
                if _is_tooling_registry_metadata_usage(name, file_display, line, window):
                    positive_usage = False
                    usage_kinds = tuple(
                        usage_kind for usage_kind in usage_kinds if usage_kind != "direct_positive_return"
                    )
                guard_usage = bool(GUARD_OR_EVIDENCE_RE.search(window))
                if positive_usage:
                    counters[name]["positive"] += 1
                if guard_usage:
                    counters[name]["guard"] += 1
                for usage_kind in usage_kinds:
                    counters[name][f"kind:{usage_kind}"] += 1
                if len(samples[name]) < sample_limit and (positive_usage or guard_usage or usage_kinds):
                    samples[name].append(
                        UsageOccurrence(
                            file=_display_path(path, root),
                            line=idx + 1,
                            text=stripped,
                            window_excerpt=window,
                            usage_kinds=usage_kinds,
                            positive_usage=positive_usage,
                            guard_usage=guard_usage,
                        )
                    )

    _add_curated_indirect_usage_samples(root, files, names, counters, samples)

    return {
        name: UsageSummary(
            usage_count=int(counter.get("usage") or 0),
            positive_usage_count=int(counter.get("positive") or 0),
            guard_usage_count=int(counter.get("guard") or 0),
            usage_kind_counts={
                key.removeprefix("kind:"): int(value)
                for key, value in counter.items()
                if key.startswith("kind:") and value
            },
            samples=tuple(sorted(samples[name], key=_usage_occurrence_priority)[:sample_limit]),
        )
        for name, counter in counters.items()
    }


def _add_curated_indirect_usage_samples(
    root: Path,
    files: Iterable[Path],
    names: Iterable[str],
    counters: dict[str, Counter[str]],
    samples: dict[str, list[UsageOccurrence]],
) -> None:
    name_set = set(names)
    if "SLANG_DICTIONARY" not in name_set:
        return
    for path in files:
        try:
            lines = _read_text(path).splitlines()
        except UnicodeDecodeError:
            continue
        text = "\n".join(lines)
        if "SLANG_DICTIONARY" not in text or "slang[1]" not in text:
            continue
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if "official_title=slang[1]" not in stripped:
                continue
            window = _line_window(lines, idx, radius=8)
            counters["SLANG_DICTIONARY"]["usage"] += 1
            counters["SLANG_DICTIONARY"]["positive"] += 1
            counters["SLANG_DICTIONARY"]["kind:direct_positive_return"] += 1
            samples["SLANG_DICTIONARY"].append(
                UsageOccurrence(
                    file=_display_path(path, root),
                    line=idx + 1,
                    text=stripped,
                    window_excerpt=window,
                    usage_kinds=("direct_positive_return",),
                    positive_usage=True,
                    guard_usage=bool(GUARD_OR_EVIDENCE_RE.search(window)),
                )
            )


def _gate_status(risk_class: str, positive_usage: bool, guard_required: bool) -> str:
    if risk_class == "local_runtime_literal":
        return "INFO"
    if risk_class == "quarantine":
        return "INFO"
    if risk_class == "prompt_hint":
        return "INFO"
    if risk_class == "tooling_marker":
        return "INFO"
    if risk_class == "positive_resolution":
        if not positive_usage:
            return "INFO"
        return "REVIEW" if guard_required else "REVIEW-LOCKED"
    if risk_class == "bootstrap":
        return "REVIEW" if positive_usage else "INFO"
    if positive_usage:
        return "REVIEW"
    return "INFO"


def _overall_gate(findings: Iterable[RegistryFinding]) -> str:
    statuses = {finding.gate_status for finding in findings}
    if "REVIEW-LOCKED" in statuses:
        return "REVIEW-LOCKED"
    if "REVIEW" in statuses:
        return "REVIEW"
    return "GO"


def audit_paths(root: Path, scan_paths: Iterable[Path]) -> dict[str, Any]:
    root = root.resolve()
    files = _iter_python_files(root, scan_paths)
    discovered = discover_registries(root, files)
    usage = summarize_usage(root, files, (item["bare_name"] for item in discovered))

    findings: list[RegistryFinding] = []
    for item in discovered:
        usage_summary = usage.get(
            item["bare_name"],
            UsageSummary(
                usage_count=0,
                positive_usage_count=0,
                guard_usage_count=0,
                usage_kind_counts={},
                samples=(),
            ),
        )
        positive_usage = usage_summary.positive_usage_count > 0
        guard_required = usage_summary.guard_usage_count > 0
        gate_status = _gate_status(item["risk_class"], positive_usage, guard_required)
        findings.append(
            RegistryFinding(
                registry_name=item["registry_name"],
                file=item["file"],
                line=int(item["line"]),
                scope=item["scope"],
                entry_count=item["entry_count"],
                risk_class=item["risk_class"],
                value_kind=item["value_kind"],
                positive_usage=positive_usage,
                guard_evidence_support_required=guard_required,
                gate_status=gate_status,
                usage_count=usage_summary.usage_count,
                positive_usage_count=usage_summary.positive_usage_count,
                guard_usage_count=usage_summary.guard_usage_count,
                usage_kind_counts=usage_summary.usage_kind_counts,
                usage_samples=usage_summary.samples,
                sample_entries=tuple(item["sample_entries"]),
            )
        )

    findings.sort(key=lambda f: (f.file, f.line, f.registry_name))
    gate = _overall_gate(findings)
    risk_counts = Counter(finding.risk_class for finding in findings)
    gate_counts = Counter(finding.gate_status for finding in findings)
    positive_blockers = [
        finding.as_dict()
        for finding in findings
        if finding.risk_class == "positive_resolution" and finding.gate_status in {"REVIEW", "REVIEW-LOCKED"}
    ]
    quarantine_only = [
        finding.as_dict()
        for finding in findings
        if finding.risk_class == "quarantine"
    ]
    critical_usage_samples = [
        {
            "registry_name": finding.registry_name,
            "risk_class": finding.risk_class,
            "gate_status": finding.gate_status,
            "sample": sample.as_dict(),
        }
        for finding in findings
        if finding.risk_class == "positive_resolution"
        for sample in finding.usage_samples
        if sample.positive_usage or "direct_positive_return" in sample.usage_kinds
        if not sample.text.strip().startswith(("from ", "import "))
    ][:20]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "audit": "hardcoded_alias_risk",
        "root": str(root),
        "scanned_file_count": len(files),
        "registry_count": len(findings),
        "risk_class_counts": dict(sorted(risk_counts.items())),
        "gate_status_counts": dict(sorted(gate_counts.items())),
        "gate": {
            "semantic_approval": gate,
            "approval_note": (
                "positive hardcoded alias/abbreviation registries are REVIEW evidence, "
                "not semantic approval evidence; quarantine-only registries are not approval blockers"
            ),
            "positive_hardcoded_alias_blocker_count": len(positive_blockers),
            "quarantine_only_count": len(quarantine_only),
        },
        "registries": [finding.as_dict() for finding in findings],
        "positive_hardcoded_alias_blockers": positive_blockers,
        "quarantine_only_registries": quarantine_only,
        "critical_usage_samples": critical_usage_samples,
    }


def build_markdown(audit: dict[str, Any]) -> str:
    gate = audit.get("gate") or {}
    lines = [
        "# Hardcoded Alias Risk 감사",
        "",
        "## 요약",
        "",
        f"- semantic approval gate: `{gate.get('semantic_approval', 'UNKNOWN')}`",
        f"- 스캔 파일: {audit.get('scanned_file_count', 0)}개",
        f"- 발견 registry: {audit.get('registry_count', 0)}개",
        f"- positive hardcoded alias blocker: {gate.get('positive_hardcoded_alias_blocker_count', 0)}개",
        f"- quarantine-only registry: {gate.get('quarantine_only_count', 0)}개",
        "",
        "positive hardcoded alias/abbreviation map은 semantic approval 근거가 아니라 `REVIEW` 또는 `REVIEW-LOCKED` 근거입니다. quarantine-only blocklist는 승인 차단자로 계산하지 않습니다.",
        "",
        "## Risk Class Counts",
        "",
    ]
    for key, value in sorted((audit.get("risk_class_counts") or {}).items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Registry Table",
            "",
            "| registry | scope | risk_class | gate_status | file:line | entries | positive_usage | guard/evidence |",
            "|---|---|---|---|---|---:|---:|---:|",
        ]
    )
    for item in audit.get("registries") or []:
        lines.append(
            "| `{registry}` | `{scope}` | `{risk}` | `{gate_status}` | `{file}:{line}` | {entries} | {positive} | {guard} |".format(
                registry=item.get("registry_name", ""),
                scope=item.get("scope", ""),
                risk=item.get("risk_class", ""),
                gate_status=item.get("gate_status", ""),
                file=item.get("file", ""),
                line=item.get("line", ""),
                entries=item.get("entry_count") if item.get("entry_count") is not None else "",
                positive="yes" if item.get("positive_usage") else "no",
                guard="yes" if item.get("guard_evidence_support_required") else "no",
            )
        )
    usage_kind_totals: Counter[str] = Counter()
    for item in audit.get("registries") or []:
        usage_kind_totals.update(item.get("usage_kind_counts") or {})
    if usage_kind_totals:
        lines.extend(["", "## Usage Severity Counts", ""])
        for key, value in sorted(usage_kind_totals.items()):
            lines.append(f"- `{key}`: {value}")
    critical_samples = audit.get("critical_usage_samples") or []
    if critical_samples:
        lines.extend(
            [
                "",
                "## Critical Usage Samples",
                "",
                "| registry | gate_status | file:line | kinds | line | context |",
                "|---|---|---|---|---|---|",
            ]
        )
        for item in critical_samples:
            sample = item.get("sample") or {}
            kinds = ", ".join(sample.get("usage_kinds") or [])
            line_text = str(sample.get("text") or "").replace("|", "\\|")
            context = " / ".join(
                part.strip()
                for part in str(sample.get("window_excerpt") or "").splitlines()
                if part.strip()
            )[:260].replace("|", "\\|")
            lines.append(
                "| `{registry}` | `{gate}` | `{file}:{line}` | `{kinds}` | `{text}` | `{context}` |".format(
                    registry=item.get("registry_name", ""),
                    gate=item.get("gate_status", ""),
                    file=sample.get("file", ""),
                    line=sample.get("line", ""),
                    kinds=kinds,
                    text=line_text,
                    context=context,
                )
            )
    lines.extend(["", "## 판정 메모", ""])
    if gate.get("semantic_approval") == "GO":
        lines.append("- hardcoded positive alias registry가 승인 차단자로 발견되지 않았습니다.")
    else:
        lines.append(
            "- hardcoded positive alias registry가 있으므로 이 감사 결과만으로는 10만 건 semantic approval을 낼 수 없습니다."
        )
        lines.append("- `REVIEW-LOCKED`는 guard/evidence usage가 확인되지 않은 positive 해소 registry를 뜻합니다.")
        lines.append("- `REVIEW`는 guard/evidence 경로가 보이더라도 별도 표본 검토 근거가 필요한 상태입니다.")
    return "\n".join(lines) + "\n"


def _default_scan_paths() -> list[Path]:
    return [Path("src"), Path("tools"), Path("expert_main.py")]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit hardcoded alias/abbreviation registries and semantic approval risk.",
    )
    parser.add_argument("--root", type=Path, default=_repo_root(), help="Repository root to scan.")
    parser.add_argument(
        "--scan-path",
        action="append",
        type=Path,
        default=None,
        help="Path under root to scan. Can be repeated. Defaults to src, tools, expert_main.py.",
    )
    parser.add_argument("--output-json", type=Path, help="Write JSON audit output to this path.")
    parser.add_argument("--output-md", type=Path, help="Write Korean markdown audit output to this path.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="Stdout format.")
    parser.add_argument(
        "--fail-on-review-locked",
        action="store_true",
        help="Return exit code 2 when the semantic approval gate is REVIEW-LOCKED.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = args.root.resolve()
    scan_paths = args.scan_path or _default_scan_paths()
    audit = audit_paths(root, scan_paths)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(build_markdown(audit), encoding="utf-8")

    if args.format == "markdown":
        print(build_markdown(audit), end="")
    else:
        print(json.dumps(audit, ensure_ascii=False, indent=2))

    if args.fail_on_review_locked and (audit.get("gate") or {}).get("semantic_approval") == "REVIEW-LOCKED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
