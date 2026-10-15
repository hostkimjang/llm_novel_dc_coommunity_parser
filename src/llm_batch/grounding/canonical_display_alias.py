"""공식 표시 제목으로 옮길 수 있는 기존 원문 약칭 후보를 고른다.

이 함수는 공식 상세의 존재를 판정하지 않는다. 호출자는 반환된 각 base 제목과
URL에 대해 실제 fetched display binding을 다시 확인해야 한다.
"""
from __future__ import annotations

import re
from typing import Any

from ..domain.title_integrity import normalize_title_integrity_token


def canonical_display_alias_candidates(
    original_title: Any,
    display_title: str,
    records: list[dict[str, Any]],
    verification: dict[str, Any],
) -> list[dict[str, str]]:
    if not isinstance(original_title, str) or not isinstance(verification, dict):
        return []
    norm = normalize_title_integrity_token
    display_key = norm(display_title)
    identity = verification.get('novel_identity')
    slang = verification.get('slang_insight')
    relation = verification.get('relation_judgment')
    if not all(isinstance(value, dict) for value in (identity, slang, relation)):
        return []
    if (verification.get('is_relevant') is not True
        or slang.get('decode_verified') is not True
        or slang.get('alias_scope') != 'pure_work_alias'
        or relation.get('relation_type') not in {'explicit_alias', 'title_alias', 'work_alias'}
        or relation.get('discussion_target') != 'specific_work'
        or relation.get('promotion_decision') not in {'allow', 'promote', 'publish'}):
        return []
    base = str(slang.get('decoded_term') or '').strip()
    alias = str(slang.get('canonical_work_alias') or slang.get('detected_term') or '').strip()
    base_key = norm(base)
    verified_title = identity.get('official_novel_title') or identity.get('official_title')
    url = str(identity.get('heretic_url') or identity.get('official_url') or '').strip()
    if (not base_key or base_key == display_key or norm(verified_title) != base_key
        or len(norm(alias)) < 2 or not url):
        return []
    selected_urls = {
        str(row.get('heretic_url') or row.get('official_url') or '').strip()
        for row in records if isinstance(row, dict)
        and norm(row.get('official_title') or row.get('title')) == display_key
        and row.get('reference_role') == 'primary'
    }
    if selected_urls != {url}:
        return []
    word = r'0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_'
    particle = r'(?:에서|에게|한테|으로|하고|처럼|까지|부터|은|는|이|가|을|를|의|도|만|에|와|과|랑|로)?'
    if not re.search(rf'(?<![{word}]){re.escape(alias)}{particle}(?![{word}])', original_title, re.IGNORECASE):
        return []
    for row in records:
        if not isinstance(row, dict) or row.get('reference_role') not in {'primary', 'candidate'}:
            continue
        row_url = str(row.get('heretic_url') or row.get('official_url') or '').strip()
        if (norm(row.get('official_title') or row.get('title')) == base_key
            and norm(row.get('alias_or_mention') or row.get('alias')) == norm(alias)
            and (not row_url or row_url == url)):
            return [{'alias': alias, 'source_title': base, 'candidate_title': display_title, 'candidate_url': url}]
    return []
