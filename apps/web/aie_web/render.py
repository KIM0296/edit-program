"""Stdlib HTML rendering (``html.escape`` + ``string.Template``). No template engine, no JS.

Every value that comes from user input (transcript text, file content, form
fields, diagnostics) goes through :func:`e` before it reaches the page.
"""

import html
import time
from collections.abc import Callable, Sequence
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
    POLICY_LABELS_KO,
    RATE_CHOICES,
    ApprovalView,
    ProjectBuild,
    effect_label,
    issue_label,
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
$head
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
<nav><a href="/">소개</a><a href="/new">새 프로젝트</a><a href="/guide">Resolve 안내</a><a href="/limits">한계</a><a href="/studio">Studio</a></nav></div></header>
<main>
$body
</main>
<footer>체험(데모) 서버 · 생성되는 파일은 모두 <b>Expected 산출물</b>이며 검증된 결과가 아닙니다 ·
Resolve로 가져오기는 사용자가 직접 합니다 · 렌더링은 하지 않습니다.</footer>
</body>
</html>
"""
)


def page(title: str, body: str, head: str = "") -> str:
    return _LAYOUT.substitute(title=e(title), body=body, head=head)


def studio(text: str) -> str:
    return (
        f'<aside class="studio"><b>Studio에서는</b> {e(text)} '
        '<a href="/studio">Studio 자세히 →</a></aside>'
    )


def csrf_field(token: str) -> str:
    return f'<input type="hidden" name="csrf_token" value="{e(token)}">'


def when(timestamp: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))


def retention_notice(hours: float, expires_at: float | None = None, trial: bool = False) -> str:
    """What is stored and when it is deleted (Korean, shown on every upload page)."""
    if trial:
        rule = (
            f"체험 코드가 처음 사용된 때부터 {hours:g}시간 뒤 코드가 만료되면, 그 코드로 만든 "
            "모든 프로젝트(영상·전사·결과 파일)가 자동으로 삭제됩니다."
        )
    else:
        rule = f"프로젝트를 만든 뒤 {hours:g}시간이 지나면 자동으로 삭제됩니다."
    due = f" 삭제 예정: <b>{e(when(expires_at))}</b> (서버 시각)." if expires_at else ""
    return (
        '<div class="card notice"><b>저장과 삭제 안내</b><p>이 서버에 저장되는 것: 올린 영상/오디오 파일, '
        "그 파일의 전사 결과(JSON), Resolve에서 내보내 올린 XML, 확인 코드. 영상은 전사와 후보 "
        f"생성에만 쓰이며 다른 곳으로 보내지 않습니다(음성 인식도 이 서버 안에서 실행). {e(rule)}"
        f"{due} 프로젝트 페이지의 <b>이 프로젝트 삭제</b> 버튼으로 언제든 즉시 지울 수 있습니다.</p></div>"
    )


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
<div class="card"><h2>Free 체험 (이 웹)</h2>
<p class="muted">흐름이 끝까지 실제로 동작하는 것을 직접 확인하는 체험판입니다.</p>
<ul>
<li>짧은 영상 업로드 → 이 서버에서 음성 인식(전사) → 후보를 Resolve 마커로</li>
<li>Resolve 안에서 마커 이름 변경으로 선택 (<code>AIE-0012 OK</code> / <code>AIE-0012 X</code>)</li>
<li>내보낸 XML 업로드 → 확인 요약(컷 수, 제거 초, 건너뛴 항목과 이유)</li>
<li>확인 버튼 → 트랙별로 편집된 새 타임라인(FCP7 XML): 대사와 연결된 A/V는 같은 프레임에서 자르고,
음악·B-roll·자막 트랙은 자르지 않고 당김(트랙은 병합하지 않음)</li>
<li>사람이 고친 구간은 보호(HARD_LOCK)되어 건너뜀</li>
<li>다시 내보낸 XML로 검증 리포트(MATCH / MISMATCH / UNVERIFIED)</li>
</ul></div>
<div class="card"><h2>Studio (Resolve 안에서, 개발 중)</h2>
<p class="muted">실제 작업용 제품입니다. 같은 후보·같은 승인 규칙에 더해:</p>
<ul>
<li>파일 주고받기 없이 Resolve 안에서: <b>색보정 전</b>에는 확인 한 번으로 컷을 적용합니다(새 버전 타임라인, 원본은 백업 — tier 1)</li>
<li><b>색보정 후</b>의 그레이드 이전은 검증 중입니다 — Resolve가 지원하는 범위에서, 네이티브 검증을 통과한 뒤에만 약속합니다</li>
<li>사람이 고친 구간을 매번 타임라인에서 직접 읽어 보호</li>
<li>Resolve 안 확인 대화상자, 네이티브 사후 검증</li>
</ul>
<p><a href="/studio">Free와 Studio 비교 · 현재 상태 →</a></p></div>
</div>
<div class="card"><h2>흐름</h2>
<ol>
<li><a href="/new">새 프로젝트</a>: 짧은 영상(CFR)을 올립니다. 이 서버에서 faster-whisper로 전사합니다.</li>
<li>다운로드: 후보 마커가 있는 FCP7 XML(기본), OTIO(선택), SRT 자막.</li>
<li>Resolve에서 가져오고 마커 이름을 바꿔 선택한 뒤, 타임라인을 FCP7 XML로 내보냅니다.</li>
<li>승인 업로드 → 확인 요약 → <b>확인</b> 버튼 → 적용된 새 타임라인 다운로드.</li>
<li>가져온 새 타임라인을 다시 내보내 검증 리포트를 받습니다.</li>
</ol>
<p><a href="/guide">Resolve 무료 버전 따라하기 안내</a> · <a href="/limits">정직한 한계 보기</a> —
특히 <b>가져오면 새 타임라인이 생기므로, 컷 승인은 색보정/이펙트 작업 전에</b> 하세요.</p>
</div>
<p class="muted">음성 인식(faster-whisper)은 이 서버 안에서 실행됩니다. LLM 호출과 외부 네트워크 호출은 없습니다.</p>
"""
    return page(
        "소개",
        body
        + studio(
            "같은 후보와 같은 승인 규칙을 Resolve 안에서 파일 없이 씁니다. "
            "네이티브 검증 전이며, 색보정 전에는 확인 한 번으로 컷을 적용합니다."
        ),
    )


def consent_page(
    csrf: str, hours: float, max_projects: int, max_minutes: int, error: str = ""
) -> str:
    err = f'<div class="err"><p>{e(error)}</p></div>' if error else ""
    body = f"""
<h1>AIE Free 체험</h1>
<p>초대 코드로 짧은 영상을 올려, AI 후보 → Resolve 안 선택 → 확인 → 적용된 타임라인 → 검증까지
흐름이 실제로 동작하는 것을 확인하는 <b>체험판</b>입니다. 실제 제품은 Resolve Studio 안에서 동작할
예정입니다(<a href="/studio">비교 보기</a>).</p>
{err}
<form class="card" method="post" action="/trial/start">
{csrf_field(csrf)}
<h2>동의 안내</h2>
<p><b>업로드한 영상은 전사·후보 생성에만 사용되며 코드 만료({hours:g}시간) 시 자동 삭제됩니다.</b></p>
<ul>
<li>저장되는 것: 올린 영상/오디오 파일, 전사 결과, 올린 XML, 확인 코드. 음성 인식은 이 서버 안에서
실행되며 외부 서비스로 보내지 않습니다.</li>
<li>코드는 처음 사용한 때부터 {hours:g}시간 유효하고, 프로젝트를 최대 {max_projects}개 만들 수
있습니다(영상 하나당 최대 {max_minutes}분, 전사는 서버 전체에서 한 번에 하나).</li>
<li>코드가 만료되거나 회수되면 그 코드로 만든 모든 프로젝트·영상·결과가 자동으로 삭제됩니다.
각 프로젝트는 직접 즉시 삭제할 수도 있습니다.</li>
<li>다른 사람의 얼굴·목소리가 담긴 영상은 올려도 되는 것만 올려 주세요.</li>
</ul>
<label for="code">초대 코드</label>
<input id="code" type="text" name="code" autocomplete="off" placeholder="AIE-XXXX-XXXX-XXXX">
<label><input type="checkbox" name="consent" value="yes"> 위 내용을 읽었고 동의합니다 (필수)</label>
<button type="submit">동의하고 시작</button>
</form>
"""
    return page("체험 시작", body + studio("Resolve 안에서 실행되므로 영상을 업로드하지 않습니다."))


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
<li>음성 인식은 faster-whisper <code>small</code> 모델(CPU)입니다. 큰 모델보다 오인식이 많고, 단어 타이밍은
경험적으로 보정된 값(HEURISTIC_ADJUSTED)입니다. 고정 프레임레이트(CFR) 영상만 받고, 길이와 크기에 제한이 있습니다.</li>
<li>체험 서버입니다: 초대 코드 외의 인증·데이터베이스가 없고, 프로젝트는 서버 폴더에 저장되었다가 정해진 시간 뒤 자동 삭제됩니다.</li>
</ul></div>
"""
    return page(
        "한계",
        body
        + studio(
            "현재 타임라인에 바로 적용되어 그레이드·이펙트·믹스가 유지되고, 사후 검증도 네이티브로 읽습니다."
        ),
    )


def _error_box(error: str, codes: Sequence[str]) -> str:
    if not error:
        return ""
    items = "".join(f"<li><code>{e(c)}</code></li>" for c in codes)
    return f'<div class="err"><p>{e(error)}</p>{"<ul>" + items + "</ul>" if items else ""}</div>'


def _timeline_fields(val: Callable[[str, str], str], p: str) -> str:
    return f"""
<label for="{p}timeline_name">새 타임라인 이름</label>
<input id="{p}timeline_name" type="text" name="timeline_name" value="{val("timeline_name", "AIE 후보")}">
<label for="{p}timeline_start">타임라인 시작 타임코드</label>
<input id="{p}timeline_start" type="text" name="timeline_start" value="{val("timeline_start", "01:00:00:00")}">
<label for="{p}gap_seconds">전사 공백 기준(초)</label>
<input id="{p}gap_seconds" type="text" name="gap_seconds" value="{val("gap_seconds", "1.0")}">
<p class="hint">단어 사이 빈 구간이 이 값 이상이면 후보로 표시합니다(음향 무음 분석 아님).</p>"""


def new_project(
    error: str = "",
    codes: Sequence[str] = (),
    values: dict[str, str] | None = None,
    *,
    csrf: str = "",
    max_minutes: int = 10,
    max_mb: int = 1024,
    asr_label: str = "faster-whisper small (CPU)",
    allow_json: bool = True,
    notice: str = "",
    busy: bool = False,
    vad_default: bool = True,
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
    vad_on = v.get("vad", "1" if vad_default else "") == "1"
    vad_checked = " checked" if vad_on else ""
    busy_note = (
        "<p class='warn'>지금 다른 전사 작업이 진행 중입니다. 한 번에 하나만 처리하므로 잠시 후 올려 주세요.</p>"
        if busy
        else ""
    )
    media_form = f"""
<form class="card" method="post" action="/media" enctype="multipart/form-data">
{csrf_field(csrf)}
<h2>A. 영상 올리기 (권장)</h2>
{busy_note}
<label for="media">영상/오디오 파일 (최대 {max_minutes}분, {max_mb} MB · mp4/mov/mkv/mxf/wav 등)</label>
<input id="media" type="file" name="media" accept="video/*,audio/*,.mxf,.mkv">
<p class="hint"><b>고정 프레임레이트(CFR)</b> 영상만 받습니다. 휴대폰 영상은 대개 가변(VFR)이라
CFR로 변환 후 올려 주세요. 전사: {e(asr_label)}, 단어 타임스탬프. 이 서버 안에서 실행됩니다.</p>
<label for="media_folder">Resolve에서 보이는 원본 폴더 경로 (선택)</label>
<input id="media_folder" type="text" name="media_folder" value="{val("media_folder")}" placeholder="D:\\Footage">
<p class="hint">XML의 미디어 경로 = 이 폴더 + 원본 파일 이름. 비워 두면 파일 이름만 쓰므로, Resolve로
가져온 뒤 미디어가 오프라인이면 <b>Relink</b>로 원본을 연결하세요.</p>
{_timeline_fields(val, "m_")}
<input type="hidden" name="vad_choice" value="1">
<label><input type="checkbox" name="vad" value="1"{vad_checked}> 음성 구간 필터(VAD) 사용 — 기본 켬</label>
<p class="hint">VAD는 긴 무음과 잡음 구간의 잘못된 인식을 줄이지만, 아주 작은 목소리를 빠뜨릴 수 있습니다.
작게 말하는 부분이 전사에서 빠지면 끄고 다시 올려 보세요. 결과의 전사 정보에 VAD 사용 여부가 기록됩니다.</p>
<button type="submit">올리고 전사 시작</button>
</form>"""
    if not allow_json:
        body = f"""
<h1>새 프로젝트</h1>
{_error_box(error, codes)}
{notice}
{media_form}
"""
        return page(
            "새 프로젝트",
            body
            + studio(
                "영상을 업로드하지 않습니다. 프레임레이트와 시작 타임코드를 타임라인에서 직접 읽습니다."
            ),
        )
    body = f"""
<h1>새 프로젝트</h1>
{_error_box(error, codes)}
{notice}
{media_form}
<form class="card" method="post" action="/projects" enctype="multipart/form-data">
{csrf_field(csrf)}
<h2>B. 이미 가진 전사 JSON으로 만들기 (개발/고급)</h2>
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
    project_id: str,
    build: ProjectBuild,
    has_approval: bool,
    has_applied: bool,
    csrf: str = "",
    notice: str = "",
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
{notice}
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
{csrf_field(csrf)}
<label for="approval">Resolve에서 내보낸 FCP7 XML (최대 8 MB)</label>
<input id="approval" type="file" name="export" accept=".xml,text/xml,application/xml">
<button type="submit">업로드하고 확인 요약 보기</button>
<p class="hint">업로드는 선택을 읽을 뿐 아무것도 적용하지 않습니다.</p>
</form>

<form method="post" action="/p/{pid}/delete">
{csrf_field(csrf)}
<button class="danger" type="submit">이 프로젝트 삭제</button>
<p class="hint">작업 폴더와 업로드한 파일이 즉시 삭제됩니다. 오래된 프로젝트는 자동으로 삭제됩니다.</p>
</form>
"""
    return page("후보 목록", body)


def confirm_page(project_id: str, build: ProjectBuild, view: ApprovalView, csrf: str = "") -> str:
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
    tracks_html = _track_section(pid, view, csrf)
    layer_html = _layer_notes(view)
    if c.loss_risks:
        action = (
            "<div class='card'><p class='warn'><b>적용할 수 없습니다 (LAYER_LOSS_RISK).</b> "
            "새 파일이 담을 수 없는 항목이 있어, 그 항목을 잃지 않도록 아무것도 만들지 않습니다. "
            "위 레이어 메모를 확인하세요.</p></div>"
        )
    elif c.approved_cuts:
        action = f"""
<form class="card" method="post" action="/p/{pid}/confirm">
{csrf_field(csrf)}
<input type="hidden" name="digest" value="{e(c.confirmation_digest)}">
<p>위 내용대로 <b>{len(c.approved_cuts)}개 컷</b>, 총 <b>{e(seconds(c.removed_frames, rate))}초</b>를
<b>트랙별 결과</b> 표대로 적용한 <b>새 타임라인 파일</b>을 만듭니다. 트랙(레이어)은 병합하지 않습니다.</p>
<p class="muted">확인 코드 <code>{e(c.confirmation_digest[:16])}…</code> — 이 버튼이 승인입니다. 트랙 정책을
바꾸거나 내용이 바뀌면 코드도 바뀌어, 이전 코드는 거부됩니다.</p>
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
<p class="hint">HUMAN_EDIT_LOCKED = 사람이 고친 구간(보호), MARKER_CONFLICT = 다른 마커와 겹침,
LAYER_CONFLICT = 다른 트랙(음악·자막 등)의 항목이 컷에 걸침(자르지 않음), UNKNOWN = 판단 불가(적용 안 함).</p></div>
{"<h2>보호 구간 이동</h2><div class='card'><p>아래 보호 구간은 편집하지 않지만 앞쪽 컷 때문에 왼쪽으로 이동합니다.</p><ul>" + shifted_rows + "</ul></div>" if shifted_rows else ""}
{tracks_html}
{layer_html}
{action}
<h2>읽은 마커</h2>
<div class="card scroll"><table><tr><th>ID</th><th>마커 이름</th><th>선택</th><th>문제</th></tr>{sel_rows}</table></div>
<details class="card"><summary>확인 요약 원문 (결정적 텍스트)</summary><pre>{e(c.summary)}</pre></details>
{studio("같은 요약과 같은 트랙별 결과를 Resolve 안에서 보고, 색보정 전에는 확인 한 번으로 새 버전 타임라인에 적용합니다(원본은 백업). 실기(네이티브) 검증 전입니다.")}
<p><a href="/p/{pid}">← 후보 목록</a></p>
"""
    return page("확인 요약", body)


def _track_section(pid: str, view: ApprovalView, csrf: str) -> str:
    """LAYER-001 per-track effect, with a per-track policy override form."""
    c = view.confirmation
    effects = {effect.track_name: effect for effect in c.track_effects}
    rows: list[str] = []
    for name in view.track_names:
        effect = effects.get(name)
        current = view.override_for(name)
        policy_text = (
            f"변경: {e(POLICY_LABELS_KO[current])}"
            if current is not None
            else "기본 (원본 클립과 같은 소스면 함께 자르기, 아니면 뒤만 당기기)"
        )
        options = "".join(
            f'<option value="{e(p.value)}"{" selected" if current is p else ""}>{e(label)}</option>'
            for p, label in POLICY_LABELS_KO.items()
        )
        default_selected = " selected" if current is None else ""
        rows.append(
            f"<tr><td><b>{e(name)}</b></td><td>{policy_text}</td>"
            f"<td>{e(effect_label(effect)) if effect is not None else '—'}</td>"
            f'<td><form method="post" action="/p/{pid}/policy">{csrf_field(csrf)}'
            f'<input type="hidden" name="track" value="{e(name)}">'
            f'<select name="policy" aria-label="{e(name)} 정책">'
            f'<option value="DEFAULT"{default_selected}>기본</option>{options}</select> '
            f'<button type="submit">바꾸기</button></form></td></tr>'
        )
    return f"""
<h2>트랙별 결과</h2>
<div class="card scroll"><table><tr><th>트랙</th><th>정책</th><th>결과</th><th>정책 바꾸기</th></tr>
{"".join(rows)}</table>
<p class="hint">자름 = 승인한 구간을 이 트랙에서도 잘라 냄 · 당김 N프레임 = 자르지 않고 뒤쪽 항목만 앞으로 당김 ·
그대로 = 자르지도 당기지도 않음 · 보류: LAYER_CONFLICT = 이 트랙의 항목(예: 음악)이 컷에 걸쳐 있어 그 컷을
적용하지 않음. 음악을 컷과 함께 자르려면 그 트랙을 <b>함께 자르기</b>로 바꾸세요. 정책을 바꾸면 확인 코드가 바뀝니다.
Resolve에서 사람이 새로 넣은 항목은 함께 자르기로 바꿔도 보호(HUMAN_EDIT_LOCKED)되어 잘리지 않습니다.</p></div>"""


def _layer_notes(view: ApprovalView) -> str:
    c = view.confirmation
    items = [
        f"<li><code>{e(issue.code.value)}</code> {e(issue_label(issue))} — {e(issue.render())}</li>"
        for issue in (*c.layer_warnings, *c.loss_risks)
    ]
    items += [
        f"<li><code>LINK_NOT_PRESERVED</code> A/V 링크를 유지할 수 없어 링크 없이 씁니다 — {e(w)}</li>"
        for w in view.link_warnings
    ]
    if not items:
        return ""
    return (
        "<h2>레이어 메모</h2><div class='card'><ul>"
        + "".join(items)
        + "</ul><p class='hint'>MARKER_MOVED_TO_CUT = 지워지는 구간 안의 타임라인 마커는 버리지 않고 "
        "컷 지점으로 옮깁니다. LINK_NOT_PRESERVED = 한쪽만 잘리는 링크(J/L 컷 등)는 링크 없이 씁니다 — "
        "가져온 뒤 A/V 링크를 확인하세요.</p></div>"
    )


def _applied_tracks(applied: AppliedTimeline) -> str:
    if not applied.track_effects:
        return ""
    rows = "".join(
        f"<tr><td>{e(effect.track_name)}</td><td>{e(effect_label(effect))}</td></tr>"
        for effect in applied.track_effects
    )
    return (
        "<div class='scroll'><table><tr><th>트랙</th><th>결과</th></tr>" + rows + "</table></div>"
    )


def applied_page(project_id: str, applied: AppliedTimeline, csrf: str = "") -> str:
    pid = e(project_id)
    rate = applied.timeline.rate
    removed = sum(c.timeline_range.duration for c in applied.applied_cuts)
    remaining = ", ".join(applied.remaining_candidate_ids) or "없음"
    body = f"""
<h1>적용된 새 타임라인</h1>
<div class="card">
<p>새 타임라인 <b>{e(applied.timeline.name)}</b> · 적용 컷 {len(applied.applied_cuts)}개 ·
제거 {removed}프레임 ({e(seconds(removed, rate))}초) · 트랙별 정책대로 편집(트랙 병합 없음), 연결된 A/V는 같은 프레임</p>
{_applied_tracks(applied)}
<p class="warn">이 파일은 <b>검증되지 않은 Expected 산출물</b>입니다(verified = False). 아래 검증 단계를 거치세요.</p>
<p><a href="/p/{pid}/download/applied.xml">적용된 타임라인 — FCP7 XML 다운로드</a></p>
<p class="muted">남은 후보 마커: {e(remaining)}</p>
<h3>가져오기</h3>{import_steps()}
<p><b>주의:</b> 새 타임라인으로 가져와지므로 이전 타임라인의 색보정·이펙트·믹스는 넘어오지 않습니다.</p>
</div>
{studio("파일을 주고받지 않습니다. 색보정 전에는 Resolve 안에서 확인 한 번으로 새 버전 타임라인을 만들고 원본은 백업으로 둡니다. 색보정 후 그레이드 이전은 검증 중입니다.")}
<h2>4. 검증</h2>
<form class="card" method="post" action="/p/{pid}/verify" enctype="multipart/form-data">
{csrf_field(csrf)}
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


# --------------------------------------------------------------------------- WEB-002 pages


def facts_page(
    project_id: str,
    media: dict[str, object],
    csrf: str,
    error: str = "",
    codes: Sequence[str] = (),
    values: dict[str, str] | None = None,
) -> str:
    pid = e(project_id)
    v = values or {}
    need_rate = media.get("rate") is None
    tag = media.get("timecode_tag")
    rate_options = "".join(
        f'<option value="{e(key)}"{" selected" if v.get("rate", "24000/1001") == key else ""}>'
        f"{e(label)}</option>"
        for key, label in RATE_CHOICES
    )
    rate_field = (
        '<label for="rate">타임라인 프레임레이트 (영상 트랙 없는 오디오 파일)</label>'
        f'<select id="rate" name="rate">{rate_options}</select>'
        if need_rate
        else ""
    )
    tag_note = (
        f"<p class='warn'>파일의 시작 타임코드 태그 <code>{e(tag)}</code>를 읽을 수 없었습니다.</p>"
        if isinstance(tag, str)
        else "<p>이 파일에는 시작 타임코드 정보(태그)가 없습니다.</p>"
    )
    profile = v.get("profile", "RESOLVE")
    body = f"""
<h1>미디어 정보 확인</h1>
{_error_box(error, codes)}
<div class="card">
<p>파일 <code>{e(media.get("original_filename", ""))}</code> ·
프레임레이트 {e(media.get("rate") or "선택 필요")} · 길이 {e(media.get("duration_text", ""))}</p>
{tag_note}
<p>Resolve의 미디어 풀에서 클립을 선택하고 메타데이터/Clip Attributes의 <b>Start TC</b>(시작 타임코드)를
확인해 입력하세요. <b>0으로 가정하지 않습니다.</b> 모르면 "일반" 프로필을 고를 수 있지만, 그 경우 XML에
시작 타임코드를 쓰지 않으므로 Resolve가 클립 위치를 다르게 잡을 수 있습니다.</p>
</div>
<form class="card" method="post" action="/p/{pid}/facts">
{csrf_field(csrf)}
{rate_field}
<label for="media_start">미디어 시작 타임코드 또는 프레임</label>
<input id="media_start" type="text" name="media_start" value="{e(v.get("media_start", ""))}" placeholder="00:00:00:00">
<label for="profile">프로필</label>
<select id="profile" name="profile">
<option value="RESOLVE"{" selected" if profile == "RESOLVE" else ""}>DaVinci Resolve (시작 타임코드 필요)</option>
<option value="GENERIC"{" selected" if profile == "GENERIC" else ""}>일반 (시작 타임코드 모름)</option>
</select>
<label for="timeline_start">새 타임라인 시작 타임코드</label>
<input id="timeline_start" type="text" name="timeline_start" value="{e(v.get("timeline_start", "01:00:00:00"))}">
<button type="submit">저장하고 전사 시작</button>
</form>
<form method="post" action="/p/{pid}/delete">{csrf_field(csrf)}<button class="danger" type="submit">이 프로젝트 삭제</button></form>
"""
    return page(
        "미디어 정보",
        body + studio("프레임레이트와 시작 타임코드를 타임라인에서 직접 읽으므로 묻지 않습니다."),
    )


def status_page(
    project_id: str, job: dict[str, object], csrf: str, filename: str, notice: str = ""
) -> str:
    pid = e(project_id)
    state = str(job.get("state", ""))
    progress = job.get("progress")
    percent = int(float(progress) * 100) if isinstance(progress, (int, float)) else 0
    active = state in ("QUEUED", "RUNNING")
    head = '<meta http-equiv="refresh" content="3">' if active else ""
    if state == "QUEUED":
        text = "<p>대기 중입니다. 전사는 서버 전체에서 한 번에 하나씩 처리합니다.</p>"
    elif state == "RUNNING":
        text = (
            f"<p>전사 중… <b>{percent}%</b> (CPU에서 실행되어 영상 길이만큼 걸릴 수 있습니다)</p>"
            f'<progress max="100" value="{percent}">{percent}%</progress>'
        )
    elif state == "FAILED":
        raw_codes = job.get("codes")
        items = "".join(
            f"<li><code>{e(c)}</code></li>"
            for c in (raw_codes if isinstance(raw_codes, list) else [])
        )
        text = (
            f'<div class="err"><p>{e(job.get("message", ""))}</p>'
            f"{'<ul>' + items + '</ul>' if items else ''}</div>"
            "<p>부분 결과는 남기지 않았고 올린 파일도 지웠습니다. "
            '<a href="/new">다른 파일로 다시 시도</a></p>'
        )
    else:
        text = f'<p>완료되었습니다. <a href="/p/{pid}">후보 목록 보기</a></p>'
    refresh = "<p class='hint'>이 페이지는 3초마다 새로 고쳐집니다.</p>" if active else ""
    body = f"""
<h1>전사 상태</h1>
<div class="card">
<p class="muted">파일 <code>{e(filename)}</code> · 상태 <code>{e(state)}</code></p>
{text}
{refresh}
</div>
{notice}
<form method="post" action="/p/{pid}/delete">{csrf_field(csrf)}<button class="danger" type="submit">이 프로젝트 삭제</button></form>
"""
    return page(
        "전사 상태",
        body + studio("Resolve 내장 전사(쓸 수 있는 경우) 또는 같은 서버 ASR을 씁니다."),
        head=head,
    )


# docs/EDITION_DELIVERY_STRATEGY.md §7 (customer-safe claim until native verification)
STUDIO_STATUS_KO = (
    "네이티브 검증 대기 중입니다. 색보정 전에는 Studio가 확인 클릭 한 번으로 컷을 적용합니다(tier 1). "
    "색보정 후의 그레이드 이전은 검증 중입니다."
)
STUDIO_STATUS_EN = (
    "Native verification pending; before grading, Studio applies cuts with a confirm click "
    "(tier 1); after grading, grade transfer is being verified."
)


def studio_page() -> str:
    rows = (
        (
            "컷 적용",
            "새 타임라인 파일을 가져옴. 이전 타임라인의 색보정·이펙트·믹스는 넘어오지 않음",
            (
                "<b>색보정 전</b>: Resolve 안에서 확인 한 번으로 적용 (새 버전 타임라인, 원본은 백업 — tier 1). "
                "<b>색보정 후</b>: 그레이드 이전은 검증 중. 클립 경계와 맞는 컷은 현재 타임라인에서 바로 삭제 "
                "(tier 3), 그 밖에는 지정 위치 블레이드 안내(tier 4). 모두 네이티브 검증 대기"
            ),
        ),
        (
            "트랙(레이어)",
            "트랙별 정책: 대사 A/V는 자르고 음악·B-roll·자막은 당김, 병합 없음",
            "같은 트랙별 정책. '그대로 두기'는 Resolve API로 제자리 적용이 안 되어 새 버전으로만 적용",
        ),
        (
            "사람 편집 보호",
            "업로드한 XML을 내보낸 순간 기준",
            "실행할 때마다 타임라인에서 직접 읽음. 내보내기 없이 반복 실행",
        ),
        ("검증", "파일 왕복 증거 (FILE_ROUNDTRIP)", "편집 직후 네이티브 타임라인을 다시 읽어 비교"),
        ("승인 UI", "Resolve 안 마커 이름 + 브라우저 확인", "마커 이름 + Resolve 안 확인 대화상자"),
        (
            "정밀도",
            "Whisper 단어 타이밍 (서버 시계, 허용 오차 ≥ 1프레임)",
            "프레임 단위 네이티브 클립 경계, 링크·트랙 상태 인식",
        ),
        ("범위", "왕복 한 번에 타임라인 하나", "여러 타임라인, 트랙별 정책, 네이티브 보호 구간"),
        (
            "전사",
            "서버 ASR (이 체험: faster-whisper small)",
            "Resolve 내장 전사(가능한 경우) 또는 서버 ASR",
        ),
        ("렌더링", "없음 — 최종 렌더는 Deliver", "없음 — 최종 렌더는 Deliver"),
    )
    table = "".join(
        f"<tr><td><b>{e(a)}</b></td><td>{e(b)}</td><td>{c}</td></tr>" for a, b, c in rows
    )
    body = f"""
<h1>Free 체험과 Studio</h1>
<p>Free 체험은 흐름이 끝까지 동작하는 것을 보여 주는 데모입니다. 실제 제품은 <b>Resolve Studio 안에서</b>
동작하도록 개발 중이며, 같은 후보·같은 승인 규칙·같은 적용 결과·같은 검증 용어를 씁니다.</p>
<div class="card scroll"><table><tr><th>영역</th><th>Free 체험 (이 웹)</th><th>Studio (Resolve 안)</th></tr>{table}</table></div>
<div class="card"><h2>현재 상태 (정직하게)</h2>
<p><b>{e(STUDIO_STATUS_KO)}</b></p>
<p class="muted" lang="en">{e(STUDIO_STATUS_EN)}</p>
<ul>
<li>Studio 경로는 <b>개발 중</b>입니다. Resolve 안에서의 적용과 사후 검증은 <b>아직 네이티브 검증(실기 검증)을 통과하지 않았습니다</b>.</li>
<li>색보정 전: Resolve 안에서 새 버전 타임라인을 가져와 <b>확인 한 번</b>으로 컷을 적용합니다(tier 1). 원래 타임라인은 수정하지 않고 백업으로 둡니다.
네이티브 검증 전까지 "확인만 누르면 된다"는 약속은 이 경우(tier 1)에만 합니다.</li>
<li>색보정 후: 그레이드·Fusion 이전은 <b>검증 중</b>입니다. Resolve가 지원하는 범위에서, 실제 Resolve로 검증된 뒤에만 약속합니다.
그 전까지 권장 사용법은 Free와 같습니다: <b>컷 확정은 색보정 전에.</b></li>
<li>이 Free 체험의 결과 파일도 Expected 산출물이며, 검증 리포트가 MATCH일 때만 의도와 일치함을 뜻합니다.</li>
</ul></div>
"""
    return page("Studio", body)


def guide_page() -> str:
    body = """
<h1>DaVinci Resolve 무료 버전으로 체험하기</h1>
<ol class="card">
<li><b>CFR 영상 준비</b>: 1~10분짜리 말하는 영상. 휴대폰 영상은 대개 가변 프레임레이트(VFR)이므로
Resolve(Deliver에서 같은 프레임레이트로 렌더)나 HandBrake("Constant Framerate")로 <b>CFR로 변환</b>하세요.</li>
<li><b>Resolve 프로젝트 프레임레이트</b>: 새 프로젝트를 만들고 <b>File &gt; Project Settings &gt; Master Settings</b>에서
Timeline frame rate를 영상과 <b>같은 값</b>으로 맞춥니다(타임라인을 만들기 전에).</li>
<li><b>업로드</b>: <a href="/new">새 프로젝트</a>에서 영상을 올립니다. 원본이 있는 폴더 경로를 Resolve에서 보이는
그대로 적으면 바로 연결되고, 비워 두면 다음 단계에서 Relink 합니다. 시작 타임코드 태그가 없으면
Resolve 클립 속성의 Start TC를 물어봅니다.</li>
<li><b>XML 가져오기</b>: 전사가 끝나면 후보 목록에서 <b>FCP7 XML</b>을 받아 <b>File &gt; Import &gt; Timeline…</b> 으로 가져옵니다.</li>
<li><b>Relink</b>: 클립이 빨간색(오프라인)이면 미디어 풀에서 클립 우클릭 &gt; <b>Relink Selected Clips…</b> 로 원본 폴더를 지정합니다.</li>
<li><b>마커 이름으로 선택</b>: 타임라인의 <code>AIE-0001 ?</code> 마커를 더블클릭해 이름을 <code>AIE-0001 OK</code>(적용)
또는 <code>AIE-0001 X</code>(제외)로 바꿉니다. 마커를 옮기거나 지우지 마세요.</li>
<li><b>내보내기</b>: 타임라인을 선택하고 <b>File &gt; Export &gt; Timeline…</b> 에서 <b>FCP 7 XML (.xml)</b> 로 저장합니다.</li>
<li><b>업로드 → 확인</b>: 프로젝트 페이지에서 그 XML을 올리고, 확인 요약을 읽은 뒤 <b>확인</b> 버튼을 누릅니다.</li>
<li><b>적용된 타임라인</b>: <code>… AIE v2</code> XML을 받아 다시 Import &gt; Timeline 으로 가져옵니다(새 타임라인).</li>
<li><b>검증</b>: 가져온 새 타임라인을 고치지 않고 다시 FCP 7 XML로 내보내 올리면 MATCH / MISMATCH / UNVERIFIED 리포트가 나옵니다.</li>
</ol>
<p class="muted">Resolve의 FCP7 XML 가져오기/내보내기 세부 동작은 실제 Resolve에서 아직 검증 중입니다.
결과가 이상하면 검증 리포트의 코드를 알려 주세요.</p>
"""
    return page(
        "Resolve 안내",
        body + studio("가져오기·내보내기·Relink 없이 Resolve 안에서 바로 후보를 보고 승인합니다."),
    )
