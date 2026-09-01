import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.experts.arbiter import _build_snippet_canonical_lock_prompt  # noqa: E402


class ArbiterCanonicalLockPromptTest(unittest.TestCase):
    def test_includes_canonical_title_and_author(self) -> None:
        prompt = _build_snippet_canonical_lock_prompt("정식 작품명", "작가명")

        self.assertEqual(
            prompt,
            "\n\n=== SNIPPET CANONICAL LOCK (스니펫 정식 후보 잠금) ===\n"
            "- snippet canonical title: 정식 작품명\n"
            "- snippet canonical author: 작가명\n"
            "- 이 제목은 약칭, 본문 앵커, 작가/캐릭터 단서가 결합된 스니펫 기반 정식 후보입니다.\n"
            "- 이후 검색에서 표면 유사 후보가 나타나더라도, "
            "본문 직접 단서와 작가/캐릭터 결합이 약한 후보로 대체하지 마세요.\n",
        )

    def test_omits_empty_author_line(self) -> None:
        prompt = _build_snippet_canonical_lock_prompt("정식 작품명")

        self.assertIn("snippet canonical title: 정식 작품명", prompt)
        self.assertNotIn("snippet canonical author:", prompt)

    def test_empty_title_returns_empty_prompt(self) -> None:
        self.assertEqual(_build_snippet_canonical_lock_prompt("", "작가명"), "")


if __name__ == "__main__":
    unittest.main()
