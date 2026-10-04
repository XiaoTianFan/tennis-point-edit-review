# Premiere integration investigation

Research date: 2026-10-04. This is repository maintenance documentation, not a
second set of match instructions. The portable workflow belongs in the skill.

## Decision

Treat ChatCut, Premiere Pro and a standalone media pipeline as three primary
editing environments. Select the environment from the user's request, existing
project and demonstrated capabilities. Select the graphics implementation
separately. The owner selected a hybrid Premiere approach: native editable
graphics where practical, rendered overlays for dense statistics.

The tennis evidence, ledger, scoring, review answers, statistics and serve timing
stay independent of both choices. An editor adapter consumes their results;
it must not infer winners, renumber points or recalculate statistics itself.

## What the evidence supports

| Route | What it provides | Limits and current qualification |
|---|---|---|
| Community MCP | Agent-friendly calls into a local Premiere instance; useful for inspection, import, MOGRT instances and export | A transport and adapter, not an Adobe guarantee; qualify the exact tool and host version |
| FCP7 XML / XMEML | Bulk import of media, tracks and frame-based cuts into an editable sequence; can be imported manually, by MCP or a plugin | Not modern FCPXML; graphics, time remapping and effects do not universally round-trip |
| Direct CEP / ExtendScript | Premiere's legacy scripting DOM via a running panel; suitable for the installed 23.5 host | JSX here means Adobe ExtendScript, not React JSX; no supported headless Premiere command-line editor |
| Direct UXP | Modern native plugin API, transactions, timeline editing, MOGRT insertion | Official since 25.6; not available on the installed 23.5 host; 26.3 changes action locking and some API behavior |
| Native graphics / MOGRT | Editable text, numbers, colors and other explicitly exposed template controls | Needs an actual compatible template and host readback; importing an image never creates editable text |
| Rendered overlays | Canonical JSX can produce transparent PNGs or alpha video; ideal for complex tables | Text changes require regenerating the asset; fonts, alpha, scaling, timing and color must be checked in Premiere |

Adobe documents UXP timeline editing and MOGRT insertion in
[SequenceEditor](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/sequenceeditor/),
project transactions and imports in
[Project](https://developer.adobe.com/premiere-pro/uxp/ppro-reference/classes/project/),
and version-specific changes in its
[changelog](https://developer.adobe.com/premiere-pro/uxp/changelog/).
The official legacy
[PProPanel sample](https://github.com/Adobe-CEP/Samples/blob/master/PProPanel/jsx/PPRO/Premiere.jsx)
demonstrates the CEP/ExtendScript route. These are application APIs, not a
standalone official desktop-editing MCP server.

The inspected community candidate is
[hetpatel-11/Adobe_Premiere_Pro_MCP](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP),
npm `adobe-premiere-pro-mcp` 1.2.8. The package was downloaded and its import,
graphics, export, installer and bridge code inspected. Its supported bridge is
CEP; its bundled UXP bridge is experimental. The npm executable name alone is
not a sufficient package identity. Pin the package/version and retain its hash.
See its [release notes](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP/releases)
and [privacy policy](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP/blob/main/PRIVACY.md).

MCP and XML are complementary: a single XML import can build the cut structure,
then host calls can install MOGRT instances, read back timing and export. Direct
UI import is also a valid route for an agent without MCP. XML generation alone
does not prove Premiere imported or rendered it correctly.

## Corrections to the earlier assessment

- "All community bridges must use CEP" is too broad. UXP is officially released
  and has timeline/MOGRT APIs. This candidate's UXP implementation and this
  computer's older host remain separate limitations.
- The seven React JSX templates are predominantly static; the statistics panel
  has a four-point opacity envelope. That does not make them native Premiere
  graphics. They need rasterization, rendering or an explicitly maintained
  native implementation.
- Not all seven components expose `transparentBackground`. Where present, that
  property controls a component's panel fill. Transparent image canvas and
  panel styling are separate; do not remove the navy panel to obtain alpha.
- Integer XML frames remove floating-point accumulation in the edit plan but
  do not eliminate VFR, mixed-rate or source-time quantization error.
- An importer returning success, a tool catalog entry, or an empty reported gap
  list is not proof of correct composition or audio. Read back tracks and
  export real frames and a video segment.
- Native MOGRT is appropriate when manual text editing matters. It is not a
  reason to rewrite dense statistics manually or create another score source.
  Adobe describes exposed text/color/layout controls in its
  [MOGRT authoring documentation](https://helpx.adobe.com/after-effects/desktop/motion-graphics/work-with-motion-graphics-templates/creating-motion-graphics-templates.html).

## Local baseline (private media stays outside the package)

Read-only inspection found Premiere Pro 23.5.0, After Effects/Media Encoder 2023,
FFmpeg, Python and Node. The supplied ChatCut project was read through its public
desktop tools. Its active timeline is 1920x1080 at 30 fps, 19,449 frames, with
five video tracks. The supplied rendered video is 60 fps and about 648.32 seconds.
The source is 1920x1080 H.264/BT.709, approximately 2,394.15 seconds, with nominal
60000/1001 and a different average rate. Probe actual timestamps before claiming
CFR; preserve the source timestamps when normalizing excerpts.

The reference includes a stable point ledger, score audit, graphics data and
serve overlay plan. Use these as a transfer baseline, not as a fresh independent
endorsement of every tennis judgment. Preserve confirmed review answers and
the existing ChatCut project. All test outputs belong in a separate scratch
project and ignored local output directory.

The candidate was installed locally for testing with telemetry/update checks
disabled. Its broad installer defaults were narrowed: no client configuration
was changed and only the installed CEP runtime's debug setting was enabled,
with previous state recorded. No successful connection or host mutation has
yet been established. Windows Computer Use was stopped by a physical Escape
before live bridge setup; app control stopped at that point.

## Test sequence and acceptance

1. **Portable helpers:** rational rates/ticks, half-open cut boundaries, linked
   audio/video, safe paths, range bounds, overlay gaps, unsupported operation
   rejection, duplicate IDs and reproducible outputs. Render the seven existing
   JSX components; test alpha, full text, five statistics pages and fade endpoints.
2. **Synthetic host test:** read-only connection and version; new scratch
   project; import a short CFR test pattern with linked audio and a cut; read
   back exact frame ranges/timebase; export/reimport XML; inspect alpha overlay
   and all actual composition boundary frames. Save, close and reopen the project.
3. **Native graphics:** generate/import representative MOGRTs; inspect exposed
   property names/types; change names, scores, server and Chinese serve text;
   read back values and duration. Check two consecutive states for no flashing,
   and confirm speed appears strictly after verified contact. Test font fallback
   and high-DPI text, then save/reopen/export. Native variants remain provisional
   until these checks pass.
4. **Real excerpt:** transfer the first two retained points from the supplied
   project (including a double fault), a corrected point, a later point, a review
   case with continuous R/P and all five statistics pages. Normalize only needed
   source windows if required. Compare source PTS, final frame count, cuts,
   visible scores, overlay entry/exit, freeze/background and audio against the
   project. A rendered 60 fps reference must be mapped by time, not frame number.
5. **Full transfer:** only after the preceding gates pass, transfer all retained
   ranges; require no unintended base-track gaps, matched linked audio ranges,
   exact overlay manifest coverage and no offline media. Export a watchable
   result, sample all state classes and listen across modified cuts. Report the
   actual checked scope separately from owner acceptance of the look and sound.

Any timeout with an unknown mutation result stops dependent commands. Inspect
the project before retrying; never blindly repeat a timeline insertion. An
installed bridge, static code test and live host qualification are separate gates.

## Architecture implementation plan

Keep a short entrypoint route, an environment-selection contract, Premiere-only
execution guidance and a graphics-adapter contract. Add bounded deterministic
helpers for FCP7 interchange and canonical overlay rendering. Preserve the seven
canonical JSX files and all review-state semantics. Native templates should be
versioned adapters with declared editable properties, not replacements for the
canonical templates. Do not hard-code this test's players, media paths or IDs.

Repository upgrades, account Skill synchronization, agent installation and GitHub
publication are distinct operations. This task prepares and commits repository
changes; account publication is not implied by a local package upgrade.
