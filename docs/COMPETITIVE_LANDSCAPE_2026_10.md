# Competitive Landscape — 2026-10 (desk research)

Status: **DESK RESEARCH / UNVALIDATED WITH CUSTOMERS**. Sources were accessed
2026-10-17. Official product pages, docs and pricing pages were preferred;
secondary sources are marked [2nd]. `UNVERIFIED` means no evidence was found,
not that a feature is absent. This document informs priorities; it is not
product evidence and does not change any gate.

## 1. Comparison

| Product | Delivery / NLE | Handoff | Core AI | Korean | Re-run after human edits | Automation | Price (public) | Resolve / Studio |
|---|---|---|---|---|---|---|---|---|
| Eddie AI | Web, desktop, iOS, MCP; Premiere/Resolve extensions, Avid beta | Premiere, FCP, Resolve, OTIO; v4 native .prproj/.drp, FCPXML both ways [2nd] | chat rough cut, multicam, selects, filler/silence | 100+ ASR languages (Korean quality UNVERIFIED) | **Partial**: can import NLE timelines/projects; preserving human edits on re-edit not documented | chat instruction → generated result | credits (~$10 per 1,000) | extension; Studio need UNVERIFIED |
| Cutback (Seoul) | Premiere extension; standalone Selects app | Selects → Premiere/FCP/Resolve | silence, filler, multicam, rough cut | **Korean UI/guides**; direct domestic competitor | **No**: docs state sequence restore is all-or-nothing | preview → apply to sequence | $0–30/mo | Premiere Assistant Premiere-only; Selects hands off to Resolve |
| Gling | desktop (YouTubers) | XML (Premiere/FCP/Resolve), SRT | bad takes, silence, filler | Korean speech supported; English UI | UNVERIFIED | AI first pass, human review | free–$100/mo | XML, works with Free |
| FireCut | Premiere/Resolve plugin | applies to timeline | silence, filler, repetition, podcast, captions | 50–90+ languages, many "experimental" | UNVERIFIED | one-click "magic cut" | $8–50/mo | **Resolve Free supported** (20+) |
| AutoCut | Premiere/Resolve plugin | applies to timeline | silence, repeated takes, podcast | Korean site UI; speech UNVERIFIED | UNVERIFIED | preview; Remove/Keep/Mute | $6.6–19.9/mo | **Free and Studio supported** |
| TimeBolt | desktop, local-first | XML, plugin | silence, filler (paid per minute) | UNVERIFIED | UNVERIFIED | UNVERIFIED | $17/mo or $347 lifetime | XML |
| Recut | desktop | XML (Premiere/Resolve/FCP) | silence, multitrack | UNVERIFIED | UNVERIFIED | "non-destructive" | $129 once / $15/mo | XML |
| Descript | web, desktop | XML (Creator+) | text editing, filler, Underlord | **No Korean transcription** (help center: Latin-script languages) | No; publishes Resolve-XML loss table | manual/semi | $16–50/mo | users report cut loss via XML |
| Vrew (VoyagerX) | desktop, web | Premiere XML (user reports; official doc UNVERIFIED) | auto captions, text cut, bulk silence removal | **Korean-first** | UNVERIFIED | bulk apply, undo | 4 tiers | UNVERIFIED |
| Premiere built-in | NLE | – | text-based editing, filler/pause filter, AI Assistant beta (2026-06) | current Korean STT UNVERIFIED | n/a | human deletes; Assistant "Always ask / Auto approve" | CC | – |
| Resolve built-in | NLE | – | transcription, text editing, IntelliScript, IntelliSearch | Korean transcription (18.5) [2nd] | n/a | manual | Studio $295 | transcription Studio-only [2nd] |
| Simon Says | web, Mac, NLE extensions, on-prem | Premiere/FCP/Resolve/Avid, SRT | transcription, assembly | UNVERIFIED | UNVERIFIED | manual | ~$0.05/min | extension |
| Opus Clip / Riverside / Kapwing / CapCut | web SaaS (short-form/recording) | Opus XML+SRT, Riverside AAF; others render | clips, filler/pause | Kapwing Korean transcription | No | automatic | – | n/a |

Not researched: Wisecut, Veed, Adobe Firefly editing.

## 2. White space against this project's principles

| Planned differentiator | Market status | Confidence |
|---|---|---|
| Human Edit Wins on re-run (preserve accepted human edits) | **Not found documented anywhere**; Cutback explicitly all-or-nothing restore; Eddie closest (imports timelines) | medium — must be tested hands-on (H5) |
| Post-edit verification (planned vs actual timeline) | **Not found**; many products publish handoff loss tables / users report lost cuts | medium-high |
| Candidates only, approval required | **Commoditized** (AutoCut preview, Cutback preview-apply, Premiere filters, Premiere Assistant "Always ask") | high |
| Korean quality | Partially contested (Cutback, Vrew, Gling); **Korean + Resolve + long interview** combination looks open | medium |
| No Resolve Studio purchase | **Not unique** (FireCut, AutoCut, XML tools support Free) | high |

### Material platform risk

Resolve 21.1 (2026-09) release notes move Python scripting to Studio; Puget
Systems reports scripting removed from Free (`pugetsystems.com/blog/2026/09/10/...`).
A *live* Resolve connector for Free users is therefore likely blocked. File
round-trip is the only Free-compatible path. Lua / Workflow Integration
availability on Free is UNVERIFIED.

## 3. Development implications (applied)

1. **Prioritise file round-trip, not a live connector.** After HANDOFF-001
   (writers), the next milestone is **RT-001: re-import a human-edited
   timeline file (FCP7 XML / OTIO) and compute a diff against the Expected
   artifact**, classifying each region as untouched / human-edited / missing /
   moved. Human-edited regions become HARD_LOCK `ProtectedRange`s for any
   re-run (Human Edit Wins).
2. **VER-001: verification report** comparing approved candidates (Expected)
   with the re-imported timeline (Actual): missing cuts, frame drift, marker
   loss, track/bin flattening. Uses existing Expected ≠ Actual concepts; a file
   re-import is FILE_ROUNDTRIP evidence, never native evidence.
3. **Korean candidates stay, measured against a baseline.** KOR-001 is kept as
   candidate evidence; H3 requires a precision baseline vs Cutback/Vrew before
   any product claim.
4. **Do not build (commoditized):** generic silence-removal engine as headline,
   animated captions, B-roll/music generation, short-form clipping, multicam
   auto-switching, generic chat editing.
5. **Hold:** live Resolve connector for Free users (21.1 scripting policy);
   consider Studio-only option later. Native mutation gates are unchanged.

## 4. Hypotheses for design partners

- H1: long-form interview editors avoid re-running AI after manual edits (fear
  of overwrite) at least weekly.
- H2: after an XML round-trip they spend ≥30 min per project checking cuts
  landed, and would pay for an automatic verification report.
- H3: unless Korean filler/repetition precision clears a usable bar, reviewing
  candidates costs more time than editing directly (measure vs Cutback/Vrew).
- H4: Resolve Free users accept file import without a live connector.
- H5: Eddie v4 FCPXML round-trip does not guarantee preservation of human
  edits (verify hands-on).

## 5. Sources (accessed 2026-10-17)

heyeddie.ai (+/pricing, /workflows/adobe-premiere-pro, /workflows/davinci-resolve);
cined.com Eddie AI v4 article (2026-09-09) [2nd]; cutback.video (+/pricing,
/ko/guide/silence-remover, Selects blog 2026-10-13); gling.ai (+/pricing);
firecut.ai (+/pricing, learn.firecut.ai installing guide); autocut.com (+help
center settings); digitalproduction.com 2026-04-08 AutoCut; timebolt.io
(+/pricing); getrecut.com; descript.com/pricing and help.descript.com articles
10249408168845, 10255813481613; feedback.descript.com DaVinci support; vrew.ai
(ko, auto-silence-removal, price policy); community.adobe.com Vrew XML thread;
helpx.adobe.com Premiere what's new 2024-1; community.adobe.com NAB 2026 post;
kompozy.io Premiere AI Assistant review [2nd]; blackmagicdesign.com what's new /
Studio; newsshooter.com 2026-06-02 Resolve 21; pugetsystems.com 2026-09-10
Resolve Free 21.1 scripting; simonsaysai.com; help.opus.pro Resolve import;
support.riverside.com 5701862492829; kapwing.com smart-cut / Korean transcribe;
capcut.com export help; ai.g2.com Spingle; try.wideframe.com 2026-05-12.
