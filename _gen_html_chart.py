"""전체 303건 인터랙티브 HTML 차트 생성"""
import json
from pathlib import Path

RESULT_FILE = Path("out/expert_result_20260208_220427.json")
OUTPUT_HTML = Path("ALL_POSTS_CHART.html")

with open(RESULT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

relevant_posts = []
noise_posts = []

for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    ni = ident.get("novel_identity") or {}

    pid = item.get("post_id", "?")
    ptitle = item.get("title", "")
    content = item.get("content") or []
    ctext = " ".join(content) if isinstance(content, list) else str(content)
    comments = item.get("comments") or []

    is_rel = ident.get("is_relevant", False)
    official_title = ni.get("official_title") or "-"
    conf = ni.get("confidence") or "-"
    dt = ident.get("discussion_type", "-")
    reason = ident.get("reason") or ""

    # 정리
    content_short = ctext.replace("type=image ", "📷").replace("url=", "")
    if len(content_short) > 100:
        content_short = content_short[:100] + "…"

    reason_short = reason[:150]
    if len(reason) > 150:
        reason_short += "…"

    row = {
        "pid": pid,
        "ptitle": ptitle[:50],
        "content": content_short,
        "official_title": official_title[:30],
        "conf": conf,
        "dt": dt,
        "reason": reason_short,
        "comment_count": len(comments),
    }

    if is_rel:
        relevant_posts.append(row)
    else:
        noise_posts.append(row)


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


html_parts = []
H = html_parts.append

H("""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>전체 게시글 판정 차트</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
h1 { color: #58a6ff; margin-bottom: 8px; }
h2 { color: #f0883e; margin: 30px 0 12px; }
.info { color: #8b949e; margin-bottom: 20px; font-size: 14px; }
.stats { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 20px; display: flex; gap: 30px; flex-wrap: wrap; }
.stat-item { text-align: center; }
.stat-num { font-size: 28px; font-weight: bold; color: #58a6ff; }
.stat-label { font-size: 12px; color: #8b949e; }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 30px; }
th { background: #161b22; color: #58a6ff; padding: 8px 6px; text-align: left; position: sticky; top: 0; border-bottom: 2px solid #30363d; white-space: nowrap; }
td { padding: 6px; border-bottom: 1px solid #21262d; vertical-align: top; }
tr:hover { background: #161b22; }
tr.checked { background: #2d1b1b !important; }
tr.checked td { color: #f85149; }
.chk { width: 18px; height: 18px; cursor: pointer; accent-color: #f85149; }
.opinion { width: 100%; min-width: 120px; background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 4px; padding: 4px 6px; font-size: 12px; }
.opinion:focus { border-color: #58a6ff; outline: none; }
.conf-high { color: #3fb950; font-weight: bold; }
.conf-max { color: #58a6ff; font-weight: bold; }
.conf-med { color: #d29922; font-weight: bold; }
.conf-low { color: #f85149; font-weight: bold; }
.conf-unk { color: #8b949e; }
.btn { background: #238636; color: #fff; border: none; padding: 10px 24px; border-radius: 6px; font-size: 14px; cursor: pointer; margin: 10px 5px; }
.btn:hover { background: #2ea043; }
.btn-danger { background: #da3633; }
.btn-danger:hover { background: #f85149; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.badge-relevant { background: #238636; color: #fff; }
.badge-noise { background: #6e7681; color: #fff; }
.badge-review { background: #1f6feb; }
.badge-char { background: #8957e5; }
.badge-general { background: #388bfd; }
.badge-meme { background: #d29922; }
.badge-antic { background: #3fb950; }
.badge-rec { background: #f78166; }
.badge-meta { background: #6e7681; }
.counter { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 20px; margin: 15px 0; display: inline-block; }
.counter strong { color: #f85149; font-size: 20px; }
#export-area { display: none; width: 100%; min-height: 200px; background: #161b22; color: #c9d1d9; border: 1px solid #30363d; border-radius: 8px; padding: 12px; font-family: monospace; font-size: 12px; margin-top: 10px; }
.filter-bar { margin: 10px 0; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.filter-bar label { font-size: 13px; color: #8b949e; }
.filter-bar select, .filter-bar input { background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 4px; padding: 4px 8px; font-size: 13px; }
</style>
</head>
<body>
<h1>📋 전체 게시글 판정 차트</h1>
<div class="info">파일: out/expert_result_20260208_220427.json | 생성일: 2026-02-09</div>

<div class="stats">
  <div class="stat-item"><div class="stat-num">""" + str(len(relevant_posts) + len(noise_posts)) + """</div><div class="stat-label">총 게시글</div></div>
  <div class="stat-item"><div class="stat-num" style="color:#3fb950">""" + str(len(relevant_posts)) + """</div><div class="stat-label">Relevant</div></div>
  <div class="stat-item"><div class="stat-num" style="color:#8b949e">""" + str(len(noise_posts)) + """</div><div class="stat-label">Noise</div></div>
  <div class="stat-item"><div class="stat-num" style="color:#f85149"><span id="total-checked">0</span></div><div class="stat-label">오판 체크</div></div>
</div>

<div style="margin-bottom:20px;">
  <button class="btn" onclick="exportChecked()">📋 체크된 항목 복사</button>
  <button class="btn btn-danger" onclick="clearAll()">🗑️ 전체 초기화</button>
  <button class="btn" style="background:#1f6feb" onclick="saveToLocal()">💾 저장 (로컬)</button>
  <button class="btn" style="background:#6e7681" onclick="loadFromLocal()">📂 불러오기</button>
</div>
""")

# ===== Part A =====
H("""
<h2>✅ Part A: Relevant 판정 (소설 관련) — """ + str(len(relevant_posts)) + """건</h2>
<div class="counter">체크된 FP: <strong id="fp-count">0</strong>건</div>
<div class="filter-bar">
  <label>Type:</label>
  <select onchange="filterTable('table-a', this.value, 'type')">
    <option value="">전체</option>
    <option value="review">review</option>
    <option value="character_talk">character_talk</option>
    <option value="general">general</option>
    <option value="anticipation">anticipation</option>
    <option value="meme">meme</option>
    <option value="recommendation">recommendation</option>
  </select>
  <label>Conf:</label>
  <select onchange="filterTable('table-a', this.value, 'conf')">
    <option value="">전체</option>
    <option value="High">High</option>
    <option value="Max">Max</option>
    <option value="Medium">Medium</option>
    <option value="Low">Low</option>
  </select>
  <label>검색:</label>
  <input type="text" placeholder="제목/내용 검색..." oninput="searchTable('table-a', this.value)">
</div>
<table id="table-a">
<thead>
<tr>
  <th style="width:35px">오판</th>
  <th style="width:30px">#</th>
  <th>Post ID</th>
  <th>게시글 제목</th>
  <th>식별 제목</th>
  <th>Conf</th>
  <th>Type</th>
  <th>본문 요약</th>
  <th style="width:35px">💬</th>
  <th>Reason</th>
  <th style="min-width:150px">내 의견</th>
</tr>
</thead>
<tbody>
""")

for i, r in enumerate(relevant_posts, 1):
    conf_cls = {"High": "conf-high", "Max": "conf-max", "Medium": "conf-med", "Low": "conf-low"}.get(r["conf"], "conf-unk")
    dt_cls = {"review": "badge-review", "character_talk": "badge-char", "general": "badge-general",
              "meme": "badge-meme", "anticipation": "badge-antic", "recommendation": "badge-rec",
              "meta": "badge-meta"}.get(r["dt"], "badge-noise")
    H(f"""<tr data-type="{esc(r['dt'])}" data-conf="{esc(r['conf'])}">
  <td><input type="checkbox" class="chk" data-section="A" data-pid="{r['pid']}" onchange="onCheck(this)"></td>
  <td>{i}</td>
  <td>{r['pid']}</td>
  <td>{esc(r['ptitle'])}</td>
  <td><b>{esc(r['official_title'])}</b></td>
  <td class="{conf_cls}">{r['conf']}</td>
  <td><span class="badge {dt_cls}">{r['dt']}</span></td>
  <td style="font-size:11px;color:#8b949e">{esc(r['content'][:80])}</td>
  <td>{r['comment_count']}</td>
  <td style="font-size:11px">{esc(r['reason'][:120])}</td>
  <td><input type="text" class="opinion" data-pid="{r['pid']}" placeholder="의견 입력..."></td>
</tr>""")

H("""</tbody></table>""")

# ===== Part B =====
H("""
<h2>❌ Part B: Not Relevant 판정 (노이즈) — """ + str(len(noise_posts)) + """건</h2>
<div class="counter">체크된 FN: <strong id="fn-count">0</strong>건</div>
<div class="filter-bar">
  <label>Type:</label>
  <select onchange="filterTable('table-b', this.value, 'type')">
    <option value="">전체</option>
    <option value="noise">noise</option>
    <option value="review">review</option>
    <option value="recommendation">recommendation</option>
    <option value="meta">meta</option>
  </select>
  <label>검색:</label>
  <input type="text" placeholder="제목/내용 검색..." oninput="searchTable('table-b', this.value)">
</div>
<table id="table-b">
<thead>
<tr>
  <th style="width:35px">오판</th>
  <th style="width:30px">#</th>
  <th>Post ID</th>
  <th>게시글 제목</th>
  <th>Type</th>
  <th>본문 요약</th>
  <th style="width:35px">💬</th>
  <th>Reason</th>
  <th style="min-width:150px">내 의견</th>
</tr>
</thead>
<tbody>
""")

for i, r in enumerate(noise_posts, 1):
    dt_cls = {"noise": "badge-noise", "review": "badge-review", "recommendation": "badge-rec",
              "meta": "badge-meta"}.get(r["dt"], "badge-noise")
    H(f"""<tr data-type="{esc(r['dt'])}" data-conf="">
  <td><input type="checkbox" class="chk" data-section="B" data-pid="{r['pid']}" onchange="onCheck(this)"></td>
  <td>{i}</td>
  <td>{r['pid']}</td>
  <td>{esc(r['ptitle'])}</td>
  <td><span class="badge {dt_cls}">{r['dt']}</span></td>
  <td style="font-size:11px;color:#8b949e">{esc(r['content'][:90])}</td>
  <td>{r['comment_count']}</td>
  <td style="font-size:11px">{esc(r['reason'][:120])}</td>
  <td><input type="text" class="opinion" data-pid="{r['pid']}" placeholder="의견 입력..."></td>
</tr>""")

H("""</tbody></table>""")

# ===== Script =====
H("""
<textarea id="export-area" readonly></textarea>

<script>
function updateCounts() {
  const fpCount = document.querySelectorAll('#table-a .chk:checked').length;
  const fnCount = document.querySelectorAll('#table-b .chk:checked').length;
  document.getElementById('fp-count').textContent = fpCount;
  document.getElementById('fn-count').textContent = fnCount;
  document.getElementById('total-checked').textContent = fpCount + fnCount;
}

function onCheck(el) {
  const tr = el.closest('tr');
  if (el.checked) {
    tr.classList.add('checked');
  } else {
    tr.classList.remove('checked');
  }
  updateCounts();
}

function filterTable(tableId, val, filterType) {
  const rows = document.querySelectorAll('#' + tableId + ' tbody tr');
  rows.forEach(row => {
    if (!val) { row.style.display = ''; return; }
    const attr = filterType === 'type' ? row.dataset.type : row.dataset.conf;
    row.style.display = attr === val ? '' : 'none';
  });
}

function searchTable(tableId, query) {
  const rows = document.querySelectorAll('#' + tableId + ' tbody tr');
  const q = query.toLowerCase();
  rows.forEach(row => {
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}

function exportChecked() {
  const lines = [];
  lines.push('=== 오판 체크 결과 ===\\n');

  // Part A (FP)
  const fpChecked = document.querySelectorAll('#table-a .chk:checked');
  if (fpChecked.length > 0) {
    lines.push('## False Positive (소설 아닌데 소설로 판정)\\n');
    fpChecked.forEach(chk => {
      const tr = chk.closest('tr');
      const pid = chk.dataset.pid;
      const title = tr.children[3].textContent;
      const identified = tr.children[4].textContent;
      const opinion = tr.querySelector('.opinion').value || '(없음)';
      lines.push(`- POST ${pid}: ${title}`);
      lines.push(`  식별: ${identified}`);
      lines.push(`  의견: ${opinion}\\n`);
    });
  }

  // Part B (FN)
  const fnChecked = document.querySelectorAll('#table-b .chk:checked');
  if (fnChecked.length > 0) {
    lines.push('## False Negative (소설인데 노이즈로 판정)\\n');
    fnChecked.forEach(chk => {
      const tr = chk.closest('tr');
      const pid = chk.dataset.pid;
      const title = tr.children[3].textContent;
      const opinion = tr.querySelector('.opinion').value || '(없음)';
      lines.push(`- POST ${pid}: ${title}`);
      lines.push(`  의견: ${opinion}\\n`);
    });
  }

  if (fpChecked.length === 0 && fnChecked.length === 0) {
    lines.push('체크된 항목이 없습니다.');
  }

  const text = lines.join('\\n');
  const area = document.getElementById('export-area');
  area.style.display = 'block';
  area.value = text;
  area.select();
  navigator.clipboard.writeText(text).then(() => {
    alert('클립보드에 복사되었습니다! (' + (fpChecked.length + fnChecked.length) + '건)');
  });
}

function clearAll() {
  if (!confirm('모든 체크와 의견을 초기화하시겠습니까?')) return;
  document.querySelectorAll('.chk').forEach(c => { c.checked = false; c.closest('tr').classList.remove('checked'); });
  document.querySelectorAll('.opinion').forEach(o => o.value = '');
  updateCounts();
}

function saveToLocal() {
  const state = {};
  document.querySelectorAll('.chk').forEach(c => {
    const pid = c.dataset.pid;
    const section = c.dataset.section;
    const opinion = c.closest('tr').querySelector('.opinion').value;
    if (c.checked || opinion) {
      state[section + '_' + pid] = { checked: c.checked, opinion: opinion };
    }
  });
  localStorage.setItem('post_chart_state', JSON.stringify(state));
  alert('저장 완료! (' + Object.keys(state).length + '건의 데이터)');
}

function loadFromLocal() {
  const raw = localStorage.getItem('post_chart_state');
  if (!raw) { alert('저장된 데이터가 없습니다.'); return; }
  const state = JSON.parse(raw);
  document.querySelectorAll('.chk').forEach(c => {
    const key = c.dataset.section + '_' + c.dataset.pid;
    if (state[key]) {
      c.checked = state[key].checked;
      const tr = c.closest('tr');
      if (state[key].checked) tr.classList.add('checked');
      tr.querySelector('.opinion').value = state[key].opinion || '';
    }
  });
  updateCounts();
  alert('불러오기 완료!');
}

// 자동 불러오기
window.addEventListener('load', () => {
  const raw = localStorage.getItem('post_chart_state');
  if (raw) {
    const state = JSON.parse(raw);
    document.querySelectorAll('.chk').forEach(c => {
      const key = c.dataset.section + '_' + c.dataset.pid;
      if (state[key]) {
        c.checked = state[key].checked;
        const tr = c.closest('tr');
        if (state[key].checked) tr.classList.add('checked');
        tr.querySelector('.opinion').value = state[key].opinion || '';
      }
    });
    updateCounts();
  }
});
</script>
</body>
</html>
""")

html_text = "".join(html_parts)
with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_text)

print(f"✅ Generated: {OUTPUT_HTML}")
print(f"   Relevant: {len(relevant_posts)}건, Noise: {len(noise_posts)}건")
