# SITE-001 — Coditor public landing site

Qualification: **CODE_COMPLETE / TEST_ONLY_SUPPORT**. Nothing deployed from this
milestone; the server was only started on `127.0.0.1:8768` for a smoke check.
Builds on WEB-001 / WEB-002 / INT-002; the trial and editing flow is unchanged.

## Purpose

The product is named **Coditor**. It will be served at `https://safestay.kr` (and
`www.`) through a Cloudflare tunnel to this web app, replacing an old WordPress
site. Audience: Korean editors / agencies cutting long talking-head interviews
in DaVinci Resolve. Core message: "AI에게 편집 업무는 맡기되, 편집권은 넘기지 않는다."

## Pages (public, no login)

| Path | Content |
|---|---|
| `/` | Hero (inline-SVG timeline with candidate markers), problem, 4-step diagram (CSS steps + inline SVG), why different, Free vs Studio table (EDITION_DELIVERY_STRATEGY.md §3/§7, Studio "개발 중 · 실기 검증 예정", "확인 클릭만" for tier 1 only), trial info + code request, embedded consent / code form in trial mode |
| `/trial` | Standalone consent / code form (trial mode only; 404 otherwise; redirects to `/new` with an active code) |
| `/privacy` | Privacy notice generated from the configured retention rules (trial: code expiry; otherwise `AIE_WEB_MAX_AGE_HOURS`), cookies, no tracking, contact |
| `/studio`, `/guide`, `/limits` | Existing pages, restyled |
| `/robots.txt` | Allow `/`, `/privacy`, `/studio`, `/guide`; disallow `/p/`, `/new`, `/media`, `/projects`, `/trial`, `/admin` |

Primary CTA "체험 코드로 시작하기" goes to the embedded form (`#start`) in trial
mode; with an active code or without trial mode it goes to `/new`.

## Design

- Stdlib HTML/CSS only (`render.py`), no JavaScript, no external URL, font, script
  or image. System font stack. Favicon is an inline SVG data URI.
- One set of design tokens on `:root` (dark first, light via
  `prefers-color-scheme`), one accent (marker amber) used by every page (trial,
  upload, confirmation, verification, Studio, guide). Skip link, `:focus-visible`,
  landmarks (`header`/`nav`/`main`/`footer`, labelled sections), `lang="ko"`,
  `role="img"` + title/desc on the hero SVG, decorative SVGs `aria-hidden`.
- Responsive to 360 px (grids collapse; tables scroll inside their card).
- Meta: title "Coditor — 인터뷰 편집 어시스턴트 for DaVinci Resolve", description,
  Open Graph (type, site_name, locale, title, description; no `og:url`/`og:image`
  because they need absolute URLs). Public pages `index, follow`; app pages
  `noindex, nofollow`.
- CSP gains only `img-src data:` (favicon). No `script-src`. Cookies unchanged
  (`aie_csrf`, `aie_trial`).

## Settings added

| Variable | Default | Meaning |
|---|---|---|
| `AIE_WEB_CONTACT_EMAIL` | `contact@safestay.kr` (**placeholder**) | address shown for trial-code requests and privacy questions (`mailto:` only) |

## Production hosting (safestay.kr via Cloudflare tunnel)

```text
$env:AIE_WEB_TRIAL="1"
$env:AIE_WEB_ALLOWED_HOSTS="safestay.kr,www.safestay.kr,demo.safestay.kr,127.0.0.1,localhost"
$env:AIE_WEB_TRUST_PROXY="1"        # behind Cloudflare: X-Forwarded-Proto, CF-Connecting-IP
$env:AIE_WEB_SECURE_COOKIES="1"
$env:AIE_WEB_MAX_MEDIA_MB="95"      # Cloudflare 100 MB request-body cap
$env:AIE_WEB_CONTACT_EMAIL="<real address>"   # replace the placeholder
$env:AIE_WEB_ROOT="D:\aie-trial"
python -m uvicorn aie_web.app:app --app-dir apps/web --host 127.0.0.1 --port 8765
```

The tunnel (named tunnel with `safestay.kr` / `www.safestay.kr` routes) points
at `http://127.0.0.1:8765`; keep the server bound to loopback. DNS cut-over from
the WordPress host and the tunnel configuration are outside this repository.
Whether `www` should redirect to the apex is a Cloudflare rule (not done here).

## Tests (`tests/web/test_site_001.py`)

Landing sections / key Korean strings / meta / favicon / no percentages; CTA by
trial state (open / active / local) and `/trial`; contact placeholder, override,
env var and escaping; privacy text for trial and local retention; Studio and
guide pages; no external URL, `<script>`, `@import` or `url(` in public and
trial HTML; `robots.txt`; security headers and a single `aie_csrf` cookie on
public pages; shared tokens / skip link / focus styles on app pages, robots
meta; allowed hosts for safestay.kr. Existing WEB-001/002 and INT-002 tests pass
unchanged.

## Open

- `contact@safestay.kr` is a placeholder; set the real address.
- The privacy notice is a short trial notice, not a legal review (PIPA items such
  as a named privacy officer are not included).
- No `og:image` (would need an absolute URL and a hosted image).
