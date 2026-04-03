from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


class OpenAIJSONClient:
    def __init__(
        self,
        *,
        model: str,
        api_key: Optional[str] = None,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: Optional[str] = None,
        timeout_s: float = 300.0,
        max_retries: int = 3,
        temperature: float = 0.2,
    ) -> None:
        self.model = str(model or "").strip()
        if not self.model:
            raise ValueError("openai model is required")
        self.api_key = str(api_key or os.getenv(api_key_env, "")).strip()
        if not self.api_key:
            raise ValueError(f"{api_key_env} is required for GPT full audit")
        self.base_url = str(base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.timeout_s = float(timeout_s)
        self.max_retries = max(1, int(max_retries))
        self.temperature = float(temperature)

    @staticmethod
    def _extract_json_object(text: str) -> Dict[str, Any]:
        if not isinstance(text, str):
            return {}
        text = text.strip()
        if not text:
            return {}
        try:
            raw = json.loads(text)
            return raw if isinstance(raw, dict) else {}
        except Exception:
            pass

        depth = 0
        start_idx = -1
        in_string = False
        escaped = False
        for idx, ch in enumerate(text):
            if escaped:
                escaped = False
                continue
            if ch == "\\" and in_string:
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                if depth == 0:
                    start_idx = idx
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start_idx >= 0:
                    try:
                        raw = json.loads(text[start_idx : idx + 1])
                        return raw if isinstance(raw, dict) else {}
                    except Exception:
                        start_idx = -1
                        continue
        return {}

    def complete_json(
        self,
        system_prompt: str,
        user_payload: Any,
        *,
        tag: str = "complete_json",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        del tag
        user_content = user_payload if isinstance(user_payload, str) else json.dumps(user_payload, ensure_ascii=False)
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": str(system_prompt or "")},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature if temperature is None else float(temperature),
        }
        if max_tokens is not None:
            body["max_tokens"] = int(max_tokens)

        def retry_with_backoff_local(fn):
            last_error = None
            for attempt in range(self.max_retries):
                try:
                    return fn()
                except Exception as exc:
                    last_error = exc
                    if attempt >= self.max_retries - 1:
                        raise
                    time.sleep(2.0 * (2 ** attempt))
            raise last_error  # pragma: no cover

        def do_request() -> Dict[str, Any]:
            import httpx

            body_variants = [
                dict(body),
                {k: v for k, v in body.items() if k != "response_format"},
                {k: v for k, v in body.items() if k != "temperature"},
                {k: v for k, v in body.items() if k not in {"response_format", "temperature"}},
            ]
            last_error = None
            data: Dict[str, Any] = {}
            with httpx.Client(timeout=self.timeout_s) as client:
                for request_body in body_variants:
                    try:
                        response = client.post(
                            f"{self.base_url}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                            },
                            json=request_body,
                        )
                        response.raise_for_status()
                        data = response.json()
                        last_error = None
                        break
                    except httpx.HTTPStatusError as exc:
                        last_error = exc
                        if exc.response.status_code != 400:
                            raise
                if last_error is not None:
                    raise last_error
            choices = data.get("choices") or []
            if not choices:
                return {}
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, list):
                text_parts: List[str] = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(str(item.get("text") or ""))
                content = "".join(text_parts)
            return self._extract_json_object(str(content or ""))

        return retry_with_backoff_local(do_request)
