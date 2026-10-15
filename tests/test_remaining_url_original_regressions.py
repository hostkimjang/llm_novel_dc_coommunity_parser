"""원형 URL 회귀10개의 실제 unittest 수명주기. 테스트 구현·기대값은 원본 그대로다."""
import unittest
import pytest
import test_agentic_pipeline_rework as _original

NAMES = ['test_title_matched_official_url_uses_snippet_when_result_title_is_generic', 'test_title_matched_official_url_prefers_author_context_over_same_title_homonym', 'test_kakao_comment_tab_webnovel_title_counts_as_sanitized_evidence', 'test_title_matched_official_url_prefers_exact_title_over_platform_rank', 'test_kakao_novel_synopsis_original_protagonist_is_not_derivative_hit', 'test_munpia_branding_title_is_not_url_title_mismatch_signal', 'test_heretic_url_validator_keeps_exact_search_title_when_fetch_is_ui_unavailable', 'test_unavailable_exact_search_title_survives_stale_representative_title', 'test_access_blocked_fetch_title_does_not_clear_exact_official_url', 'test_unavailable_official_url_kept_when_post_contains_url_and_exact_title']

@pytest.mark.parametrize('method_name', NAMES)
def test_original_url_regression(method_name):
    case = _original.AgenticPipelineReworkTest(methodName=method_name)
    result = unittest.TestResult()
    case.run(result)
    assert result.testsRun == 1
    assert not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses
    assert result.wasSuccessful(), '\n'.join(text for _, text in result.failures + result.errors)
