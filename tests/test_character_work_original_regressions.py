"""원형 인물 군집 회귀2개의 실제 unittest 수명주기. 원본 기대는 유지한다."""
import unittest
import pytest
import test_agentic_pipeline_rework as original

NAMES = ['test_deliberated_character_cluster_reseeds_candidate_without_publication_authority', 'test_character_cluster_metadata_preserves_candidates_without_public_pair']

@pytest.mark.parametrize('method_name', NAMES)
def test_original_character_work_regression(method_name):
    case = original.AgenticPipelineReworkTest(methodName=method_name)
    result = unittest.TestResult()
    case.run(result)
    assert result.testsRun == 1
    assert not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses
    assert result.wasSuccessful(), '\n'.join(t for _, t in result.failures + result.errors)
