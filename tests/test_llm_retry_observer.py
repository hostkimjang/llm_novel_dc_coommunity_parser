from __future__ import annotations

import unittest

import httpx

from llm_batch.llm.client import (
    RetryAttemptObservation,
    observe_llm_retry_attempts,
    retry_with_backoff,
)


class RetryAttemptObserverTest(unittest.TestCase):
    def test_successful_first_attempt_is_observed(self) -> None:
        observations: list[RetryAttemptObservation] = []

        with observe_llm_retry_attempts(observations.append):
            self.assertEqual(retry_with_backoff(lambda: "ok", max_retries=3, base_delay=0), "ok")

        self.assertEqual([item.event for item in observations], ["ATTEMPT_STARTED", "ATTEMPT_SUCCEEDED"])
        self.assertEqual([item.attempt_number for item in observations], [1, 1])
        self.assertTrue(all(item.max_attempts == 3 for item in observations))
        self.assertTrue(all(item.will_retry is None for item in observations))

    def test_retry_then_success_observes_two_physical_attempts(self) -> None:
        observations: list[RetryAttemptObservation] = []
        calls = 0

        def first_failure_then_success() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("temporary")
            return "ok"

        with observe_llm_retry_attempts(observations.append):
            self.assertEqual(retry_with_backoff(first_failure_then_success, max_retries=3, base_delay=0), "ok")

        self.assertEqual(
            [(item.event, item.attempt_number, item.will_retry) for item in observations],
            [
                ("ATTEMPT_STARTED", 1, None),
                ("ATTEMPT_FAILED", 1, True),
                ("ATTEMPT_STARTED", 2, None),
                ("ATTEMPT_SUCCEEDED", 2, None),
            ],
        )
        self.assertEqual(observations[1].error_type, "ConnectionError")
        self.assertEqual(observations[1].error_message, "temporary")
        self.assertTrue(observations[0].retry_operation_id)
        self.assertEqual(
            {item.retry_operation_id for item in observations},
            {observations[0].retry_operation_id},
        )

    def test_final_fallback_is_observed_after_terminal_failure(self) -> None:
        observations: list[RetryAttemptObservation] = []
        fallback_errors: list[Exception] = []

        def always_fails() -> str:
            raise ConnectionError("down")

        with observe_llm_retry_attempts(observations.append):
            result = retry_with_backoff(
                always_fails,
                max_retries=2,
                base_delay=0,
                on_failure=lambda error: fallback_errors.append(error) or "fallback",
            )

        self.assertEqual(result, "fallback")
        self.assertEqual(len(fallback_errors), 1)
        failed = [item for item in observations if item.event == "ATTEMPT_FAILED"]
        self.assertEqual([(item.attempt_number, item.will_retry) for item in failed], [(1, True), (2, False)])

    def test_no_observer_preserves_result(self) -> None:
        self.assertEqual(retry_with_backoff(lambda: 7, max_retries=1, base_delay=0), 7)

    def test_nonretryable_http_failure_is_terminal(self) -> None:
        observations: list[RetryAttemptObservation] = []
        calls = 0
        request = httpx.Request("POST", "http://example.test/v1/chat/completions")
        response = httpx.Response(400, request=request)

        def nonretryable_failure() -> str:
            nonlocal calls
            calls += 1
            raise httpx.HTTPStatusError("bad request", request=request, response=response)

        with observe_llm_retry_attempts(observations.append):
            result = retry_with_backoff(
                nonretryable_failure,
                max_retries=3,
                base_delay=0,
                on_failure=lambda _error: "fallback",
            )

        self.assertEqual(result, "fallback")
        self.assertEqual(calls, 1)
        self.assertEqual(
            [(item.event, item.attempt_number, item.will_retry) for item in observations],
            [("ATTEMPT_STARTED", 1, None), ("ATTEMPT_FAILED", 1, False)],
        )

    def test_observer_failure_does_not_change_retry_outcome(self) -> None:
        calls = 0

        def observer_that_fails(_observation: RetryAttemptObservation) -> None:
            raise RuntimeError("observer failure")

        def first_failure_then_success() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("temporary")
            return "ok"

        with observe_llm_retry_attempts(observer_that_fails):
            self.assertEqual(retry_with_backoff(first_failure_then_success, max_retries=2, base_delay=0), "ok")
        self.assertEqual(calls, 2)

    def test_nested_context_restores_outer_observer(self) -> None:
        outer: list[RetryAttemptObservation] = []
        inner: list[RetryAttemptObservation] = []

        with observe_llm_retry_attempts(outer.append):
            retry_with_backoff(lambda: "outer-before", max_retries=1, base_delay=0)
            with self.assertRaisesRegex(ValueError, "inner scope"):
                with observe_llm_retry_attempts(inner.append):
                    retry_with_backoff(lambda: "inner", max_retries=1, base_delay=0)
                    raise ValueError("inner scope")
            retry_with_backoff(lambda: "outer-after", max_retries=1, base_delay=0)

        self.assertEqual(len(outer), 4)
        self.assertEqual(len(inner), 2)
        self.assertTrue(all(item.event != "ATTEMPT_FAILED" for item in outer + inner))


if __name__ == "__main__":
    unittest.main()
