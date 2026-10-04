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
UI import can be a manual setup/test step, but the delivered agent workflow uses
a terminal-accessible host bridge. XML generation alone
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
with previous state recorded. The earlier turn stopped when Computer Use was
stopped by Escape. In the new turn the permitted runtime became available and
was used to activate the panel and inspect/dismiss test-error dialogs.

Premiere 23.5.0 build 56 then connected. All timeline import, inspection,
automation, export, save and reopen operations used terminal requests. The
first activation needs an open project: Extensions is disabled on the empty
Home screen. A fresh agent can ask the user to create/open a blank scratch
project and activate the panel once; subsequent terminal launch uses that
machine's Premiere executable and the saved project path. No screenshot/click
capability is required by the distributed skill.

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

## Implemented and checked

- Explicit editor selection and independent graphics selection, including
  legacy CEP and newer UXP setup, prerequisites and version gates.
- A terminal-only, single-request stdio MCP client, exercised against the actual
  1.2.8 server and the installed 23.5.0.56 CEP host. Results retain full requests,
  responses and errors; no automatic mutation retries.
- A bounded FCP7 generator for same-rate CFR cuts, linked mono/stereo audio and
  full-canvas stills. It rejects unsupported effects/rates and retains pending
  host operations explicitly. Exact frame/tick and structural tests passed.
- Canonical RGBA rendering: 18 synthetic PNGs across seven components, all five
  statistics pages and seven fade-boundary samples. Measured alpha was zero at
  both fade endpoints, 255 on the plateau, and zero outside graphic bounds.
  The 11-row statistics page and speed label were visually inspected. A speed
  text line-box overflow warning was inspected: visible text was not cropped.
- Two real source excerpts normalized to 30 fps: 309 + 114 = 423 frames. Packet
  inspection of the source's first 70 seconds found both 1/60-second and
  11/600-second frame durations, confirming variable cadence in that window.
  Their XML and source-offset mapping were imported; original media was not
  changed. Twelve real-data graphics were rendered into ignored local test
  output, including five saved statistics pages.
- A provisional authoring-script generator for five native graphics. JavaScript
  syntax and field mappings are checked. AE's supported `-r` script entry was
  attempted, but a subscription/language installation error prevented execution.
  **No custom binary MOGRT was produced or qualified.** Rendered statistics and
  explanation overlays retain their canonical implementation.

The live ChatCut project changed while this investigation was running. A saved
serve-overlay data file also differed from the earlier live speed instance.
The test pack records this instead of silently choosing old data as current.
The real test freezes the prepared two-point schedule and saved panel data with
hashes; the speed label uses the earlier sampled live value and retains the
disagreement. This is a transfer fixture, not an assertion of current project
authority. A frame at the same two-second timestamp was also visually compared
with the user-provided rendered reference: footage state, layout and displayed
values match, with expected text-rendering differences. No ChatCut timeline,
review answers or source media was edited.

## v21 live evidence and fixes

| Check | Observed result |
|---|---|
| Windows media paths | Pr 23.5 misread `file:///C:/...` and opened Link Media. Matching Pr's exported `file://localhost/C%3a/...` resolved it; Chinese, spaces, `#` and `%` imported online. UNC/macOS remain untested in a host. |
| Exact synthetic cuts | 90 exported frames; source in/out and timeline boundaries matched integer ticks, including XML export/reimport. All 90 decoded frames matched source cuts plus the alpha overlay: maximum whole-frame mean absolute RGB error 1.34/255. |
| Stereo | Two ordinary mono tracks collapsed both tones to the center. Premiere's exploded Stereo XML grouping fixed it; 440 Hz left and 880 Hz right remained separated in the actual export. |
| Real fixture | 423 footage frames plus 5 × 240 statistics frames = 1,623 frames / 54.1 seconds at 30 fps. All media online, no base-track gaps, matched score/serve/speed boundary samples. |
| Native automation on rendered stats | Five opacity envelopes read back at 0/100/100/0; two source-time audio fades retained the measured 0 dB raw level. These are native Premiere properties on raster graphics, not editable native text. |
| SDR composition | Initial linear-color composition failed the PNG comparison at translucent fades. Setting the scratch sequence's `compositeLinearColor=false` reduced the maximum mean error across 40 statistics boundary/plateau samples to 1.60/255. This is a tested SDR choice, not an HDR default. |
| Audio | Exported PCM matched both source interiors with zero sample lag, unity gain and effectively perfect correlation; the statistics tail was silent. AAC output showed a 1,024-sample / 21.33 ms delay relative to PCM. No subjective listening claim. |
| Save/reopen | A slash-joined candidate Save As produced a file but later Save failed. `saveAs(new File(destination).fsName)` fixed the Windows path. Save, project close, terminal reopen and effect readback passed. Full Premiere process exit and terminal restart also restored the panel automatically. |
| Pr-authored MOGRT | The installed Basic Title imported, but returned no MGT component/text parameter through this legacy DOM. Import success does not establish terminal text editability. |
| AE-authored MOGRT | Both custom authoring and an installed AE-authored template were blocked by the local AE subscription/language error. No licensing settings were changed. |

The 1.2.8 bridge may report a missing bridge while a modal blocks the host, or
after closing the last project unloads CEP. An `export_frame` call also returned
an error before its PNG appeared. Inspect outcomes before retrying; record
partial mutation and independently validate output files. A terminal agent asks
the user to resolve a concrete blocking dialog when necessary. It must not
invent click capability or silently switch editors.

The skill now documents blank-project bootstrap, panel configuration, native
filesystem paths, stereo slot mapping, source-time keyframes, compositing,
factory encoder preset discovery, save/reopen and these failure modes. Adobe's
[legacy sample](https://github.com/Adobe-CEP/Samples/blob/master/PProPanel/jsx/PPRO/Premiere.jsx)
and [UXP changelog](https://developer.adobe.com/premiere-pro/uxp/changelog/) remain
the primary API references; newer-host claims do not inherit 23.5 test results.

**Remaining gates:** resolve AE's installation/licensing issue; produce and
qualify all five custom MOGRT types (Unicode fields, edit/readback, trimming,
save/reopen and typography); test the hybrid real excerpt, corrected/later and
continuous-review cases; listen across cuts; then perform full-match transfer.
Newer UXP requires its own installed host and verified terminal bridge. The
current rendered test fixture is useful evidence, not completion of the selected
hybrid workflow. Private media and detailed JSON evidence stay in ignored local
output; nothing was synchronized to the account Skill or published.
