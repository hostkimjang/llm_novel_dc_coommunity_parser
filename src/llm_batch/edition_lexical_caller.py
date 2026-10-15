"""검증된 A 원문 inventory와 captured public 전달 helper. 역할 추정·공식 권한 부여 없음."""
from __future__ import annotations
from typing import Any, Optional
from . import promotion_gate as P
from . import record_role_types as T
from . import record_role_transport as R
from .promotion_gate import apply_publish_contract
from .edition_lexical_pipeline_api import encode_actual_value, verify_captured_bundle

def original_text(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        if str(value.get("type") or "text").strip().lower() != "text":
            return None
        if any(value.get(key) is True for key in ("is_quote", "quoted", "is_quoted")):
            return None
        speaker = str(value.get("speaker") or "").strip().lower()
        if speaker and speaker not in {"author", "post_author", "original_author", "op"}:
            return None
        if value.get("is_post_author") is False:
            return None
        if any(value.get(key) for key in ("url", "image_url", "href", "src")):
            return None
        if any(str(value.get(key) or "").strip().lower() in {"true", "1", "yes"}
               for key in ("is_generated", "generated", "from_ocr", "is_ocr")):
            return None
        provenance = " ".join(
            str(value.get(key) or "")
            for key in ("source", "origin", "provenance", "generated_source")
        ).lower()
        if any(marker in provenance for marker in ("ocr", "vlm", "generated", "summary", "image", "search", "link_preview")):
            return None
        value = value.get("text") or value.get("content")
    if not isinstance(value, str):
        return None
    if value.lstrip().startswith(("[이미지 OCR]", "[이미지 요약]", "[이미지 설명]", "[VLM 요약]", "[VLM 설명]")):
        return None
    return value if value.strip() else None


def source_chunks_with_origins(ctx):
    post=getattr(ctx,'post_data',None);post=post if isinstance(post,dict) else {}
    inventory=[];chunks=[]
    def add(role,index,pointer,value,title=False):
        row={'source_role':role,'original_source_index':index,'original_source_position':len(inventory),
             'input_pointer':pointer,'raw_input':value}
        selected=str(value or '').strip() if title else original_text(value)
        row.update({'selected':bool(selected),'selected_text':selected,
             'selected_index':len(chunks) if selected else None,
             'raw_title_trim_start':len(str(value or ''))-len(str(value or '').lstrip()) if title else 0})
        inventory.append(row)
        if selected:chunks.append((role,selected))
    add('post_title',0,'/post_data/title',post.get('title'),True)
    blocks=post.get('content_blocks')
    if isinstance(blocks,list) and blocks:
        for i,value in enumerate(blocks):add('post_body',i,'/post_data/content_blocks/'+str(i),value)
    else:
        body=post.get('content'); values=body if isinstance(body,(list,tuple)) else [body]
        for i,value in enumerate(values):add('post_body',i,'/post_data/content/'+str(i) if isinstance(body,(list,tuple)) else '/post_data/content',value)
    for i,value in enumerate(getattr(ctx,'comments',None) or []):
        if isinstance(value,(dict,str)):add('comment',i,'/comments/'+str(i),value)
        else:inventory.append({'source_role':'comment','original_source_index':i,'original_source_position':len(inventory),'input_pointer':'/comments/'+str(i),
            'raw_input':value,'selected':False,'selected_text':None,'selected_index':None,'reason':'original_caller_unsupported_comment_type'})
    return chunks,tuple(inventory)


def apply_publish_contract_with_native_bundle(identity,contract,bundle):
    if contract.state.edition_publication is not bundle.state or bundle.state.current_relation is not bundle.result.relation:
        raise ValueError('actual publish state/relation differs from lexical caller return')
    captured, fresh_normalized = verify_captured_bundle(bundle)
    # Encode before scalar mutation; all returned containers are fresh, not bundle aliases.
    normalized_output = encode_actual_value(fresh_normalized)
    apply_publish_contract(identity,contract)
    identity['edition_record_role_native']=captured
    identity['edition_record_role_normalized']=normalized_output
    return identity

def current_product_bindings():
    """Use actual loaded product defining modules; no candidate class/source substitution."""
    return (R.ClassBinding(P, P.__file__, R.file_sha(P.__file__)),
            R.ClassBinding(T, T.__file__, R.file_sha(T.__file__)))


def apply_publish_contract_for_context(identity, contract, ctx):
    """Select the actual returned state by identity, then consume the r3 transmission verifier."""
    ctx._edition_lexical_publication_bundle = None
    ctx._edition_record_role_native = None
    ctx._edition_record_role_normalized = None
    state = contract.state.edition_publication
    if state is None or state.current_relation is None:
        return apply_publish_contract(identity, contract)
    cache = getattr(ctx, '_edition_lexical_candidate_bundles', {})
    matches = {id(bundle): bundle for bundle in cache.values() if bundle.state is state}
    if len(matches) != 1:
        raise ValueError('actual lexical publication bundle for returned state missing or ambiguous')
    bundle = next(iter(matches.values()))
    returned = apply_publish_contract_with_native_bundle(identity, contract, bundle)
    ctx._edition_lexical_publication_bundle = bundle
    ctx._edition_record_role_native = returned['edition_record_role_native']
    ctx._edition_record_role_normalized = returned['edition_record_role_normalized']
    return returned
