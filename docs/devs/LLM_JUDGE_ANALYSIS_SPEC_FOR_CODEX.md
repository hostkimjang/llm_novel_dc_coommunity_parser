# LLM-Judge 분석 지침 (Codex용) — 파이프라인 판정 vs 독립 재판정 head-to-head

목적: expert 파이프라인이 산출한 작품매칭 결과(run 출력)를 **독립 LLM이 post 한 건씩 재판정**해 파이프라인 결정과
대조하고, 불일치를 분류·집계해 **현재 한계/문제 catalog와 개선 시드**를 만든다. 이 문서는 Claude(ultracode workflow)로
1회 수행한 분석을 Codex가 동일하게 재현하도록 단계·프롬프트·스키마·분류체계·집계규칙을 고정한다.

> 원칙(상위 계약 준수): head slice는 **모집단 오류율/품질 승인으로 환산 금지**. judge는 **진단·개선 시드용**.
> 라이브 재실행은 LLM 비결정성으로 게이트 효과를 격리 못 함 — judge는 "현재 출력의 정답성" 스냅샷이다.
> 과대단정 금지: 불확실하면 `uncertain`. 웹근거 없는 단정 금지.

> 2026-06-21 정정: completed779 이후의 "LLM judge" 기본값은 `agbrowse`나 API key가 아니라 **Codex 5.5 native web judge**다.
> Codex가 post 원문(title/body/comments/OCR)과 pipeline final만 읽고, 내장 web search/open으로 공식 작품 페이지·별칭·후보 URL을 직접 확인한다.
> 파이프라인 로그/history 기반 deterministic audit나 브라우저 ChatGPT 자동화는 이 요구를 충족한 것으로 보지 않는다.

---

## 1. 입력 (run 출력 파일)
대상: expert_main 산출 `out/expert_result_<runid>_checkpoint.jsonl` (진행 중 런) 또는 `..._completed_subset.json` /
최종 `....json`(완료 런, list 형태).

- **checkpoint.jsonl** 각 줄: `{global_idx, post_id, status, result}` — `status=="completed"`만 채택. 분석 본체는 `result`.
- **list json**(완료): 각 원소가 곧 `result` 형태.
- `result`(=post 레코드) 핵심 필드:
  - 원문: `title`, `content_blocks`[{type,text,url}], `comments`[str|{text}], `image_urls`, `image_count`
  - 파이프라인 판정: `result["analysis_result"]["identity"]` =
    `is_relevant, work_resolution, title_resolution_state, discussion_type, anchor_type, reason,`
    `image_evidence_catalog`[{explicit_work_title, explicit_author_name, ocr_text, visual_summary, evidence_type}],
    그리고 `primary_work`{official_title, source_tier, locked, confidence}.

## 2. 단계 (Codex 실행)

### 2-1. judge 입력 패킷 빌드 (결정적, 파이썬)
`result`에서 post별로 아래 압축 레코드를 추출해 **배치 파일(에이전트당 N=25건)**로 분할한다.
```python
# build_judge_batches.py  (Codex가 그대로 실행)
import json, os, sys
SRC = sys.argv[1]            # checkpoint.jsonl 또는 완료 list json
OUT = sys.argv[2]            # 배치 출력 디렉터리 (예: out/_judge/)
N   = int(sys.argv[3]) if len(sys.argv) > 3 else 25
os.makedirs(OUT, exist_ok=True)

def iter_results(path):
    if path.endswith(".jsonl"):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line: continue
            it = json.loads(line)
            if str(it.get("status")) != "completed": continue
            yield it.get("result") or {}
    else:
        for r in json.load(open(path, encoding="utf-8")):
            yield r

rows = []
for r in iter_results(SRC):
    idn = (r.get("analysis_result") or {}).get("identity") or {}
    pw = idn.get("primary_work") or {}
    body = " / ".join(str(b.get("text") or "").strip()
                      for b in (r.get("content_blocks") or [])
                      if isinstance(b, dict) and str(b.get("text") or "").strip())
    cmts = [(c if isinstance(c, str) else str((c or {}).get("text") or ""))
            for c in (r.get("comments") or [])]
    ocr = []
    for e in (idn.get("image_evidence_catalog") or [])[:2]:
        if isinstance(e, dict) and (e.get("explicit_work_title") or e.get("ocr_text")):
            ocr.append(f"표제={e.get('explicit_work_title')} 작가={e.get('explicit_author_name')} "
                       f"ocr={str(e.get('ocr_text') or '')[:140]}")
    rows.append({
        "post_id": r.get("post_id"),
        "title": str(r.get("title") or "")[:120],
        "body": body[:280],
        "comments": [c[:90] for c in cmts[:5]],
        "image_ocr": ocr,
        "img_count": r.get("image_count") or 0,
        "pipe": {k: (pw.get(k) if k in ("official_title","source_tier","locked","confidence") else idn.get(k))
                 for k in ("is_relevant","work_resolution","title_resolution_state","official_title",
                           "discussion_type","anchor_type","source_tier","locked","confidence")},
        "reason": str(idn.get("reason") or "")[:280],
    })
for i in range(0, len(rows), N):
    json.dump(rows[i:i+N], open(f"{OUT}/batch_{i//N:03d}.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"num_batches": (len(rows)+N-1)//N, "batch_size": N, "total": len(rows)},
          open(f"{OUT}/_meta.json", "w"))
print("batches:", (len(rows)+N-1)//N, "total:", len(rows))
```

### 2-2. judge 실행 (배치 = 1 LLM 호출/에이전트)
Codex는 배치 파일 1개를 1개의 judge LLM 호출(또는 sub-agent)에 넘긴다. **배치 내 25건을 한 번에 판정**해
호출 수를 (총건수/25)로 억제한다. Codex의 동시성/순차 정책에 맞춰 배치들을 순회(병렬 가능 시 병렬, 아니면 순차).
세션/요청 한도가 있으면 배치 단위로 체크포인트(완료 배치 verdicts를 파일로 저장)하고 중단 시 재개.

#### Legacy: Codex + agbrowse ChatGPT Pro 실행 보정 (2026-06-14)
`agbrowse web-ai`로 ChatGPT Pro를 브라우저 경유 호출할 때는 아래 보정을 적용한다. 초기 smoke에서
`--context-from-files`/`--file` 기반 전달과 Windows `agbrowse.cmd` wrapper 조합이 배치 JSON을 안정적으로
전달하지 못해 `{"batch":null,"verdicts":[]}` 같은 빈 껍데기 응답이 발생했다.

이 경로는 2026-06-21 completed779 외부 웹 judge의 기본 경로가 아니다. 해당 작업은 `agbrowse` 없이 Codex native web search로 수행한다.

- Windows에서는 `agbrowse.cmd`가 `%*`를 통해 긴 JSON 프롬프트를 넘기므로, 자동 runner는
  `node %APPDATA%\npm\node_modules\agbrowse\bin\agbrowse.mjs ...`를 직접 실행한다.
- batch 파일을 provider context/attachment로 맡기지 말고, 5건 이하 record를 `POSTS_JSON`으로 프롬프트 본문에 직접 inline한다.
- `agbrowse web-ai` 기본 instruction이 웹검색/citation을 유도할 수 있으므로, 자동 JSON 수집 단계에서는 웹검색·citation·Markdown link를 금지한다.
  웹근거가 필요한 건은 `note`에 `web_unverified`를 남기고 `uncertain` 또는 보수 severity로 둔다.
- 원래 spec의 25건 batch 단위 산출물은 유지한다. 단, runner 내부에서는 5건 이하 sub-call을 병합해
  `verdict_<i>.json` 1개를 원자 저장하고, `post_id` 집합 검증을 통과한 경우에만 완료로 본다.
- 장기 실행 기본 경로는 `agbrowse web-ai query` 단발 호출이 아니라 `send -> watch -> sessions show` 세션 경로다.
  `query`는 ChatGPT 답변이 보인 뒤 copy/완료 감지에서 멈출 수 있으므로, 완료 답변은 session store의 `answer`를 우선 읽는다.
- 각 5건 sub-call은 `chunk_<batch>_<chunk>.json` checkpoint로 먼저 저장한다. 5건 chunk 전송/검증이 실패하면
  같은 chunk를 1건 단위 subchunk로 자동 분해하고, 성공한 subchunk도 checkpoint로 남긴 뒤 원래 5건 chunk로 병합한다.
- ChatGPT provider tab이 누적되면 `provider.commit-not-verified`가 발생할 수 있으므로, runner는 chunk 호출 전후
  `tab-cleanup --provider chatgpt --keep-provider-tabs 1`로 provider overflow를 정리한다.
- `verdicts=[]`, `batch=null`, post_id 누락/중복, enum 이탈은 실패로 보고 저장하지 않는다.

**judge 시스템/유저 프롬프트 (배치당, 그대로 사용):**
> 너는 한국 웹소설 커뮤니티(dcinside) 글 작품매칭 파이프라인의 판정을 독립 재판정으로 검수하는 평가자다.
> 입력은 post 배열(각: post_id, title, body, comments, image_ocr[표제/작가/ocr], img_count, pipe[파이프라인 판정],
> reason[파이프라인 근거]). 각 post마다:
> 1) 본문+댓글+이미지 OCR을 정독해 **독립 판단**: (a) 소설 관련 글인가 (b) 식별 가능한 특정 웹소설이 있는가/무엇인가
>    (c) 글의 실제 의도/문맥(작품토론·추천요청·작가잡담·트로프일반론·밈·리뷰 등).
> 2) 파이프라인 `pipe`와 대조.
> 3) `disagreement_type`을 §3 분류표에서 선택.
> 4) `likely_correct`(pipeline/claude/both_unclear), `severity`(high=확정오류·과대확신/거짓음성 명백, med, low).
> 5) **웹검색은 resolved이거나 작품 식별이 모호/유명작 의심일 때만** 수행해 실제 작품(작가·플랫폼·줄거리·조회수)을 확인.
>    동명이인·유사제목·게임/애니/일본소설/고전/웹툰 오인을 경계. 명백한 noise/trope/잡담 일치 건은 웹검색 생략.
> 6) 배치 내 모든 post를 `verdicts` 배열에 담고, **최상위에 주어진 batch 인덱스를 함께 반환**(batch=<i>). 과대단정 말고 불확실하면 uncertain.

**verdict 스키마 (배치 응답, JSON) — 최상위 봉투 필수:**
```json
{ "batch": "<int, 프롬프트로 주어진 배치 인덱스를 그대로 반환>",
  "verdicts": [
    { "post_id": "int",
      "agree": "bool",
      "disagreement_type": "none|under_resolved_false_negative|wrong_work|garbage_title|over_resolved|wrong_relevance|wrong_discussion_type|cross_media_or_famous_mismatch|title_noisy_ocr|uncertain",
      "likely_correct": "pipeline|claude|both_unclear",
      "claude_take": "독립 판단 요약(관련성/작품/문맥) 한국어 1문장",
      "severity": "high|med|low",
      "note": "근거(웹검색 시 사실/URL 포함) 한국어 간결" }
  ]
}
```
- required(최상위) = `["batch","verdicts"]`. required(verdicts.items) = `["post_id","agree","disagreement_type","likely_correct","claude_take","severity","note"]`.
- `disagreement_type`은 위 10개 enum만. `agree=true` ⇔ `disagreement_type="none"`(상호 동치, 둘 다 강제).

**Codex 호출·구조화출력·검증 절차 (멱등):**
1. **호출**: 각 `batch_i.json`을 Codex가 직접 read해 내용을 §2-2 프롬프트에 인라인하고 judge LLM에 **배치당 1콜**. (서브에이전트 fan-out 가능 시 병렬, 아니면 순차. 동시성은 Codex 정책에 맞춤.)
2. **구조화 출력 강제**: OpenAI 경로면 `response_format={"type":"json_schema","strict":true}`에 위 스키마(enum 포함)를 넣는다. 단일 LLM이면 "코드펜스 금지·JSON 객체만 출력" 지시 후 `json.loads`.
3. **검증**: 파싱 후 (i) `verdicts`의 post_id 집합 == 입력 batch의 post_id 집합(완전성), (ii) 각 항목의 `disagreement_type`/`likely_correct`/`severity`가 enum에 속함, (iii) 7개 필수키 존재, (iv) `agree`와 `disagreement_type=="none"`이 동치인지. 하나라도 실패 시 **동일 배치 최대 3회 재호출**.
4. **폴백**: 3회 후에도 실패하면 누락/무효 post를 `disagreement_type="uncertain", severity="low", note="schema_fail"`로 채워 집계 붕괴를 막는다.
5. **저장**: 검증 통과한 배치 응답을 `out/_judge/verdict_<i:03d>.json`에 **원자적 저장**(temp 파일 write → `os.replace`). 세션/요청 한도로 중단돼도 완료 배치는 보존된다(재개는 §6).
6. **웹검색 도구**: Codex가 가진 web 도구(WebSearch/브라우즈)로 §4 규칙대로 검색. 웹검색 불가 환경이면 `note`에 `web_unverified` 기록하고 단정 회피(해당 건 `uncertain` 상향).

### 2-3. 집계 + 보고서
모든 `verdict_*.json`을 합산한다(Codex가 그대로 실행):
```python
# aggregate_verdicts.py  →  python aggregate_verdicts.py out/_judge/
import json, glob, sys
OUT = sys.argv[1]
meta = json.load(open(f"{OUT}/_meta.json"))
all_v, batches_ok = [], 0
for f in sorted(glob.glob(f"{OUT}/verdict_*.json")):
    v = json.load(open(f, encoding="utf-8"))
    if isinstance(v.get("verdicts"), list):
        batches_ok += 1; all_v += v["verdicts"]
c = lambda p: sum(1 for x in all_v if p(x))
byType = {}
for x in all_v: byType[x["disagreement_type"]] = byType.get(x["disagreement_type"], 0) + 1
res = {
  "total_judged": len(all_v), "batches_ok": batches_ok,
  "agree": c(lambda x: x["agree"]), "disagree": c(lambda x: not x["agree"]),
  "by_disagreement_type": byType,
  "by_severity": {s: c(lambda x, s=s: x["severity"] == s) for s in ("high", "med", "low")},
  "high_severity_issues": [
    {"post_id": x["post_id"], "type": x["disagreement_type"], "correct": x["likely_correct"],
     "claude": x["claude_take"], "note": x["note"]}
    for x in all_v if (not x["agree"]) and x["severity"] == "high"],
  # 유형별 post_id 전체(개선 타깃 시드)
  "post_ids_by_type": {t: [x["post_id"] for x in all_v if x["disagreement_type"] == t] for t in byType},
}
json.dump(res, open(f"{OUT}/_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
exp = batches_ok * meta["batch_size"]
if res["total_judged"] != exp:
    print(f"[부분배치 경고] judged={res['total_judged']} != batches_ok*N={exp} → 마지막/일부 배치 부분완료(§5-1 보고)")
print("판정", res["total_judged"], "/ 배치", batches_ok, "/", meta["num_batches"], "일치", res["agree"])
```
보고서는 §5 형식으로 작성하고, `post_ids_by_type`를 개선 타깃 시드 파일로 둔다.

---

## 3. 불일치 분류 taxonomy (enum + 정의 + 사례)
`agree=true` ⇔ `disagreement_type="none"`(동치). 불일치면 **단일** 라벨을 고른다. 복수 정의가 동시 성립하면
**아래 우선순위에서 가장 위에 먼저 매칭되는 1개만** 선택한다(라벨 중복 방지):

1. `garbage_title` — official_title **문자열 형식 자체**가 URL/도메인/'광고'/일반어 등 작품명이 아님(파이프라인이 resolved).
2. `cross_media_or_famous_mismatch` — 글 대상이 **비-웹소설**(게임/애니/일본소설/고전/웹툰)인데 웹소설로 확정(resolved).
3. `over_resolved` — 글이 **단일 작품 토론이 아닌데**(묘사어·현실잡담·모집공지·밈) 작품으로 확정(resolved). (단 비-웹소설 매체면 위 2번 우선.)
4. `wrong_work` — 글은 특정 웹소설 토론이 맞으나 **다른 웹소설로 오매칭**(resolved). (제목 문자열은 작품명 형식 — 형식 깨짐이면 1번.)
5. `title_noisy_ocr` — 파이프라인이 **올바른 작품을 resolved**했고 official_title도 그 작품을 가리키나, **제목 문자열에만** OCR 누출/오타/외국문자.
6. `under_resolved_false_negative` — **파이프라인이 미해소**(work_resolution=none/noise/trope)인데 식별 가능한 작품 단서(표준약칭·고유 캐릭터명·작가)가 있음.
7. `wrong_relevance` — 파이프라인이 **관련성 자체를 오판**(작품토론인데 is_relevant=false 등). 작품 식별까지 가능하면 6번 우선(=거짓음성).
8. `wrong_discussion_type` — 관련성·해소는 대체로 맞으나 **의도/문맥 라벨만** 틀림(추천요청↔작품토론↔트로프↔작가잡담↔밈).
9. `uncertain` — 본문+웹으로도 확정 불가.

경계 메모: (a) **resolved 계열**(1~5)과 **unresolved 계열**(6~7)을 파이프라인 `work_resolution`로 먼저 가른다.
(b) `title_noisy_ocr`(5)는 "작품은 맞음" 전제 — 작품 자체가 미해소면 6, 오작품이면 4. (c) `under_resolved`(6) vs
`wrong_relevance`(7): 식별 가능한 특정 작품이 있으면 항상 6(거짓음성), 작품 특정은 안 되지만 관련성만 틀렸으면 7.

| enum | 정의 | 실제 사례(3905 run) |

| enum | 정의 | 실제 사례(3905 run) |
|---|---|---|
| `none` | 파이프라인 = 독립판정 (본질적 일치) | — |
| `under_resolved_false_negative` | **식별 가능한 작품(표준약칭·고유 캐릭터명·작가)이 있는데 미해소**(none/noise/trope) | 망카데미→망할 놈의 아카데미, 악엔→악역의 엔딩은, 괴담텔 캐릭터 토론(알레프/한가인/위대한자)을 noise로 |
| `wrong_work` | **다른 작품 오매칭**(유사제목·환각제목·작가의 타작·비교인용작을 대상작으로) | '로판 속 금태양 남부제독…'을 '로판 속 금태양…'(별개작)으로; 환각 '조향사의 헌터상담기록' |
| `garbage_title` | official_title이 **URL/도메인/'광고'/일반어** 등 작품명 아님(OCR엔 정답 존재 가능) | 'novel.munpia.com', '광고' |
| `over_resolved` | **단일 작품 토론이 아닌데 작품 확정**(묘사어·현실잡담·모집공지·밈). ※비-웹소설 매체(게임/애니/고전)는 `cross_media_or_famous_mismatch`로 보냄 | 묘사어 '소시오패스', 모집공지 '밀리언 클래스', 운전면허 잡담 |
| `wrong_relevance` | 관련성 자체 오판(관련인데 비관련/그 반대) | 작품토론을 비관련 처리 |
| `wrong_discussion_type` | 의도/문맥 오분류(작품토론↔트로프↔추천요청↔작가잡담↔밈) | 추천요청을 작품토론으로 등 |
| `cross_media_or_famous_mismatch` | **게임/애니/일본소설/고전/웹툰 등 대중적 비-웹소설을 웹소설로 오인** | 림월드(게임), 드퀘4, 블아, 용의자 X의 헌신(일본소설), 괴테 파우스트, 탑툰 웹툰 |
| `title_noisy_ocr` | **올바른 작품을 resolved**(official_title이 그 작품)했으나 제목 문자열에만 **OCR 누출어/오타/외국문자** | '죽 검귀가 환생함'(누출 '죽 '), 'ชค악의 파트너'(태국문자), '총통…'( '각하' 누락) |
| `uncertain` | 본문+웹으로도 확정 불가 | — |

`severity` 기준(운영 가능하도록 구체화):
- **high**: ① resolved+locked(또는 confidence High)인데 **확정 오매칭/garbage/over_resolved/cross_media**(독자에게 틀린 작품을 자신 있게 제시), 또는 ② **명백한 거짓음성**(표준약칭 또는 작품 고유 캐릭터명 2개+로 단일작 특정 가능한데 미해소).
- **med**: 영향은 있으나 ① locked=false/confidence Medium 이하의 오매칭, ② 약칭 1개·모호 단서의 거짓음성, ③ 관련성/문맥 라벨만 틀림(작품 결론은 무해).
- **low**: 사소(문맥 라벨 미세차, 경계적 trope/adjacent 판정 등 다운스트림 영향 거의 없음).
- 분포 sanity: 정상 run이면 low가 다수, high는 소수다. high 비중이 비정상적으로 크면 severity 기준 오적용을 의심.

---

## 4. 웹검증 규칙 (precision의 핵심)
- 검색 대상: `pipe.official_title`과 `image_ocr` 표제를 각각 — (a) 실존하는 한국 웹소설인가, (b) 본문/댓글 내용과
  부합하는가, (c) 작가·플랫폼(노벨피아/문피아/카카오페이지/리디/조아라)·줄거리·조회수가 일치하는가.
- 경계: **동명이인·유사제목**(토큰 1개 차이로 별개작), **게임/애니/일본소설/고전/웹툰**(비-웹소설), **환각 제목**(어떤
  플랫폼에도 없음 → 검색 무결과면 확정 의심).
- 생략: 명백한 noise/일상잡담/트로프 일반론(작품 단서 없음)은 웹검색하지 말고 빠르게 판정(비용·시간 절약).

## 5. 보고서 형식 (산출물)
1. 커버리지(judged/total, 미판정분/중단사유, head slice 경고).
2. 일치율 + `disagreement_type`·`severity` 분포 표.
3. 한계 패턴(빈도·임팩트순) + 유형별 대표 post_id 사례 3~6개.
4. 개선 우선순위(임팩트 기준; recall 거짓음성 vs precision 오매칭 구분).
5. 유형별 post_id 전체 목록(개선 타깃 시드 파일).

## 6. Codex 실행 체크리스트 + 멱등 재개 루프
- [ ] `python build_judge_batches.py <run파일> out/_judge/ 25` → `batch_*.json` + `_meta.json`.
- [ ] 아래 멱등 루프로 배치 순회(중단/한도 발생 시 그대로 다시 실행하면 완료 배치는 skip):
```
NB = _meta.num_batches; N = _meta.batch_size; total = _meta.total
for i in range(NB):
    vp = f"{OUT}/verdict_{i:03d}.json"
    exp = min(N, total - i*N)                      # 마지막 배치는 잔여건수
    if exists(vp):
        v = try_load_json(vp)
        if v and v.get("batch")==i and isinstance(v.get("verdicts"),list) and len(v["verdicts"])==exp:
            continue                               # 존재 AND 완전 → skip
        # 존재하나 부분/무효 → 재처리(덮어씀)
    out = judge_llm(read(batch_i), prompt=§2-2, schema=BATCH_VERDICT)   # §2-2 검증·최대3회 재호출 포함
    if not valid(out, exp): continue               # 실패는 영속 안 함(다음 패스 재시도)
    atomic_write(vp, out)                          # temp write → os.replace(temp, vp)
```
  핵심: (a) skip은 '존재'가 아니라 '존재 AND 기대 verdict 수(exp) 일치'일 때만, (b) 부분/무효는 재호출, (c) 원자적 쓰기.
- [ ] ChatGPT web UI 전송 안정화:
  - provider prompt에는 `POSTS_JSON`을 inline으로 넣고, 원본 파일 upload/context package에 의존하지 않는다.
  - 성적/연령 민감 표현은 provider prompt에서만 bracket label로 치환한다. 원본 batch/checkpoint/verdict는 변경하지 않는다.
  - bracket label은 작품명으로 취급하지 말고, 작품 관련성/문맥 판단에 필요한 coarse signal로만 쓴다.
  - `provider.commit-not-verified`가 반복되면 stale `sent` session prune, provider tab cleanup, chunk/subchunk checkpoint 재시도를 먼저 수행한다.
  - long pass는 `--no-fallback --continue-on-fail`로 실행해 간헐 실패 batch를 건너뛰고, 다음 pass에서 aggregate의 missing batch를 checkpoint 기반으로 메운다.
  - 현재 장기 실행 기본값은 25건 단일 호출: `--records-per-call 25 --no-split-on-failure`. 특정 batch가 반복 실패하면 5건 chunk 모드로 fallback한다.
- [ ] `python aggregate_verdicts.py out/_judge/` → `_result.json`(+ 부분배치 경고) → §5 보고서 + `post_ids_by_type` 시드.
- [ ] §7 검산 기준값 대비 분포 sanity check(유사하면 정상).
- [ ] 과대주장 금지: 모집단 오류율 환산·semantic approval 금지. 불확실은 `uncertain`.

## 7. 참고 (Claude 1회 실행 결과 — 검산 기준값)
run `20260612_174715_296791`, judged 2564/3874(세션한도 중단), 일치율 87.4%. 불일치 분포:
under_resolved_false_negative 152 / wrong_discussion_type 87 / wrong_relevance 57 / uncertain 41 /
cross_media_or_famous_mismatch 33 / title_noisy_ocr 30 / wrong_work 19 / over_resolved 14 / garbage_title 6.
→ **최대 한계는 recall(거짓음성)**. Codex 재현 시 유사 분포가 나오면 정상.
