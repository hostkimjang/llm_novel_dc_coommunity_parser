import unittest
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory

from tools import capture_vlm_ocr_browser_review_cli as browser_review


class VlmBrowserReviewCliTest(unittest.TestCase):
    def test_article_image_selectors_do_not_count_entire_dc_view_container(self):
        self.assertNotIn(".writing_view_box img", browser_review.ARTICLE_IMAGE_SELECTORS)
        self.assertNotIn(".write_div img", browser_review.ARTICLE_IMAGE_SELECTORS)
        self.assertTrue(any(".img_area" in selector for selector in browser_review.ARTICLE_IMAGE_SELECTORS))
        self.assertTrue(any("data-original" in selector for selector in browser_review.ARTICLE_IMAGE_SELECTORS))

    def test_image_state_eval_filters_non_article_ancestors_and_tracks_original_src(self):
        script = browser_review.image_state_eval_func()

        self.assertIn("ignoredAncestorPattern", script)
        self.assertIn("rcont_imgtxt_box", script)
        self.assertIn("kcaptcha", script)
        self.assertIn("dataOriginal", script)
        self.assertIn("articleCandidateImageCount", script)
        self.assertIn("articleAttachmentFileCount", script)
        self.assertIn("viewimagePop", script)
        self.assertIn("async ()", script)
        self.assertIn("scrollIntoView", script)
        self.assertIn("await sleep", script)

    def test_evidence_grade_blocks_placeholder_or_missing_article_images(self):
        base = {
            "title": "테스트 제목 - 장르소설 마이너 갤러리",
            "body_text": "post 11097334 테스트 제목",
            "target_title": "테스트 제목",
            "post_id": 11097334,
            "screenshot_ok": True,
            "blocked_signals": [],
            "open_return_code": 0,
            "eval_return_code": 0,
            "article_image_count": 3,
            "article_loaded_count": 3,
            "article_incomplete_count": 0,
            "article_placeholder_count": 0,
            "article_broken_count": 0,
            "article_lazy_pending_count": 0,
            "data_original_pending_count": 0,
            "placeholder_current_src_count": 0,
        }

        self.assertEqual(browser_review.evidence_grade(**base), "Strong")
        self.assertEqual(browser_review.evidence_grade(**{**base, "article_image_count": 0}), "Missing")
        self.assertEqual(
            browser_review.evidence_grade(
                **{**base, "article_image_count": 0, "article_attachment_file_count": 1}
            ),
            "Weak",
        )
        self.assertEqual(browser_review.evidence_grade(**{**base, "article_placeholder_count": 1}), "Weak")
        self.assertEqual(browser_review.evidence_grade(**{**base, "article_loaded_count": 2}), "Weak")

    def test_detect_blocked_does_not_treat_generic_dc_ui_block_word_as_blocked(self):
        body = "갤로그 차단 글쓰기 본문 이미지와 댓글 영역"

        self.assertEqual(browser_review.detect_blocked(body, "정상 게시글"), [])
        self.assertIn("접근이 차단", browser_review.detect_blocked("접근이 차단되었습니다", ""))

    def test_windows_cmd_escape_protects_dc_query_ampersand(self):
        url = "https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=11718049"

        escaped = browser_review.escape_windows_cmd_arg(url)

        self.assertIn("^^^&no=11718049", escaped)
        self.assertNotIn("&no=11718049", escaped.replace("^^^&", ""))

    def test_cmd_safe_args_only_escapes_cmd_wrappers(self):
        url = "https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=11718049"

        cmd_args = browser_review.cmd_safe_args("npx.cmd", ["open", url])
        exe_args = browser_review.cmd_safe_args("node.exe", ["open", url])

        if browser_review.sys.platform == "win32":
            self.assertEqual(cmd_args[1], url.replace("&", "^^^&"))
        else:
            self.assertEqual(cmd_args[1], url)
        self.assertEqual(exe_args[1], url)

    def test_load_eval_payload_falls_back_to_stdout_and_writes_sidecar(self):
        payload = {
            "title": "테스트",
            "articleImageCount": 1,
            "articleLoadedCount": 1,
        }
        with TemporaryDirectory() as tmp_dir:
            eval_path = Path(tmp_dir) / "row.eval.json"
            proc = CompletedProcess(args=["playwright-cli", "eval"], returncode=0, stdout=f"note\n{browser_review.json.dumps(payload, ensure_ascii=False)}\n")

            loaded, source = browser_review.load_eval_payload(eval_path, proc)

            self.assertEqual(source, "stdout")
            self.assertEqual(loaded["articleImageCount"], 1)
            self.assertTrue(eval_path.exists())
            persisted = browser_review.json.loads(eval_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["articleLoadedCount"], 1)

    def test_load_eval_payload_prefers_existing_file_over_stdout(self):
        with TemporaryDirectory() as tmp_dir:
            eval_path = Path(tmp_dir) / "row.eval.json"
            eval_path.write_text('{"articleImageCount": 2}', encoding="utf-8")
            proc = CompletedProcess(args=["playwright-cli", "eval"], returncode=0, stdout='{"articleImageCount": 1}')

            loaded, source = browser_review.load_eval_payload(eval_path, proc)

            self.assertEqual(source, "file")
            self.assertEqual(loaded["articleImageCount"], 2)


if __name__ == "__main__":
    unittest.main()
