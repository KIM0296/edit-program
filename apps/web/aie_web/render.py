"""Stdlib HTML rendering (``html.escape`` + ``string.Template``). No template engine, no JS.

Every value that comes from user input (transcript text, file content, form
fields, diagnostics) goes through :func:`e` before it reaches the page.
"""

import html
from collections.abc import Sequence
from string import Template

from davinci_ai_editor.apply_cuts import SKIP_LABELS_KO, AppliedTimeline
from davinci_ai_editor.candidate_markers import CandidateDecision
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.roundtrip_verification import (
    KOREAN_LABELS,
    VerificationReport,
    VerificationStatus,
)

from .pipeline import (
    KIND_LABELS_KO,
    RATE_CHOICES,
    ApprovalView,
    ProjectBuild,
    seconds,
    timecode,
)


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


_LAYOUT = Template(
    """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title · AIE Free</title>
<style>
:root{--fg:#1d2330;--muted:#5b6475;--bg:#f6f7f9;--card:#fff;--line:#dfe3ea;--accent:#2457d6;
--ok:#1d7a46;--warn:#9a6200;--bad:#b3261e;--studio:#f1ecff;--studio-line:#cbb8ff}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif;
color:var(--fg);background:var(--bg);line-height:1.6}
header{background:var(--card);border-bottom:1px solid var(--line)}
header .in{max-width:1040px;margin:0 auto;padding:12px 16px;display:flex;flex-wrap:wrap;gap:16px;align-items:center}
header a.brand{font-weight:700;color:var(--fg);text-decoration:none}
nav a{margin-right:14px;color:var(--accent);text-decoration:none}
main{max-width:1040px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;margin:.4em 0}
h2{font-size:1.15rem;margin:1.4em 0 .5em}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.studio{background:var(--studio);border:1px solid var(--studio-line);border-radius:10px;padding:10px 14px;margin:12px 0}
.studio b{color:#4b2aa8}
.err{background:#fdecea;border:1px solid #f2b8b5;border-radius:10px;padding:12px 14px}
.muted{color:var(--muted)}
.tag{display:inline-block;padding:0 8px;border-radius:999px;font-size:.85em;border:1px solid var(--line)}
.s-MATCH,.ok{color:var(--ok);font-weight:700}
.s-MISMATCH,.bad{color:var(--bad);font-weight:700}
.s-UNVERIFIED,.warn{color:var(--warn);font-weight:700}
table{border-collapse:collapse;width:100%;font-size:.93rem}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.scroll{overflow-x:auto}
code,pre{font-family:ui-monospace,Consolas,monospace;font-size:.9em}
pre{white-space:pre-wrap;word-break:break-all;background:#f0f2f6;padding:10px;border-radius:8px}
label{display:block;font-weight:600;margin-top:10px}
input[type=text],input[type=number],select{width:100%;max-width:520px;padding:7px;border:1px solid var(--line);border-radius:6px;font:inherit}
.hint{font-size:.88em;color:var(--muted);margin:2px 0 0}
button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:9px 16px;font:inherit;cursor:pointer;margin-top:12px}
button.danger{background:var(--bad)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
ol li,ul li{margin:4px 0}
footer{max-width:1040px;margin:24px auto;padding:0 16px 24px;color:var(--muted);font-size:.85em}
</style>
</head>
<body>
<header><div class="in"><a class="brand" href="/">AIE Free · 웹 (로컬)</a>
<nav><a href="/">소개</a><a href="/new">새 프로젝트</a><a href="/limits">한계</a></nav></div></header>
<main>
$body
</main>
<footer>로컬 개발 서버(127.0.0.1) 전용 · 생성되는 파일은 모두 <b>Expected 산출물</b>이며 검증된 결과가 아닙니다 ·
Resolve로 가져오기는 사용자가 직접 합니다 · 렌더링은 하지 않습니다.</footer>
</body>
</html>
"""
)


def page(title: str, body: str) -> str:
    return _LAYOUT.substitute(title=e(title), body=body)


def studio(text: str) -> str:
    return f'<aside class="studio"><b>Studio에서는</b> {e(text)}</aside>'


def error_page(message: str, codes: Sequence[str] = (), back: str | None = None) -> str:
    items = "".join(f"<li><code>{e(c)}</code></li>" for c in codes)
    detail = f"<p class='muted'>진단 코드</p><ul>{items}</ul>" if items else ""
    link = f'<p><a href="{e(back)}">돌아가기</a></p>' if back else ""
    return page(
        "문제가 있습니다",
        f'<h1>문제가 있습니다</h1><div class="err"><p>{e(message)}</p>{detail}</div>{link}',
    )


# --------------------------------------------------------------------------- static pages


def landing() -> str:
    body = """
<h1>편집은 맡기되, 편집권은 넘기지 않는다</h1>
<p>AI가 <b>후보</b>를 찾고, 편집자가 DaVinci Resolve 안에서 <b>마커 이름</b>으로 고르고,
브라우저에서 <b>확인 버튼</b>을 눌러야만 컷이 적용된 새 타임라인 파일이 만들어집니다.
자동 적용은 없습니다.</p>
<div class="grid">
<div class="card"><h2>Free (이 웹)</h2>
<p class="muted">설득용: 핵심 결과를 모두 직접 확인합니다.</p>
<ul>
<li>전사 JSON + 미디어 정보 입력 → 후보를 Resolve 마커로</li>
<li>Resolve 안에서 마커 이름 변경으로 선택 (<code>AIE-0012 OK</code> / <code>AIE-0012 X</code>)</li>
<li>내보낸 XML 업로드 → 확인 요약(컷 수, 제거 초, 건너뛴 항목과 이유)</li>
<li>확인 버튼 → 비디오+오디오가 같은 프레임에서 잘린 새 타임라인(FCP7 XML)</li>
<li>사람이 고친 구간은 보호(HARD_LOCK)되어 건너뜀</li>
<li>다시 내보낸 XML로 검증 리포트(MATCH / MISMATCH / UNVERIFIED)</li>
</ul></div>
<div class="card"><h2>Studio (Resolve 안에서)</h2>
<p class="muted">실제 작업용: 같은 결과 + 더 깊이.</p>
<ul>
<li>현재 타임라인에 바로 적용 — 그레이드, 이펙트, 믹스 유지</li>
<li>파일 내보내기/가져오기 없이 타임라인을 실시간으로 읽음</li>
<li>Resolve 안 확인 대화상자, 네이티브 사후 검증</li>
<li>프레임 단위 정확한 클립 경계, 여러 타임라인, 트랙별 정책</li>
</ul></div>
</div>
<div class="card"><h2>흐름</h2>
<ol>
<li><a href="/new">새 프로젝트</a>: 전사 JSON(faster-whisper / whisperX)과 미디어 정보를 입력합니다.</li>
<li>다운로드: 후보 마커가 있는 FCP7 XML(기본), OTIO(선택), SRT 자막.</li>
<li>Resolve에서 가져오고 마커 이름을 바꿔 선택한 뒤, 타임라인을 FCP7 XML로 내보냅니다.</li>
<li>승인 업로드 → 확인 요약 → <b>확인</b> 버튼 → 적용된 새 타임라인 다운로드.</li>
<li>가져온 새 타임라인을 다시 내보내 검증 리포트를 받습니다.</li>
</ol>
<p><a href="/limits">정직한 한계 보기</a> — 특히 <b>가져오면 새 타임라인이 생기므로, 컷 승인은 색보정/이펙트 작업 전에</b> 하세요.</p>
</div>
<p class="muted">이 단계(Phase 1)는 로컬 개발 서버입니다: 미디어 업로드, 음성 인식(ASR), LLM 호출, 네트워크 호출이 없습니다.</p>
"""
    return page(
        "소개", body + studio("같은 후보와 같은 승인 규칙을 Resolve 안에서 파일 없이 바로 씁니다.")
    )


def limits() -> str:
    body = """
<h1>정직한 한계</h1>
<div class="card"><ul>
<li><b>가져오기는 새 타임라인을 만듭니다.</b> 이전 타임라인의 색보정, 이펙트, 타이틀, 속도 변경, 믹스는
새 타임라인(<code>… AIE v2</code>)으로 넘어가지 않습니다. <b>컷 승인을 마무리 작업(색보정·믹스·이펙트) 전에</b> 하세요.</li>
<li>후보는 제안일 뿐입니다. 필러/반복 후보는 <b>어휘 일치</b>이며 모호합니다(예: "이제"는 실제 의미일 수 있음).</li>
<li>전사 공백 후보는 단어 타이밍 사이의 빈 구간입니다. <b>소리를 분석한 무음이 아닙니다.</b>
Whisper 계열 타이밍은 서버 시계 기준이라 최소 1프레임 오차를 가정합니다.</li>
<li>컷은 모든 비디오/오디오 트랙에서 같은 프레임을 제거합니다(음악·B롤 포함). 트랙 선택 컷은 없습니다.</li>
<li>마커는 <code>Video 1</code>의 클립 위에만 놓입니다. FCP7 XML은 마커 색을 담지 못하므로 <b>이름만</b> 신호입니다.</li>
<li>사람이 수정한 구간(트림, 이동, 추가한 마커 등)은 보호되어 그 안의 후보는 건너뜁니다(HUMAN_EDIT_LOCKED).
리플 트림 뒤쪽 클립 전체가 보호될 수 있습니다(보수적).</li>
<li>판단할 수 없는 것(UNKNOWN)은 절대 성공으로 표시하지 않습니다.</li>
<li>Resolve의 FCP7 XML 내보내기 세부(소스 in/out 기준, <code>&lt;link&gt;</code> 처리, SRT 기준 시각)는 아직
실제 Resolve에서 확인되지 않았습니다(UNVERIFIED).</li>
<li>한 번의 왕복에 타임라인 하나, 미디어 파일 하나만 다룹니다. 렌더링은 하지 않습니다(최종 렌더는 Resolve Deliver).</li>
<li>로컬 개발 서버입니다: 인증·데이터베이스 없음, 프로젝트는 임시 폴더에 저장되고 일정 시간 뒤 자동 삭제됩니다.</li>
</ul></div>
"""
    return page(
        "한계",
        body
        + studio(
            "현재 타임라인에 바로 적용되어 그레이드·이펙트·믹스가 유지되고, 사후 검증도 네이티브로 읽습니다."
        ),
    )


def new_project(
    error: str = "", codes: Sequence[str] = (), values: dict[str, str] | None = None
) -> str:
    v = values or {}

    def val(name: str, default: str = "") -> str:
        return e(v.get(name, default))

    def selected(name: str, option: str, default: str) -> str:
        return " selected" if v.get(name, default) == option else ""

    rate_options = "".join(
        f'<option value="{e(key)}"{selected("rate", key, "24000/1001")}>{e(label)}</option>'
        for key, label in RATE_CHOICES
    )
    err = ""
    if error:
        items = "".join(f"<li><code>{e(c)}</code></li>" for c in codes)
        err = f'<div class="err"><p>{e(error)}</p>{"<ul>" + items + "</ul>" if items else ""}</div>'
    body = f"""
<h1>새 프로젝트</h1>
{err}
<form class="card" method="post" action="/projects" enctype="multipart/form-data">
<h2>1. 전사 JSON</h2>
<label for="transcript">전사 파일 (faster-whisper 또는 whisperX 결과 JSON, 최대 5 MB)</label>
<input id="transcript" type="file" name="transcript" accept=".json,application/json">
<label for="tool">ASR 도구</label>
<select id="tool" name="tool">
<option value="faster-whisper"{selected("tool", "faster-whisper", "faster-whisper")}>faster-whisper (단어 타임스탬프)</option>
<option value="whisperx"{selected("tool", "whisperx", "faster-whisper")}>whisperX (정렬된 단어)</option>
</select>
<label for="tool_version">도구 버전 (선택)</label><input id="tool_version" type="text" name="tool_version" value="{val("tool_version")}">
<label for="model_id">모델 (선택, 예: large-v3)</label><input id="model_id" type="text" name="model_id" value="{val("model_id")}">
<label for="offset_ms">전사 시작 오프셋(ms)</label>
<input id="offset_ms" type="number" min="0" name="offset_ms" value="{val("offset_ms", "0")}">
<p class="hint">전사가 미디어 처음부터 시작했다면 0.</p>
<h2>2. 미디어 정보 (Resolve에서 보이는 그대로)</h2>
<label for="media_path">미디어 파일 경로</label>
<input id="media_path" type="text" name="media_path" value="{val("media_path")}" placeholder="D:\\Footage\\interview.mov">
<p class="hint">Resolve가 이 파일을 찾을 수 있는 경로. 미디어는 업로드하지 않습니다.</p>
<label for="rate">프레임레이트</label><select id="rate" name="rate">{rate_options}</select>
<label for="duration_frames">미디어 길이(프레임)</label>
<input id="duration_frames" type="number" min="1" name="duration_frames" value="{val("duration_frames")}">
<label for="media_start">미디어 시작 타임코드 또는 프레임</label>
<input id="media_start" type="text" name="media_start" value="{val("media_start")}" placeholder="00:00:00:00">
<p class="hint">Resolve 클립 속성의 Start TC. Resolve 프로필에서는 필수이며 0으로 가정하지 않습니다.</p>
<label for="profile">프로필</label>
<select id="profile" name="profile">
<option value="RESOLVE"{selected("profile", "RESOLVE", "RESOLVE")}>DaVinci Resolve (권장)</option>
<option value="GENERIC"{selected("profile", "GENERIC", "RESOLVE")}>일반 (시작 타임코드 모름)</option>
</select>
<h2>3. 새 타임라인</h2>
<label for="timeline_name">타임라인 이름</label>
<input id="timeline_name" type="text" name="timeline_name" value="{val("timeline_name", "AIE 후보")}">
<label for="timeline_start">타임라인 시작 타임코드</label>
<input id="timeline_start" type="text" name="timeline_start" value="{val("timeline_start", "01:00:00:00")}">
<label for="gap_seconds">전사 공백 기준(초)</label>
<input id="gap_seconds" type="text" name="gap_seconds" value="{val("gap_seconds", "1.0")}">
<p class="hint">단어 사이 빈 구간이 이 값 이상이면 후보로 표시합니다(음향 무음 분석 아님).</p>
<button type="submit">후보 만들기</button>
</form>
"""
    return page(
        "새 프로젝트",
        body
        + studio(
            "Resolve 내장 전사(사용 가능할 때) 또는 서버 ASR을 쓰고, 미디어 정보는 타임라인에서 직접 읽습니다."
        ),
    )


# --------------------------------------------------------------------------- project pages


def _range_cell(build: ProjectBuild, frame_range: FrameRange | None) -> str:
    if frame_range is None:
        return "<span class='muted'>타이밍 없음</span>"
    facts = build.facts
    return (
        f"{e(timecode(facts, frame_range.start))} – {e(timecode(facts, frame_range.end))}"
        f"<br><span class='muted'>[{frame_range.start},{frame_range.end}) "
        f"{e(seconds(frame_range.duration, facts.rate))}초</span>"
    )


def _rows(build: ProjectBuild, marked: bool) -> str:
    out = []
    for row in build.rows:
        if (row.candidate_id is not None) != marked:
            continue
        ident = e(row.candidate_id) if row.candidate_id else "—"
        extra = f"<br><span class='warn'>{e(row.not_marked)}</span>" if row.not_marked else ""
        out.append(
            f"<tr><td><code>{ident}</code></td><td>{e(KIND_LABELS_KO[row.kind])}</td>"
            f"<td>{_range_cell(build, row.frame_range)}</td><td>{e(row.words.strip())}</td>"
            f"<td>{e(row.reason)}<br><span class='muted'>{e(row.detail)}</span>{extra}</td></tr>"
        )
    return "".join(out)


_TABLE_HEAD = "<tr><th>ID</th><th>종류</th><th>구간</th><th>전사</th><th>이유</th></tr>"


def import_steps() -> str:
    return """
<ol>
<li>Resolve(무료 버전)에서 <b>File &gt; Import &gt; Timeline…</b> 을 열고 받은 <code>.xml</code>을 선택합니다.</li>
<li>미디어가 오프라인이면 <b>Relink</b>(미디어 풀에서 클립 우클릭 &gt; Relink Selected Clips…)로 원본 파일을 연결합니다.</li>
<li>자막이 필요하면 <code>.srt</code>를 미디어 풀로 가져온 뒤(File &gt; Import &gt; Subtitle…) 타임라인으로 끌어다 놓습니다.</li>
<li>이 단계의 가져오기는 사용자가 직접 합니다. 이 웹은 Resolve를 조작하지 않습니다.</li>
</ol>"""


def rename_rules() -> str:
    return """
<ul>
<li>후보 마커 이름: <code>AIE-0012 ?</code> (미결정). 메모: <code>candidate=AIE-0012; reason=…</code></li>
<li><b>적용하려면</b> 이름을 <code>AIE-0012 OK</code> 또는 <code>AIE-0012 승인</code> 으로 바꿉니다.</li>
<li><b>제외하려면</b> <code>AIE-0012 X</code> 또는 <code>AIE-0012 제외</code> 로 바꿉니다.</li>
<li>나중에 정하려면 그대로 둡니다. 대소문자는 구분하지 않습니다.</li>
<li>마커를 옮기거나 복사·삭제하지 마세요. 옮긴 마커, 중복, 이상한 이름은 <b>판단 불가(UNKNOWN)</b>로 적용되지 않습니다.</li>
<li>마커 이름 변경은 <b>선택</b>일 뿐입니다. 실제 <b>승인</b>은 다음 단계의 확인 버튼입니다.</li>
</ul>"""


def project_page(
    project_id: str, build: ProjectBuild, has_approval: bool, has_applied: bool
) -> str:
    pid = e(project_id)
    facts = build.facts
    marked_count = sum(1 for r in build.rows if r.candidate_id is not None)
    unmarked = _rows(build, marked=False)
    srt_note = ""
    if build.srt_diagnostics:
        srt_note = (
            f"<p class='warn'>자막 {len(build.srt_diagnostics)}개 구간은 쓸 수 없어 빠졌습니다 "
            "(빈 텍스트 또는 '--&gt;' 포함).</p>"
        )
    progress = ""
    if has_approval:
        progress += f'<p><a href="/p/{pid}/confirm">→ 확인 요약 보기</a></p>'
    if has_applied:
        progress += f'<p><a href="/p/{pid}/applied">→ 적용된 타임라인 / 검증</a></p>'
    start_text = (
        "모름(UNKNOWN)"
        if facts.media_start_frame is None
        else str(facts.media_start_frame) + "프레임"
    )
    body = f"""
<h1>후보 목록</h1>
<p class="muted">타임라인 <b>{e(facts.timeline_name)}</b> · 미디어 <code>{e(facts.media_path)}</code> ·
{e(facts.rate.numerator)}/{e(facts.rate.denominator)} fps · 길이 {facts.duration_frames}프레임 ·
미디어 시작 {e(start_text)} · 프로필 {e(facts.profile.value)}</p>
{progress}
<div class="card">
<p>마커 후보 <b>{marked_count}개</b> (모두 <b>제안</b>이며 자동 적용되지 않습니다) ·
전사 단어 {len(build.snapshot.words)}개 · 타이밍 문제 {build.projection_issue_count}개 ·
단어 타이밍 없는 전사 구간 {build.unavailable_segment_count}개</p>
<p class="muted">정책 {e(build.policy.version)}: 전사 공백 기준 {build.policy.gap_threshold_frames}프레임,
여유 {build.policy.gap_padding_frames}프레임, 반복 간격 ≤ {build.policy.max_repetition_gap_frames}프레임,
타이밍 허용 오차 {build.policy.tolerance_frames}프레임. 필러/반복은 KOR-001 어휘 규칙(모호), 전사 공백은 음향 무음이 아닙니다.</p>
<div class="scroll"><table>{_TABLE_HEAD}{_rows(build, marked=True) or "<tr><td colspan=5>마커 후보가 없습니다.</td></tr>"}</table></div>
</div>
{"<h2>마커로 만들지 않은 후보</h2><div class='card scroll'><table>" + _TABLE_HEAD + unmarked + "</table></div>" if unmarked else ""}
{studio("후보가 현재 타임라인에 바로 마커로 표시되고, 사람이 고친 구간을 매번 실시간으로 읽어 제외합니다.")}

<h2>2. 다운로드</h2>
<div class="card">
<ul>
<li><a href="/p/{pid}/download/candidates.xml">후보 마커 타임라인 — FCP7 XML (기본)</a></li>
<li><a href="/p/{pid}/download/candidates.otio">같은 타임라인 — OTIO (선택)</a></li>
<li><a href="/p/{pid}/download/transcript.srt">자막 — SRT</a></li>
</ul>
{srt_note}
<h3>Resolve Free에서 가져오기</h3>{import_steps()}
<h3>마커 이름으로 선택하기</h3>{rename_rules()}
<p>선택을 마치면 타임라인을 선택하고 <b>File &gt; Export &gt; Timeline…</b> 에서 <b>FCP 7 XML (.xml)</b> 로 내보냅니다.</p>
</div>
{studio("파일을 주고받지 않습니다. 타임라인에 바로 마커가 생기고, Resolve 안에서 확인 대화상자로 승인합니다.")}

<h2>3. 승인 업로드</h2>
<form class="card" method="post" action="/p/{pid}/approval" enctype="multipart/form-data">
<label for="approval">Resolve에서 내보낸 FCP7 XML (최대 8 MB)</label>
<input id="approval" type="file" name="export" accept=".xml,text/xml,application/xml">
<button type="submit">업로드하고 확인 요약 보기</button>
<p class="hint">업로드는 선택을 읽을 뿐 아무것도 적용하지 않습니다.</p>
</form>

<form method="post" action="/p/{pid}/delete">
<button class="danger" type="submit">이 프로젝트 삭제</button>
<p class="hint">작업 폴더와 업로드한 파일이 즉시 삭제됩니다. 오래된 프로젝트는 자동으로 삭제됩니다.</p>
</form>
"""
    return page("후보 목록", body)


def confirm_page(project_id: str, build: ProjectBuild, view: ApprovalView) -> str:
    pid = e(project_id)
    c = view.confirmation
    rate = c.actual.rate
    decisions = {
        CandidateDecision.APPROVED: "승인",
        CandidateDecision.REJECTED: "제외",
        CandidateDecision.PENDING: "미결정",
        CandidateDecision.UNKNOWN: "판단 불가",
    }
    sel_rows = "".join(
        f"<tr><td><code>{e(s.candidate_id)}</code></td><td>{e(s.marker_name or '—')}</td>"
        f"<td>{e(decisions[s.decision])} <span class='muted'>{e(s.decision.value)}</span></td>"
        f"<td>{e('' if s.issue.value == 'NONE' else s.issue.value)}</td></tr>"
        for s in view.selection.selections
    )
    cut_rows = "".join(
        f"<tr><td><code>{e(cut.candidate_id)}</code></td>"
        f"<td>[{cut.timeline_range.start},{cut.timeline_range.end})</td>"
        f"<td>{cut.timeline_range.duration}프레임 ({e(seconds(cut.timeline_range.duration, rate))}초)</td>"
        f"<td>{e(cut.reason)}</td></tr>"
        for cut in c.approved_cuts
    )
    skip_rows = "".join(
        f"<tr><td><code>{e(s.candidate_id)}</code></td><td><code>{e(s.reason.value)}</code></td>"
        f"<td>{e(SKIP_LABELS_KO[s.reason])}</td><td>{e(s.detail)}</td></tr>"
        for s in c.skipped
    )
    shifted_rows = "".join(
        f"<li><code>{e(s.lock.track_id)}</code> [{s.lock.frame_range.start},{s.lock.frame_range.end}) "
        f"{s.delta_frames:+d}프레임 이동 (내용은 편집하지 않음)</li>"
        for s in c.shifted_locks
    )
    warnings = []
    if view.diff.status.value == "UNKNOWN":
        reasons = ", ".join(r.value for r in view.diff.reasons)
        warnings.append(
            f"왕복 비교 전체가 판단 불가(UNKNOWN)입니다 ({e(reasons)}). 모든 컷이 보호되어 적용되지 않습니다."
        )
    if view.unknown_region_count:
        warnings.append(
            f"지원하지 않는 요소(트랜지션, 속도 변경 등) {view.unknown_region_count}곳은 판단 불가 구간으로 보호됩니다."
        )
    if view.selection.unexpected_tokens:
        warnings.append(
            "우리가 만들지 않은 토큰은 무시합니다: "
            + e(", ".join(view.selection.unexpected_tokens))
        )
    warn_html = "".join(f"<p class='warn'>{w}</p>" for w in warnings)
    if c.approved_cuts:
        action = f"""
<form class="card" method="post" action="/p/{pid}/confirm">
<input type="hidden" name="digest" value="{e(c.confirmation_digest)}">
<p>위 내용대로 <b>{len(c.approved_cuts)}개 컷</b>, 총 <b>{e(seconds(c.removed_frames, rate))}초</b>를
비디오와 오디오 모든 트랙에서 같은 프레임으로 잘라 <b>새 타임라인 파일</b>을 만듭니다.</p>
<p class="muted">확인 코드 <code>{e(c.confirmation_digest[:16])}…</code> — 이 버튼이 승인입니다. 내용이 바뀌면 코드도 바뀌어 거부됩니다.</p>
<button type="submit">확인 — 승인한 컷 적용</button>
</form>"""
    else:
        action = "<div class='card'><p><b>적용할 승인 컷이 없습니다.</b> Resolve에서 마커 이름을 바꾼 뒤 다시 내보내 업로드하세요.</p></div>"
    body = f"""
<h1>확인 요약</h1>
<p class="muted">마커 이름 변경은 <b>선택</b>이었습니다. 아래를 확인하고 버튼을 눌러야 <b>승인</b>되며, 그 전에는 아무것도 적용되지 않습니다.</p>
{warn_html}
<div class="card">
<p><span class="ok">승인된 컷 {len(c.approved_cuts)}개</span> · 제거 {c.removed_frames}프레임
({e(seconds(c.removed_frames, rate))}초) · 건너뜀 {len(c.skipped)}개</p>
<div class="scroll"><table><tr><th>ID</th><th>구간(현재 타임라인 프레임)</th><th>길이</th><th>이유</th></tr>
{cut_rows or "<tr><td colspan=4>없음</td></tr>"}</table></div>
</div>
<h2>건너뛴 항목과 이유</h2>
<div class="card scroll"><table><tr><th>ID</th><th>코드</th><th>뜻</th><th>세부</th></tr>
{skip_rows or "<tr><td colspan=4>없음</td></tr>"}</table>
<p class="hint">HUMAN_EDIT_LOCKED = 사람이 고친 구간(보호), MARKER_CONFLICT = 다른 마커와 겹침, UNKNOWN = 판단 불가(적용 안 함).</p></div>
{"<h2>보호 구간 이동</h2><div class='card'><p>아래 보호 구간은 편집하지 않지만 앞쪽 컷 때문에 왼쪽으로 이동합니다.</p><ul>" + shifted_rows + "</ul></div>" if shifted_rows else ""}
{action}
<h2>읽은 마커</h2>
<div class="card scroll"><table><tr><th>ID</th><th>마커 이름</th><th>선택</th><th>문제</th></tr>{sel_rows}</table></div>
<details class="card"><summary>확인 요약 원문 (결정적 텍스트)</summary><pre>{e(c.summary)}</pre></details>
{studio("같은 요약을 Resolve 안의 확인 대화상자로 보고, 승인하면 현재 타임라인에 그대로 적용됩니다.")}
<p><a href="/p/{pid}">← 후보 목록</a></p>
"""
    return page("확인 요약", body)


def applied_page(project_id: str, applied: AppliedTimeline) -> str:
    pid = e(project_id)
    rate = applied.timeline.rate
    removed = sum(c.timeline_range.duration for c in applied.applied_cuts)
    remaining = ", ".join(applied.remaining_candidate_ids) or "없음"
    body = f"""
<h1>적용된 새 타임라인</h1>
<div class="card">
<p>새 타임라인 <b>{e(applied.timeline.name)}</b> · 적용 컷 {len(applied.applied_cuts)}개 ·
제거 {removed}프레임 ({e(seconds(removed, rate))}초) · 비디오+오디오 같은 프레임, 리플, A/V 링크</p>
<p class="warn">이 파일은 <b>검증되지 않은 Expected 산출물</b>입니다(verified = False). 아래 검증 단계를 거치세요.</p>
<p><a href="/p/{pid}/download/applied.xml">적용된 타임라인 — FCP7 XML 다운로드</a></p>
<p class="muted">남은 후보 마커: {e(remaining)}</p>
<h3>가져오기</h3>{import_steps()}
<p><b>주의:</b> 새 타임라인으로 가져와지므로 이전 타임라인의 색보정·이펙트·믹스는 넘어오지 않습니다.</p>
</div>
{studio("새 파일 없이 현재 타임라인에 바로 적용되어 색보정·이펙트·믹스·빈 구성이 그대로 유지됩니다.")}
<h2>4. 검증</h2>
<form class="card" method="post" action="/p/{pid}/verify" enctype="multipart/form-data">
<p>가져온 새 타임라인을 Resolve에서 다시 <b>FCP 7 XML</b>로 내보내 올리면, 의도한 컷 목록과 비교합니다.</p>
<label for="reexport">다시 내보낸 FCP7 XML</label>
<input id="reexport" type="file" name="export" accept=".xml,text/xml,application/xml">
<label for="provenance">이 파일은…</label>
<select id="provenance" name="provenance">
<option value="IMMEDIATE_REEXPORT">가져온 직후 아무것도 고치지 않고 내보냈습니다 (사용자 선언)</option>
<option value="AFTER_HUMAN_EDIT">가져온 뒤 직접 수정했습니다</option>
</select>
<p class="hint">수정했다면 차이를 사람 수정인지 전달 손실인지 구분할 근거가 없어 판단 불가(UNKNOWN)로 남습니다.</p>
<button type="submit">검증 리포트 보기</button>
</form>
<p><a href="/p/{pid}">← 후보 목록</a> · <a href="/p/{pid}/confirm">확인 요약</a></p>
"""
    return page("적용 결과", body)


def report_page(project_id: str, report: VerificationReport) -> str:
    pid = e(project_id)
    status = report.status
    label = KOREAN_LABELS.get(status.value, status.value)
    headline = {
        VerificationStatus.MATCH: "의도한 컷 목록과 다시 내보낸 타임라인이 일치합니다.",
        VerificationStatus.MISMATCH: "의도와 다른 항목이 있습니다. 아래 항목별 코드를 확인하세요.",
        VerificationStatus.UNVERIFIED: "판단할 수 없는 항목이 있어 검증되지 않았습니다. 성공으로 보지 마세요.",
    }[status]

    def css(code: str) -> str:
        if code in ("MATCH", "HUMAN_CHANGED"):
            return "MATCH"
        return "UNVERIFIED" if code == "UNKNOWN" else "MISMATCH"

    def span(frame_range: FrameRange | None) -> str:
        return "-" if frame_range is None else f"[{frame_range.start},{frame_range.end})"

    rows = "".join(
        f"<tr><td><code>{e(i.item_id)}</code></td><td>{e(i.track.label)}</td>"
        f"<td><span class='s-{css(i.status.value)}'>{e(i.status.value)}</span> "
        f"<span class='muted'>{e(KOREAN_LABELS.get(i.status.value, ''))}</span></td>"
        f"<td>{e(span(i.expected_range))} → {e(', '.join(span(r) for r in i.actual_ranges) or '-')}</td>"
        f"<td>{e(i.attribution.value)} / {e(i.basis.value)}</td><td>{e(i.identity.value)}</td>"
        f"<td>{e(i.detail)}</td></tr>"
        for i in report.items
    )
    reasons = ", ".join(report.reasons)
    body = f"""
<h1>검증 리포트</h1>
<div class="card">
<p>결과: <span class="s-{e(status.value)}">{e(status.value)} ({e(label)})</span></p>
<p>{e(headline)}</p>
<p class="muted">증거 등급 {e(report.evidence_class)} — 파일 왕복 증거이며 네이티브(실시간) 검증이 아닙니다.
출처 선언: {e(report.provenance.value)} · 사람 수정 {report.human_changed_count}개</p>
{f"<p class='warn'>사유: {e(reasons)}</p>" if reasons else ""}
</div>
<div class="card scroll"><table><tr><th>항목</th><th>트랙</th><th>상태</th><th>기대 → 실제(프레임)</th><th>원인/근거</th><th>식별</th><th>세부</th></tr>{rows}</table></div>
{studio("편집 직후 Resolve 타임라인을 직접 다시 읽어 Expected와 Actual을 비교합니다(파일 왕복 없이).")}
<p><a href="/p/{pid}/applied">← 적용 결과</a> · <a href="/p/{pid}">후보 목록</a></p>
"""
    return page("검증 리포트", body)


def deleted_page() -> str:
    return page(
        "삭제됨", "<h1>프로젝트를 삭제했습니다</h1><p><a href='/new'>새 프로젝트 만들기</a></p>"
    )
