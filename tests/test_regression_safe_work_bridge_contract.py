import inspect
import unittest

from src.llm_batch.agentic_pipeline import AgenticPipeline


class RegressionSafeWorkBridgeContractTest(unittest.TestCase):
    def test_no_work_title_promotion_routes_through_shared_work_bridge(self):
        source = inspect.getsource(AgenticPipeline._can_promote_title_after_semantic_no_work)

        self.assertIn("_post_discusses_work_as_work", source)
        self.assertNotIn("_has_strict_direct_work_anchor_for_no_work_rescue(\n                ctx,\n                candidate", source)

    def test_high_risk_rescue_entry_points_still_call_no_work_gate(self):
        batch_alias_source = inspect.getsource(AgenticPipeline._resolve_batch_memory_alias_candidate)
        safe_single_source = inspect.getsource(AgenticPipeline._pick_safe_single_candidate_unresolved_promotion)

        self.assertIn("_can_promote_title_after_semantic_no_work", batch_alias_source)
        self.assertIn("_can_promote_title_after_semantic_no_work", safe_single_source)

    def test_shared_work_bridge_owns_alias_and_character_setting_contracts(self):
        shared_source = inspect.getsource(AgenticPipeline._post_discusses_work_as_work)
        alias_source = inspect.getsource(AgenticPipeline._has_verified_contextual_alias_work_bridge)

        self.assertIn("_has_deliberated_character_setting_work_convergence", shared_source)
        self.assertIn("source=\"verified_contextual_alias_work_bridge\"", alias_source)
        self.assertIn("_post_discusses_work_as_work", alias_source)


if __name__ == "__main__":
    unittest.main()
