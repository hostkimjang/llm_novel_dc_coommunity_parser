from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


RUN_ID = "20260505_214349_324347"
DEFAULT_BROWSER_SURFACE = "fallback_playwright_cli"
DIRECT_BROWSER_SURFACE = "fallback_playwright_node"
PREFERRED_BROWSER_SURFACE = "codex_in_app_browser_iab"
ARTICLE_IMAGE_SELECTORS = [
    ".write_div .img_area .imgwrap > img",
    ".write_div .img_area img",
    ".write_div div.imgwrap > img",
    ".write_div img[data-original*='dcimg']",
    ".write_div img[src*='dcimg']",
]
ARTICLE_ATTACHMENT_SELECTORS = [
    ".appending_file a",
    ".write_div a[href*='download.php']",
    ".write_div a[href*='viewimagePop.php']",
    "a[href*='image.dcinside.com/download.php']",
]
WINDOWS_CMD_META_PATTERN = re.compile(r"[&|<>^()]")
WINDOWS_CMD_META_ESCAPES = {
    "^": "^^^^",
    "&": "^^^&",
    "|": "^^^|",
    "<": "^^^<",
    ">": "^^^>",
    "(": "^^^(",
    ")": "^^^)",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def safe_name(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "unknown"))[:120]


def compact_text(value: Any, limit: int = 1500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def contains(haystack: Any, needle: Any) -> bool:
    needle_text = str(needle or "").strip().lower()
    if not needle_text:
        return False
    return needle_text in str(haystack or "").lower()


def escape_windows_cmd_arg(value: str) -> str:
    if not value or re.search(r"\s", value) or not WINDOWS_CMD_META_PATTERN.search(value):
        return value
    # npx.cmd expands %* inside a batch file, so metacharacters need to
    # survive both the initial cmd.exe parse and the wrapper's second parse.
    return "".join(WINDOWS_CMD_META_ESCAPES.get(char, char) for char in value)


def cmd_safe_args(executable: str, args: Iterable[str]) -> list[str]:
    if sys.platform != "win32" or not executable.lower().endswith((".cmd", ".bat")):
        return list(args)
    return [escape_windows_cmd_arg(str(arg)) for arg in args]


def playwright_cmd(session: str, *args: str) -> list[str]:
    npx = shutil.which("npx.cmd") or shutil.which("npx") or "npx"
    tail_args = [
        "--yes",
        "--package",
        "@playwright/cli",
        "playwright-cli",
        f"-s={session}",
        *args,
    ]
    return [
        npx,
        *cmd_safe_args(npx, tail_args),
    ]


def _installed_playwright_browser_revision(node_modules: Path) -> str:
    browsers_path = node_modules / "playwright-core" / "browsers.json"
    if not browsers_path.exists():
        return ""
    try:
        payload = json.loads(browsers_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    for browser in payload.get("browsers") or []:
        if not isinstance(browser, dict):
            continue
        if browser.get("name") in {"chromium-headless-shell", "chromium"}:
            revision = str(browser.get("revision") or "").strip()
            if revision:
                return revision
    return ""


def _has_installed_playwright_browser(node_modules: Path) -> bool:
    revision = _installed_playwright_browser_revision(node_modules)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not revision or not local_app_data:
        return False
    browser_root = Path(local_app_data) / "ms-playwright"
    return any(
        (browser_root / f"{prefix}-{revision}").exists()
        for prefix in ("chromium_headless_shell", "chromium")
    )


def _node_modules_supports_playwright(node_modules: Path) -> bool:
    return (
        (node_modules / "playwright").exists()
        and (node_modules / "playwright-core").exists()
        and _has_installed_playwright_browser(node_modules)
    )


@lru_cache(maxsize=1)
def find_playwright_node_modules() -> str:
    explicit = os.environ.get("PLAYWRIGHT_NODE_MODULES")
    if explicit:
        explicit_path = Path(explicit)
        if _node_modules_supports_playwright(explicit_path):
            return str(explicit_path)

    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        npx_root = Path(local_app_data) / "npm-cache" / "_npx"
        if npx_root.exists():
            candidates.extend(path / "node_modules" for path in npx_root.iterdir() if path.is_dir())

    candidates.sort(key=lambda path: path.parent.stat().st_mtime if path.parent.exists() else 0, reverse=True)
    for node_modules in candidates:
        if _node_modules_supports_playwright(node_modules):
            return str(node_modules)
    return ""


def node_cmd() -> str:
    bundled = os.environ.get("CODEX_NODE_EXE")
    if bundled and Path(bundled).exists():
        return bundled
    return shutil.which("node.exe") or shutil.which("node") or "node"


def run_cli(session: str, *args: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        playwright_cmd(session, *args),
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )


def parse_eval_payload_from_stdout(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


def load_eval_payload(eval_path: Path, eval_proc: subprocess.CompletedProcess[str]) -> tuple[dict[str, Any], str]:
    if eval_path.exists():
        raw = eval_path.read_text(encoding="utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"_decode_error": raw[:500]}, "file_decode_error"
        return (payload if isinstance(payload, dict) else {"_decode_error": raw[:500]}), "file"

    payload = parse_eval_payload_from_stdout(eval_proc.stdout)
    if payload:
        write_json(eval_path, payload)
        return payload, "stdout"
    return {}, "missing"


def detect_blocked(text: str, title: str) -> list[str]:
    combined = f"{title}\n{text}".lower()
    signals = [
        "captcha",
        "access denied",
        "blocked",
        "robot",
        "비정상적인 접근",
        "자동입력",
        "접근이 제한",
        "접근 제한",
        "접근이 차단",
        "ip가 차단",
        "아이피가 차단",
        "차단되었습니다",
        "삭제된 게시물",
        "게시글이 존재하지",
        "비공개 게시물",
        "성인인증",
        "로그인이 필요",
    ]
    return [signal for signal in signals if signal in combined]


def evidence_grade(
    *,
    title: str,
    body_text: str,
    target_title: str,
    post_id: Any,
    screenshot_ok: bool,
    blocked_signals: list[str],
    open_return_code: int,
    eval_return_code: int,
    article_image_count: int,
    article_loaded_count: int,
    article_incomplete_count: int,
    article_placeholder_count: int,
    article_broken_count: int,
    article_lazy_pending_count: int,
    data_original_pending_count: int,
    placeholder_current_src_count: int,
    article_attachment_file_count: int = 0,
) -> str:
    if blocked_signals or not screenshot_ok:
        return "Missing"
    if open_return_code != 0 or eval_return_code != 0:
        return "Weak"
    if article_image_count <= 0:
        return "Weak" if article_attachment_file_count > 0 else "Missing"
    if (
        article_placeholder_count > 0
        or article_broken_count > 0
        or article_lazy_pending_count > 0
        or data_original_pending_count > 0
        or placeholder_current_src_count > 0
    ):
        return "Weak"
    if article_incomplete_count > 0 or article_loaded_count < article_image_count:
        return "Weak"
    if contains(title, target_title) or contains(body_text, target_title) or contains(body_text, post_id):
        return "Strong"
    if len(body_text) > 200:
        return "Medium"
    return "Weak"


def build_observation(grade: str) -> str:
    if grade == "Strong":
        return "브라우저에서 원문 페이지가 열렸고 제목/post id 단서와 본문 이미지 로딩 게이트가 함께 확인된다."
    if grade == "Medium":
        return "본문 이미지는 로드됐지만 원문 제목 직접 일치는 약해 추가 판독이 필요하다."
    if grade == "Weak":
        return "브라우저 접근은 되었으나 본문 이미지 로딩/본문 단서가 약해 ACCEPT 근거로 쓰기 어렵다."
    return "브라우저 접근 실패, 차단, 스크린샷 실패, 본문 이미지 노드 미검출, 또는 이미지 로딩 근거 없음 중 하나가 있어 Missing evidence로 취급한다."


def image_state_eval_func() -> str:
    selectors = json.dumps(ARTICLE_IMAGE_SELECTORS)
    attachment_selectors = json.dumps(ARTICLE_ATTACHMENT_SELECTORS)
    return f"""async () => {{
  const selectors = {selectors};
  const attachmentSelectors = {attachment_selectors};
  const ignoredAncestorPattern = /(?:rcont_imgtxt_box|reply|comment|kcaptcha|captcha|recommend|ad_|advert|gall_list|issuebox|minor_intro_box)/i;
  const hasIgnoredAncestor = (node) => {{
    let cur = node;
    for (let depth = 0; cur && depth < 8; depth += 1, cur = cur.parentElement) {{
      const marker = [cur.id || '', String(cur.className || ''), cur.tagName || ''].join(' ');
      if (ignoredAncestorPattern.test(marker)) return true;
      if (String(cur.className || '').includes('write_div')) return false;
    }}
    return false;
  }};
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const collectCandidateImages = () => {{
    const seen = new Set();
    const candidates = [];
    for (const selector of selectors) {{
      for (const img of Array.from(document.querySelectorAll(selector))) {{
        if (seen.has(img)) continue;
        seen.add(img);
        if (hasIgnoredAncestor(img)) continue;
        candidates.push(img);
      }}
    }}
    return candidates;
  }};
  const normalizeUrl = (value) => String(value || '').replace(/&amp;/g, '&').trim();
  const normalizeAttachmentHref = (href) => {{
    const text = String(href || '');
    const popup = text.match(/imgPop\\('([^']+)/);
    if (popup) return popup[1].replace(/%27/g, '');
    return text;
  }};
  const collectAttachmentLinks = () => {{
    const seen = new Set();
    const links = [];
    for (const selector of attachmentSelectors) {{
      for (const anchor of Array.from(document.querySelectorAll(selector))) {{
        const rawHref = anchor.getAttribute('href') || anchor.href || '';
        const href = normalizeUrl(normalizeAttachmentHref(rawHref));
        const text = String(anchor.innerText || anchor.textContent || '').trim();
        if (!href || seen.has(href)) continue;
        seen.add(href);
        links.push({{
          text,
          href,
          isImagePopup: /viewimagePop\\.php|viewimage\\.php/i.test(href),
          isDownload: /download\\.php/i.test(href),
        }});
      }}
    }}
    return links;
  }};

  const initialCandidates = collectCandidateImages();
  for (const img of initialCandidates.slice(0, 12)) {{
    try {{
      img.scrollIntoView({{ block: 'center', inline: 'nearest' }});
      await sleep(450);
    }} catch (_err) {{}}
  }}
  await sleep(800);

  const candidateImages = collectCandidateImages();
  const attachmentLinks = collectAttachmentLinks();
  const articleImages = [];
  for (const img of candidateImages) {{
    const rect = img.getBoundingClientRect();
      const dataOriginal = img.getAttribute('data-original') || img.getAttribute('data-src') || img.getAttribute('data-lazy') || '';
      const src = img.currentSrc || img.src || dataOriginal || '';
      const className = String(img.className || '');
      const parentClass = img.parentElement ? String(img.parentElement.className || '') : '';
      const grandParentClass = img.parentElement && img.parentElement.parentElement ? String(img.parentElement.parentElement.className || '') : '';
      const stateText = [src, dataOriginal, className, parentClass, grandParentClass].join(' ');
      const placeholderSrc = /gallview_loading|loading_btntype|l_load|placeholder|blank\\.gif|lazyload\\.gif/i.test(src);
      const isPlaceholder = /gallview_loading|loading_btntype|l_load|placeholder|blank\\.gif|lazyload\\.gif/i.test(stateText);
      const dataOriginalPending = Boolean(dataOriginal) && normalizeUrl(src) !== normalizeUrl(dataOriginal);
      const lazyPending = Boolean(placeholderSrc || dataOriginalPending);
      articleImages.push({{
        idx: articleImages.length,
        src,
        dataOriginal,
        alt: img.getAttribute('alt') || '',
        className,
        parentClass,
        grandParentClass,
        complete: Boolean(img.complete),
        naturalWidth: img.naturalWidth || 0,
        naturalHeight: img.naturalHeight || 0,
        renderedWidth: Math.round(rect.width || 0),
        renderedHeight: Math.round(rect.height || 0),
        visibleInViewport: rect.bottom >= 0 && rect.right >= 0 && rect.top <= window.innerHeight && rect.left <= window.innerWidth,
        isPlaceholder,
        placeholderSrc,
        dataOriginalPending,
        lazyPending,
      }});
  }}
  const broken = articleImages.filter((img) => img.complete && (img.naturalWidth <= 0 || img.naturalHeight <= 0)).length;
  const incomplete = articleImages.filter((img) => !img.complete || img.naturalWidth <= 0 || img.naturalHeight <= 0).length;
  const placeholder = articleImages.filter((img) => img.isPlaceholder).length;
  const placeholderCurrentSrc = articleImages.filter((img) => img.placeholderSrc).length;
  const dataOriginalPending = articleImages.filter((img) => img.dataOriginalPending).length;
  const lazyPending = articleImages.filter((img) => img.lazyPending).length;
  return {{
    title: document.title,
    bodyText: document.body ? document.body.innerText.slice(0, 5000) : '',
    url: location.href,
    readyState: document.readyState,
    scrollY: window.scrollY,
    documentHeight: Math.max(document.body ? document.body.scrollHeight : 0, document.documentElement ? document.documentElement.scrollHeight : 0),
    articleImageSelectors: selectors,
    articleAttachmentSelectors: attachmentSelectors,
    articleCandidateImageCount: candidateImages.length,
    articleImageCount: articleImages.length,
    articleLoadedCount: articleImages.filter((img) => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0 && !img.isPlaceholder).length,
    articleIncompleteCount: incomplete,
    articlePlaceholderCount: placeholder,
    articleBrokenCount: broken,
    articleLazyPendingCount: lazyPending,
    dataOriginalPendingCount: dataOriginalPending,
    placeholderCurrentSrcCount: placeholderCurrentSrc,
    articleImages: articleImages.slice(0, 20),
    articleAttachmentFileCount: attachmentLinks.length,
    articleAttachmentLinks: attachmentLinks.slice(0, 20),
  }};
}}"""


def direct_capture_driver_js() -> str:
    eval_func = image_state_eval_func()
    return f"""const fs = require('fs');
const {{ chromium }} = require('playwright');

const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const evaluateArticleState = {eval_func};

(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage({{ viewport: {{ width: 1280, height: 900 }} }});
  let responseStatus = null;
  try {{
    const response = await page.goto(config.url, {{ waitUntil: 'domcontentloaded', timeout: config.timeoutMs }});
    responseStatus = response ? response.status() : null;
    await page.waitForLoadState('networkidle', {{ timeout: Math.min(config.timeoutMs, 15000) }}).catch(() => null);
    await page.waitForTimeout(1200);
    const payload = await page.evaluate(evaluateArticleState);
    fs.writeFileSync(config.evalPath, JSON.stringify(payload, null, 2), 'utf8');
    await page.screenshot({{ path: config.shotPath, scale: 'css', type: 'png' }});
    console.log(JSON.stringify({{
      ok: true,
      responseStatus,
      url: page.url(),
      title: await page.title(),
    }}));
  }} finally {{
    await browser.close();
  }}
}})().catch((error) => {{
  console.error(JSON.stringify({{
    ok: false,
    name: error && error.name,
    message: error && error.message,
    stack: error && error.stack,
  }}));
  process.exit(1);
}});
"""


def write_direct_capture_driver(out_dir: Path) -> Path:
    path = out_dir / "_playwright_direct_capture_driver.js"
    path.write_text(direct_capture_driver_js(), encoding="utf-8", newline="\n")
    return path


def build_review_row(
    *,
    row: dict[str, Any],
    run_id: str,
    started_at: str,
    shot_path: Path,
    eval_path: Path,
    eval_payload: dict[str, Any],
    eval_payload_source: str,
    browser: str,
    browser_surface: str,
    open_return_code: int,
    eval_return_code: int,
    screenshot_return_code: int,
    open_stdout: str = "",
    eval_stdout: str = "",
    screenshot_stdout: str = "",
    open_stderr: str = "",
    eval_stderr: str = "",
    screenshot_stderr: str = "",
    capture_engine: str = "",
) -> dict[str, Any]:
    post_id = row.get("post_id")

    page_title = str(eval_payload.get("title") or "")
    body_text = str(eval_payload.get("bodyText") or "")
    blocked_signals = detect_blocked(body_text, page_title)
    screenshot_ok = shot_path.exists() and shot_path.stat().st_size > 0
    article_image_count = int(eval_payload.get("articleImageCount") or 0)
    article_loaded_count = int(eval_payload.get("articleLoadedCount") or 0)
    article_incomplete_count = int(eval_payload.get("articleIncompleteCount") or 0)
    article_placeholder_count = int(eval_payload.get("articlePlaceholderCount") or 0)
    article_broken_count = int(eval_payload.get("articleBrokenCount") or 0)
    article_lazy_pending_count = int(eval_payload.get("articleLazyPendingCount") or 0)
    data_original_pending_count = int(eval_payload.get("dataOriginalPendingCount") or 0)
    placeholder_current_src_count = int(eval_payload.get("placeholderCurrentSrcCount") or 0)
    article_attachment_file_count = int(eval_payload.get("articleAttachmentFileCount") or 0)
    grade = evidence_grade(
        title=page_title,
        body_text=body_text,
        target_title=str(row.get("title") or ""),
        post_id=post_id,
        screenshot_ok=screenshot_ok,
        blocked_signals=blocked_signals,
        open_return_code=open_return_code,
        eval_return_code=eval_return_code,
        article_image_count=article_image_count,
        article_loaded_count=article_loaded_count,
        article_incomplete_count=article_incomplete_count,
        article_placeholder_count=article_placeholder_count,
        article_broken_count=article_broken_count,
        article_lazy_pending_count=article_lazy_pending_count,
        data_original_pending_count=data_original_pending_count,
        placeholder_current_src_count=placeholder_current_src_count,
        article_attachment_file_count=article_attachment_file_count,
    )

    return {
        "run_id": run_id,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "capture_started_at": started_at,
        "post_id": post_id,
        "url": row.get("url"),
        "title": row.get("title"),
        "exit_action": row.get("exit_action"),
        "quarantine_category": row.get("quarantine_category"),
        "primary_pattern": row.get("primary_pattern"),
        "previous_label": row.get("previous_label"),
        "previous_action": row.get("previous_action"),
        "previous_evidence_grade": row.get("previous_evidence_grade"),
        "browser": browser,
        "browser_surface": browser_surface,
        "capture_engine": capture_engine or browser_surface,
        "preferred_browser_surface": PREFERRED_BROWSER_SURFACE,
        "fallback_reason": (
            "Codex 내장 Browser plugin @browser / in-app browser iab 사용이 기본 지침이다. "
            "이 CLI는 내장 브라우저가 실제로 불가능하거나 대량 배치 캡처 fallback이 필요할 때만 사용한다."
        ),
        "viewport": "playwright-cli default viewport",
        "page_url": eval_payload.get("url"),
        "page_title": page_title,
        "page_ready_state": eval_payload.get("readyState"),
        "title_seen": contains(page_title, row.get("title")) or contains(body_text, row.get("title")),
        "post_id_seen": contains(body_text, post_id),
        "blocked_signals": blocked_signals,
        "screenshot_path": str(shot_path.resolve()) if screenshot_ok else None,
        "screenshot_ok": screenshot_ok,
        "eval_path": str(eval_path.resolve()) if eval_path.exists() else None,
        "eval_payload_source": eval_payload_source,
        "article_image_selectors": eval_payload.get("articleImageSelectors") or ARTICLE_IMAGE_SELECTORS,
        "article_attachment_selectors": eval_payload.get("articleAttachmentSelectors") or ARTICLE_ATTACHMENT_SELECTORS,
        "article_image_count": article_image_count,
        "article_loaded_count": article_loaded_count,
        "article_incomplete_count": article_incomplete_count,
        "article_placeholder_count": article_placeholder_count,
        "article_broken_count": article_broken_count,
        "article_lazy_pending_count": article_lazy_pending_count,
        "data_original_pending_count": data_original_pending_count,
        "placeholder_current_src_count": placeholder_current_src_count,
        "article_attachment_file_count": article_attachment_file_count,
        "article_attachment_links": eval_payload.get("articleAttachmentLinks") or [],
        "article_images_sample": eval_payload.get("articleImages") or [],
        "visual_evidence_grade": grade,
        "body_text_excerpt": compact_text(body_text),
        "visual_observation_ko": build_observation(grade),
        "accept_guard_ko": (
            "시각 접근과 본문 이미지 로딩 게이트는 통과했지만, 최종 ACCEPT는 모델 판정/evidence/reason 재검토 이후에만 가능하다."
            if grade == "Strong"
            else "지침상 브라우저 시각 근거 또는 본문 이미지 로딩 근거가 약하거나 없으므로 이 행은 ACCEPT로 승격하지 않는다."
        ),
        "cli": {
            "open_return_code": open_return_code,
            "eval_return_code": eval_return_code,
            "screenshot_return_code": screenshot_return_code,
            "open_stdout_excerpt": compact_text(open_stdout, 800),
            "eval_stdout_excerpt": compact_text(eval_stdout, 800),
            "screenshot_stdout_excerpt": compact_text(screenshot_stdout, 800),
            "open_stderr_excerpt": compact_text(open_stderr, 800),
            "eval_stderr_excerpt": compact_text(eval_stderr, 800),
            "screenshot_stderr_excerpt": compact_text(screenshot_stderr, 800),
        },
    }


def capture_one_direct(row: dict[str, Any], out_dir: Path, timeout: int, run_id: str) -> dict[str, Any]:
    post_id = row.get("post_id")
    shot_path = out_dir / f"{safe_name(post_id)}.png"
    eval_path = out_dir / f"{safe_name(post_id)}.eval.json"
    config_path = out_dir / f"{safe_name(post_id)}.capture.config.json"
    started_at = datetime.now().isoformat(timespec="seconds")
    driver_path = write_direct_capture_driver(out_dir)
    config = {
        "url": str(row.get("url") or ""),
        "shotPath": str(shot_path),
        "evalPath": str(eval_path),
        "timeoutMs": max(timeout * 1000, 1000),
    }
    write_json(config_path, config)
    env = os.environ.copy()
    env["NODE_PATH"] = find_playwright_node_modules()
    proc = subprocess.run(
        [node_cmd(), str(driver_path), str(config_path)],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout + 30,
        env=env,
    )
    eval_payload, eval_payload_source = load_eval_payload(
        eval_path,
        subprocess.CompletedProcess(proc.args, proc.returncode, stdout="", stderr=proc.stderr),
    )
    return build_review_row(
        row=row,
        run_id=run_id,
        started_at=started_at,
        shot_path=shot_path,
        eval_path=eval_path,
        eval_payload=eval_payload,
        eval_payload_source=eval_payload_source,
        browser="playwright chromium direct",
        browser_surface=DIRECT_BROWSER_SURFACE,
        open_return_code=proc.returncode,
        eval_return_code=proc.returncode,
        screenshot_return_code=0 if shot_path.exists() else proc.returncode,
        open_stdout=proc.stdout,
        eval_stdout=proc.stdout,
        screenshot_stdout=proc.stdout,
        open_stderr=proc.stderr,
        eval_stderr=proc.stderr,
        screenshot_stderr=proc.stderr,
        capture_engine="playwright_node_direct",
    )


def capture_one_cli(row: dict[str, Any], out_dir: Path, session: str, timeout: int, run_id: str) -> dict[str, Any]:
    post_id = row.get("post_id")
    shot_path = out_dir / f"{safe_name(post_id)}.png"
    eval_path = out_dir / f"{safe_name(post_id)}.eval.json"
    started_at = datetime.now().isoformat(timespec="seconds")

    open_proc = run_cli(session, "open", str(row.get("url") or ""), timeout=timeout)
    eval_func = image_state_eval_func()
    eval_proc = run_cli(session, "eval", eval_func, "--filename", str(eval_path), timeout=timeout)
    screenshot_proc = run_cli(session, "screenshot", "--filename", str(shot_path), timeout=timeout)

    eval_payload, eval_payload_source = load_eval_payload(eval_path, eval_proc)
    return build_review_row(
        row=row,
        run_id=run_id,
        started_at=started_at,
        shot_path=shot_path,
        eval_path=eval_path,
        eval_payload=eval_payload,
        eval_payload_source=eval_payload_source,
        browser="playwright-cli chromium",
        browser_surface=DEFAULT_BROWSER_SURFACE,
        open_return_code=open_proc.returncode,
        eval_return_code=eval_proc.returncode,
        screenshot_return_code=screenshot_proc.returncode,
        open_stdout=open_proc.stdout,
        eval_stdout=eval_proc.stdout,
        screenshot_stdout=screenshot_proc.stdout,
        open_stderr=open_proc.stderr,
        eval_stderr=eval_proc.stderr,
        screenshot_stderr=screenshot_proc.stderr,
        capture_engine="playwright_cli",
    )


def capture_one(row: dict[str, Any], out_dir: Path, session: str, timeout: int, run_id: str) -> dict[str, Any]:
    if find_playwright_node_modules():
        return capture_one_direct(row, out_dir, timeout, run_id)
    return capture_one_cli(row, out_dir, session, timeout, run_id)


def write_summary(path: Path, manifest: dict[str, Any], reviews: list[dict[str, Any]]) -> None:
    lines = [
        "# VLM/OCR 브라우저 시각 확인",
        "",
        f"- 생성 시각: `{manifest['generated_at']}`",
        f"- target row 수: `{manifest['target_rows']}`",
        f"- capture row 수: `{manifest['captured_rows']}`",
        f"- screenshot 성공: `{manifest['screenshot_ok_rows']}`",
        f"- blocked/error 후보: `{manifest['blocked_rows'] + manifest['error_rows']}`",
        f"- 본문 이미지 없음: `{manifest['article_image_missing_rows']}`",
        f"- 첨부파일 링크만 확인됨: `{manifest['article_attachment_only_rows']}`",
        f"- 본문 이미지 로딩 미완료/placeholder/broken: `{manifest['article_image_gate_failed_rows']}`",
        f"- 본문 이미지 게이트 통과: `{manifest['article_image_gate_passed_rows']}`",
        f"- lazy/data-original 교체 대기: `{manifest['article_lazy_pending_rows']}`",
        "",
        "## 시각 증거 등급",
        "",
    ]
    for grade, count in sorted(manifest["visual_evidence_grade_counts"].items()):
        lines.append(f"- `{grade}`: `{count}`")
    lines.extend(["", "## 대표 확인 결과", ""])
    for row in reviews[:20]:
        lines.append(
            f"- post `{row.get('post_id')}` / `{row.get('visual_evidence_grade')}` / "
            f"images=`{row.get('article_loaded_count')}/{row.get('article_image_count')}` / "
            f"attachments=`{row.get('article_attachment_file_count')}` / "
            f"placeholder=`{row.get('article_placeholder_count')}` / "
            f"lazy_pending=`{row.get('article_lazy_pending_count')}` / "
            f"broken=`{row.get('article_broken_count')}` / "
            f"screenshot=`{row.get('screenshot_path')}` / {row.get('visual_observation_ko')}"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "VLM/OCR 격리 행을 Playwright CLI fallback으로 열고 스크린샷 근거를 남긴다. "
            "기본 지침은 Codex 내장 Browser plugin @browser / in-app browser iab 우선이다."
        )
    )
    parser.add_argument(
        "--targets",
        default=f"qualitative_review/{RUN_ID}/round3_exit_re_search_re_run_p36_vlm_ocr_browser_targets.jsonl",
    )
    parser.add_argument("--out-dir", default=f"qualitative_review/{RUN_ID}/browser_visual_vlm_ocr")
    parser.add_argument("--output", default=None)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--summary", default=None)
    parser.add_argument("--session", default="vlm_ocr_review")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--run-id", default=RUN_ID)
    args = parser.parse_args()

    target_path = Path(args.targets)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else out_dir / "vlm_ocr_browser_visual_reviews.jsonl"
    manifest_path = Path(args.manifest) if args.manifest else out_dir / "vlm_ocr_browser_visual_manifest.json"
    summary_path = Path(args.summary) if args.summary else out_dir / "vlm_ocr_browser_visual_summary_ko.md"

    rows = load_jsonl(target_path)
    selected = rows[: args.limit] if args.limit and args.limit > 0 else rows
    reviews: list[dict[str, Any]] = []
    use_direct = bool(find_playwright_node_modules())

    try:
        for row in selected:
            reviews.append(capture_one(row, out_dir, args.session, args.timeout, args.run_id))
    finally:
        if not use_direct:
            run_cli(args.session, "close", timeout=30)

    write_jsonl(output_path, reviews)
    grade_counts = Counter(str(row.get("visual_evidence_grade")) for row in reviews)
    manifest = {
        "run_id": args.run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "targets_path": str(target_path.resolve()),
        "output_path": str(output_path.resolve()),
        "summary_path": str(summary_path.resolve()),
        "out_dir": str(out_dir.resolve()),
        "browser_surface": DIRECT_BROWSER_SURFACE if use_direct else DEFAULT_BROWSER_SURFACE,
        "preferred_browser_surface": PREFERRED_BROWSER_SURFACE,
        "fallback_policy": (
            "Codex 내장 Browser plugin @browser / in-app browser iab를 1순위로 사용한다. "
            "이 manifest는 Playwright fallback 산출물이므로 fallback 사유와 함께 해석해야 한다."
        ),
        "capture_engine_counts": dict(Counter(str(row.get("capture_engine") or "") for row in reviews)),
        "target_rows": len(rows),
        "captured_rows": len(reviews),
        "visual_evidence_grade_counts": dict(grade_counts),
        "screenshot_ok_rows": sum(1 for row in reviews if row.get("screenshot_ok")),
        "blocked_rows": sum(1 for row in reviews if row.get("blocked_signals")),
        "article_image_missing_rows": sum(1 for row in reviews if int(row.get("article_image_count") or 0) <= 0),
        "article_attachment_only_rows": sum(
            1
            for row in reviews
            if int(row.get("article_image_count") or 0) <= 0
            and int(row.get("article_attachment_file_count") or 0) > 0
        ),
        "article_image_gate_failed_rows": sum(
            1
            for row in reviews
            if int(row.get("article_image_count") or 0) > 0
            and (
                int(row.get("article_loaded_count") or 0) < int(row.get("article_image_count") or 0)
                or int(row.get("article_incomplete_count") or 0) > 0
                or int(row.get("article_placeholder_count") or 0) > 0
                or int(row.get("article_broken_count") or 0) > 0
                or int(row.get("article_lazy_pending_count") or 0) > 0
                or int(row.get("data_original_pending_count") or 0) > 0
                or int(row.get("placeholder_current_src_count") or 0) > 0
            )
        ),
        "article_lazy_pending_rows": sum(
            1
            for row in reviews
            if int(row.get("article_lazy_pending_count") or 0) > 0
            or int(row.get("data_original_pending_count") or 0) > 0
            or int(row.get("placeholder_current_src_count") or 0) > 0
        ),
        "article_image_gate_passed_rows": sum(
            1
            for row in reviews
            if int(row.get("article_image_count") or 0) > 0
            and int(row.get("article_loaded_count") or 0) == int(row.get("article_image_count") or 0)
            and int(row.get("article_incomplete_count") or 0) == 0
            and int(row.get("article_placeholder_count") or 0) == 0
            and int(row.get("article_broken_count") or 0) == 0
            and int(row.get("article_lazy_pending_count") or 0) == 0
            and int(row.get("data_original_pending_count") or 0) == 0
            and int(row.get("placeholder_current_src_count") or 0) == 0
        ),
        "error_rows": sum(
            1
            for row in reviews
            if row.get("cli", {}).get("open_return_code") != 0 or row.get("cli", {}).get("eval_return_code") != 0
        ),
    }
    write_json(manifest_path, manifest)
    write_summary(summary_path, manifest, reviews)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
