# Output language / 产物语言

Resolve the output language before assembling any visible text. An explicit
request to render in a language wins over the dominant language the user uses
to describe the task or interact with the agent. Infer English or Chinese from
that interaction, not from this skill's documentation, media filenames, player
names, browser locale or quoted source text. For mixed interaction, use the
dominant task language; if genuinely unclear, retain the saved language and ask
only if the choice materially affects delivery. A short continuation such as
“OK” does not switch an established language or revoke an explicit request.

Record `outputLanguage` (`en` or `zh-CN`) and its basis in the stage record and
local project. Carry it through subsequent stages. A new explicit request can
change it; regenerate dependent text from the same data without changing score,
evidence, timing, IDs, review rows or answers. Legacy helper calls without a
language retain Chinese for compatibility; agents must pass the resolved value.
Do not silently substitute English or Chinese for an unsupported language:
prepare and verify the requested translations and layout before rendering.

This applies to all seven overlays, score/rule badges, serve and speed labels,
explanations, five statistics pages, comparison matrices, review timelines,
standalone HTML, generated HTML headings, controls, statuses, accessibility text,
captions and export instructions. Author task-specific descriptions, reasons,
subtitles and footnotes in the resolved language. Preserve original evidence and
user notes separately; do not rewrite names, source identifiers or quotations.
Do not produce extra reports merely to demonstrate a language.

The persistent studio already supports English and Chinese UI. Its interface
toggle is independent of `outputLanguage`: switching the UI must not translate
project content or rewrite saved review answers. Static graphics must be
regenerated when their output language changes.

## Interfaces

- `output_language.resolve_language(explicit, interaction, saved)` accepts language
  tags supplied by the agent; it does not guess language from arbitrary text.
- `template_pack.bundle(component, overrides, language='en')` localizes defaults
  for all seven canonical JSX templates. Explicit overrides are authoritative;
  write all supplied visible text in the selected language. CLI:
  `python scripts/template_pack.py scoreboard --language en --output bundle.json`.
- `build_stats_pages(metrics, speed_summary, diagnostics, language='en')` retains
  the same 39 keys, denominators, highlights and five pages. Use these same rows
  for HTML tables/matrices. `output_language.text` supplies shared terminology;
  the English catalog is [output-en.json](output-en.json).
- `serve_overlay.build_plan(records, fps, language='en')`; CLI input uses
  `outputLanguage`. `1st serve`, `2nd serve`, `2nd · DF` (double fault), and
  `· Let` retain the same verified-event timing. `Est.` means an estimate;
  `Imp.` explicitly marks a model-imputed estimate. Explain these abbreviations
  in the accompanying selected-language statistics footnote when applicable.
- `review_io.build(data, target, language='en')` or
  `python scripts/review_io.py build review.json review.html --language en`.
  The data's `outputLanguage` is used when the argument is absent. Localized
  HTML retains the same draft key, point IDs, full export and state transitions.
  Caller-supplied reasons, names, notes and timeline names are not translated.
- PNG requests accept top-level `outputLanguage`, with an optional per-entry
  override. Local graphics rendering passes the saved project language through.
  `node scripts/make_mogrt.cjs new-directory FontName en` creates English native
  defaults. Both adapters retain explicit caller text and canonical styling.

## Terminology and semantic boundaries

| 中文 | English | Meaning |
|---|---|---|
| 分 / 局 / 盘 | Point / game / set | Score units; not clip count |
| 第N分 / 第N局 / 第N盘 | Point N / Game N / Set N | Visible numbering; P and R IDs stay unchanged |
| 发球方 / 接发方 | Server / receiver | Player roles |
| 一发 / 二发 | 1st serve / 2nd serve | Serve opportunity, not every toss |
| 双误 / 擦网重发 | Double fault (DF) / serve let | Let does not consume the serve opportunity |
| 整分重打 / 多打 | Replayed point / extra point | Distinct non-scoring states |
| 无占先 / 金球 | No-ad / deciding point | Deciding point at 40–40 |
| 制胜分 / 非受迫性失误 / 受迫性失误 | Winner / unforced error (UE) / forced error (FE) | Preserve classification evidence |
| 正手 / 反手 | Forehand (FH) / backhand (BH) | Stroke side |
| 移动中 / 站定 | On the move / stationary | Independent UE motion classification |
| 初速 / 飞行均速 | Launch speed / mean flight speed | Never interchangeable |
| 估算 / 补估 | Estimated / model-imputed | Not radar measurements |
| 待填写 / 未完整 | Pending / incomplete | `pending` / `partial`; not human reviewed |
| 人工无法确定 | Cannot determine | Human-reviewed unresolved scorer; inference still needed |
| 已复核 / 已解决 | Reviewed / resolved | Reviewed can include unresolved cases |
| 待核 / 不适用 | Unverified / not applicable | Missing evidence differs from a zero denominator |
| 逐分精剪 / 必要复核 | Point-by-point edit / required review | Preserve stage boundaries |

The full metric label mapping is in the shared catalog. Translate descriptor
headings and prose using these terms; do not translate JSON keys, enum values,
schema names, file paths, mathematical units or provenance categories.

## Verification

Check English and Chinese at target resolution, including long names, 11-row
serve statistics, imputed speed labels, double faults and lets, review headings,
keyboard controls and full exports. Preserve the seven JSX sources and visual
design. Shorten labels with established abbreviations or use supported layout
dimensions when necessary; never clip text or alter statistical meaning to fit.
