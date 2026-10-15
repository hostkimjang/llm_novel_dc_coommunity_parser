"""저장 전문가를 실제 serializer/검산/공개 WAL에 재생한다. 외부 호출 및 guard mock 없음."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Mapping

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / 'fixtures/actual80_nsfw74_saved_experts.json'
canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
sha = lambda value: hashlib.sha256(value).hexdigest()


class NoExternalIO:
    def fetch(self, *args, **kwargs):
        raise AssertionError('EXTERNAL_FETCH_FORBIDDEN')

    def search(self, *args, **kwargs):
        raise AssertionError('EXTERNAL_SEARCH_FORBIDDEN')


def wrapper_class():
    # 실제 main의 운반/저장 검산 클래스 그대로. main 프로세스/모델은 실행하지 않는다.
    tree = ast.parse((ROOT / 'expert_main.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_FinalSourceContextResult')
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {'Any': Any, 'Dict': Dict, 'Mapping': Mapping}
    exec(compile(module, str(ROOT / 'expert_main.py'), 'exec'), namespace)
    return namespace['_FinalSourceContextResult']


def context_for(label='new', mutate_post=None, *, capture=True, record_override=None):
    record = copy.deepcopy(record_override if record_override is not None else json.loads(FIXTURE.read_text(encoding='utf-8'))['records'][label])
    raw = dict(record['post'], comments=record['comments'])
    if mutate_post:
        mutate_post(raw)
    post = PostInput(**raw)
    pipe = AgenticPipeline(llm=object(), mcp=NoExternalIO(), max_iterations=1)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    if capture:
        ctx._source_bound_nsfw_original_carrier = pipe._capture_source_bound_nsfw_carrier(post)
    for name, payload in record['experts'].items():
        ctx.set_expert_output(ExpertType(name), copy.deepcopy(payload))
    discourse = (record['experts'].get('discourse') or {}).get('discourse_analysis') or {}
    ctx.primary_domain = discourse.get('primary_domain')
    ctx.discourse_intent = discourse.get('intent')
    return pipe, ctx, record


def set_comment(raw, text):
    raw['comments'][4]['content'] = text
    raw['comments'][4]['content_html'] = text


class SourceBoundNSFWTests(unittest.TestCase):
    def serialize(self, pipe, ctx):
        before = canonical({'post_data': ctx.post_data, 'comments': ctx.comments})
        output = pipe._context_to_output(ctx)
        payload = output.model_dump(mode='json')
        observation = pipe.verify_final_source_context_serialization(output, payload, stage='nsfw_regression_model_dump')
        self.assertEqual(canonical({'post_data': ctx.post_data, 'comments': ctx.comments}), before)
        self.assertIsNone(payload['identity']['novel_identity'])
        self.assertFalse(payload['identity']['title_resolution_allowed'])
        return output, payload, observation

    def test_actual74_false_conflict_uses_exact_source_and_real_wal_readback(self):
        fixture_before = FIXTURE.read_bytes()
        pipe, ctx, record = context_for()
        self.assertIs(record['experts']['arbiter']['metadata_synthesis']['is_nsfw'], False)
        output, payload, observation = self.serialize(pipe, ctx)
        self.assertIs(payload['analysis']['is_nsfw'], True)
        proof = observation['nsfw_content_observation']
        self.assertEqual(proof['status'], 'SOURCE_CONFLICT_RESOLVED_TRUE')
        self.assertIs(proof['arbiter_value'], False)
        self.assertIs(proof['publication_authority'], False)
        self.assertEqual(proof['author_endorsement'], 'NOT_ASSESSED')
        self.assertEqual(len(proof['evidence']), 1)
        evidence = proof['evidence'][0]
        self.assertEqual((evidence['raw_path'], evidence['raw_span'], evidence['quote']), ('/comments/4/content', [0, 6], '히로인 강간'))
        self.assertEqual((evidence['comment_id'], evidence['comment_id_type']), ('28684585', 'str'))
        self.assertEqual(evidence['target_span'], [0, 3])
        self.assertEqual(evidence['act_span'], [4, 6])
        self.assertEqual(evidence['raw_text_sha256'], sha('히로인 강간'.encode()))
        self.assertEqual(evidence['speaker_scope'], 'COMMENT_OCCURRENCE_AUTHORSHIP_NOT_INFERRED')
        full = dict(record['post'], post_author=record['post'].get('author'),
                    comments=record['comments'], analysis_result=payload)
        wrapped = wrapper_class()(full, output=output, verifier=pipe.verify_final_source_context_serialization)
        with tempfile.TemporaryDirectory() as tmp:
            scope = build_publication_scope_descriptor(input_file_sha256=sha(canonical(record['post']).encode()),
                post_ids=[ctx.post_id], config_hash='nsfw-saved-expert-regression', release_fingerprint='draft-only')
            path = Path(tmp) / 'publication_commits.jsonl'
            registry = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=True)
            wrapped.verify_stored_payload(wrapped, stage='before_publication_commit')
            commit, created = commit_publication_result(wrapped, registry=registry,
                attempt_run_id='saved-expert-nsfw', input_index=1, post_id=ctx.post_id)
            self.assertTrue(created)
            self.assertEqual(commit.outcome, 'HOLD')
            self.assertFalse(commit.publish_allowed)
            reopened = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=False)
            stored = reopened.result(ctx.post_id)
            stored_observation = wrapped.verify_stored_payload(stored, stage='canonical_stored_payload')
            self.assertIs(stored['analysis_result']['analysis']['is_nsfw'], True)
            self.assertEqual(stored_observation['nsfw_content_observation'], proof)
            before_wal = path.read_bytes()
            tampered = copy.deepcopy(stored)
            tampered['analysis_result']['analysis']['is_nsfw'] = False
            with self.assertRaises(ValueError):
                wrapped.verify_stored_payload(tampered, stage='tampered_readback')
            self.assertEqual(path.read_bytes(), before_wal)
        self.assertEqual(FIXTURE.read_bytes(), fixture_before)

    def test_old_true_stays_true_and_legacy_field_seal_definition_is_unchanged(self):
        pipe, ctx, record = context_for('old')
        self.assertIs(record['experts']['arbiter']['metadata_synthesis']['is_nsfw'], True)
        _, payload, observation = self.serialize(pipe, ctx)
        self.assertIs(payload['analysis']['is_nsfw'], True)
        fields = pipe._final_source_serialization_fields(payload)
        self.assertNotIn('is_nsfw', fields['analysis'])
        self.assertEqual(observation['nsfw_content_observation']['status'], 'SOURCE_EXPLICIT_CONTENT_TRUE')

    def test_missing_carrier_does_not_reconstruct_proof_or_override_false(self):
        pipe, ctx, _ = context_for(capture=False)
        _, payload, observation = self.serialize(pipe, ctx)
        self.assertIs(payload['analysis']['is_nsfw'], False)
        self.assertEqual(observation['nsfw_content_observation']['status'], 'SOURCE_NOT_BOUND')

    def test_keyword_negation_question_quote_nonfiction_and_html_do_not_trigger(self):
        for text in ('강간', '히로인 강간은 아니다', '히로인 강간 없음', '히로인 강간인가?',
                     '"히로인 강간"', '성폭행 예방 교육', '강간은 범죄다', '내 지갑 강간당함', '히로인 강화', '<p>히로인 강간</p>',
                     'https://example.invalid/히로인강간', '예전에 "히로인 강간"이라고 누가 말했다'):
            with self.subTest(text=text):
                pipe, ctx, _ = context_for(mutate_post=lambda raw: set_comment(raw, text))
                _, payload, observation = self.serialize(pipe, ctx)
                self.assertIs(payload['analysis']['is_nsfw'], False)
                self.assertEqual(observation['nsfw_content_observation']['evidence'], [])

    def test_explicit_fictional_role_object_particle_and_spacing_are_supported(self):
        for text in ('히로인을 강간하는 장면', '여주인공을 성폭행하는 전개', '  남주인공 성폭행 묘사  ', '주인공을\t강간하는 장면'):
            with self.subTest(text=text):
                pipe, ctx, _ = context_for(mutate_post=lambda raw: set_comment(raw, text))
                _, payload, observation = self.serialize(pipe, ctx)
                self.assertIs(payload['analysis']['is_nsfw'], True)
                evidence = observation['nsfw_content_observation']['evidence'][0]
                lo, hi = evidence['raw_span']
                self.assertEqual(text[lo:hi], text.strip())
                for part in ('target', 'act'):
                    lo, hi = evidence[part + '_span']
                    self.assertEqual(text[lo:hi], evidence[part + '_surface'])

    def test_external_snippet_or_expert_only_phrase_cannot_replace_original(self):
        pipe, ctx, _ = context_for(mutate_post=lambda raw: set_comment(raw, '요즘 볼 게 없다'))
        ctx.search_results = [{'title': '히로인 강간', 'content': '히로인 강간'}]
        ctx.get_expert_output(ExpertType.ARBITER)['metadata_synthesis']['micro_tags'] = ['히로인 강간']
        _, payload, observation = self.serialize(pipe, ctx)
        self.assertFalse(payload['analysis']['is_nsfw'])
        self.assertEqual(observation['nsfw_content_observation']['evidence'], [])

    def test_trope_context_and_additional_example_request_are_both_required(self):
        def no_topic(raw):
            raw['title'] = '오늘 뉴스 이야기'
        def no_request(raw):
            raw['content_blocks'][-1]['text'] = '오늘 날씨가 좋다'
        for change in (no_topic, no_request):
            with self.subTest(change=change.__name__):
                pipe, ctx, _ = context_for(mutate_post=change)
                _, payload, _ = self.serialize(pipe, ctx)
                self.assertFalse(payload['analysis']['is_nsfw'])

    def test_original_html_conflicting_selector_typed_parent_and_duplicate_id_are_rejected(self):
        def html(raw): raw['comments'][4]['content_html'] = '<p>히로인 강간</p>'
        def text(raw): raw['comments'][4]['text'] = '다른 원문'
        def parent(raw): raw['comments'][4]['post_id'] = str(raw['post_id'])
        def duplicate(raw): raw['comments'][0]['comment_id'] = raw['comments'][4]['comment_id']
        for change in (html, text, parent, duplicate):
            with self.subTest(change=change.__name__):
                pipe, ctx, _ = context_for(mutate_post=change)
                _, payload, observation = self.serialize(pipe, ctx)
                self.assertFalse(payload['analysis']['is_nsfw'])
                self.assertEqual(observation['nsfw_content_observation']['evidence'], [])

    def test_source_changed_after_capture_cannot_create_new_nsfw_proof(self):
        pipe, ctx, _ = context_for(mutate_post=lambda raw: set_comment(raw, '전개 예시 없음'))
        ctx._final_source_original_comment_refs[4]['content'] = '히로인 강간'
        ctx._final_source_original_comment_refs[4]['content_html'] = '히로인 강간'
        ctx.comments[4] = '히로인 강간'
        # 직접 원문 어댑터 검산의 실패 사유. native verifier나 판정 함수를 mock하지 않는다.
        output = pipe._context_to_output(ctx)
        observation = pipe.verify_final_source_context_serialization(output, output.model_dump(mode='json'), stage='changed_original')
        self.assertFalse(output.analysis.is_nsfw)
        self.assertNotEqual(observation['nsfw_content_observation']['status'], 'SOURCE_CONFLICT_RESOLVED_TRUE')

    def test_comment_cap_is_not_bypassed_and_comment_id_is_not_coerced(self):
        def after_cap(raw):
            target = copy.deepcopy(raw['comments'][4])
            raw['comments'] = [{'comment_id': str(500 + i), 'content': '일반 반응', 'post_id': raw['post_id']} for i in range(15)] + [target]
        pipe, ctx, _ = context_for(mutate_post=after_cap)
        _, payload, observation = self.serialize(pipe, ctx)
        self.assertFalse(payload['analysis']['is_nsfw'])
        self.assertEqual(observation['nsfw_content_observation']['evidence'], [])

    def test_fresh_bool_missing_null_false_and_model_tampering_are_rejected(self):
        pipe, ctx, _ = context_for()
        output, payload, _ = self.serialize(pipe, ctx)
        for marker in (False, None, 0, 'true', 'DELETE'):
            changed = copy.deepcopy(payload)
            if marker == 'DELETE':
                changed['analysis'].pop('is_nsfw')
            else:
                changed['analysis']['is_nsfw'] = marker
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                pipe.verify_final_source_context_serialization(output, changed, stage='bool_tamper')
        output.analysis.is_nsfw = False
        with self.assertRaises(ValueError):
            pipe.verify_final_source_context_serialization(output, output.model_dump(mode='json'), stage='model_tamper')

    def test_sealed_true_cannot_be_changed_to_analysis_none(self):
        pipe, ctx, _ = context_for()
        output, payload, _ = self.serialize(pipe, ctx)
        changed = copy.deepcopy(payload)
        changed['analysis'] = None
        with self.assertRaises(ValueError):
            pipe.verify_final_source_context_serialization(output, changed, stage='analysis_none_tamper')

    def test_current_source_mutation_after_initial_seal_is_rejected(self):
        pipe, ctx, _ = context_for()
        output, payload, _ = self.serialize(pipe, ctx)
        ctx.post_data['comments_raw'][4]['comment_id'] = 28684585
        with self.assertRaises(ValueError):
            pipe.verify_final_source_context_serialization(output, payload, stage='typed_id_drift')

    def test_mixed_string_and_dict_comments_preserve_original_occurrence(self):
        def mixed(raw): raw['comments'].insert(0, '다른 예시는?')
        pipe, ctx, _ = context_for(mutate_post=mixed)
        self.assertEqual(len(ctx.post_data['comments_raw']), 7)
        self.assertEqual(len(ctx._final_source_original_comment_refs), 8)
        _, payload, observation = self.serialize(pipe, ctx)
        proof = observation['nsfw_content_observation']
        self.assertTrue(payload['analysis']['is_nsfw'])
        self.assertEqual(proof['status'], 'SOURCE_CONFLICT_RESOLVED_TRUE')
        self.assertEqual(proof['evidence'][0]['raw_path'], '/comments/5/content')
        self.assertEqual(proof['evidence'][0]['original_index'], 5)
        self.assertEqual(proof['evidence'][0]['comment_id'], '28684585')

    def test_mixed_comments_dict_id_text_and_order_mutation_after_seal_are_rejected(self):
        def mixed(raw): raw['comments'].insert(0, '다른 예시는?')
        for mutation in ('id', 'text', 'order'):
            with self.subTest(mutation=mutation):
                pipe, ctx, _ = context_for(mutate_post=mixed)
                output, payload, _ = self.serialize(pipe, ctx)
                if mutation == 'id':
                    ctx.post_data['comments_raw'][4]['comment_id'] = 28684585
                elif mutation == 'text':
                    ctx.post_data['comments_raw'][4]['content'] = '다른 문구'
                else:
                    ctx.post_data['comments_raw'].reverse()
                with self.assertRaises(ValueError):
                    pipe.verify_final_source_context_serialization(output, payload, stage='mixed_' + mutation + '_drift')

    def test_existing16_explicit_false_remains_false_even_with_new_carrier(self):
        path = ROOT / 'tests/fixtures/actual80_semantic_state_evidence.json'
        record = json.loads(path.read_text(encoding='utf-8'))['records']['16']
        record['experts']['arbiter'] = {
            'final_decision': {'is_relevant': False, 'discussion_type': 'noise'},
            'metadata_synthesis': {'is_nsfw': False},
        }
        pipe, ctx, _ = context_for(record_override=record)
        _, payload, observation = self.serialize(pipe, ctx)
        self.assertFalse(payload['analysis']['is_nsfw'])
        self.assertEqual(observation['nsfw_content_observation']['evidence'], [])


if __name__ == '__main__':
    unittest.main()
