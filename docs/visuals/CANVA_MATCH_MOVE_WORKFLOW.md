# Canva Match & Move Compatibility Workflow

## Purpose and boundary

PowerPoint Morph and Canva Match & Move are different transition engines. PowerPoint OOXML `p159:morph` is not a Canva transition command. Importing PPTX into Canva converts slide content into Canva pages; the presence of Morph XML in the source is not proof that Canva has created Match & Move transitions.

The user imported the custom-mask PowerPoint Morph deck into Canva and reported no animation. Treat that PPTX-to-Canva animation path as FAILED.

## Current Canva keyframe fixture

An editable five-page keyframe fixture was created directly in the connected Canva account:

- Design ID: `DAHbXq0gvl0`
- Edit URL: https://www.canva.com/d/B57HXK3Xjxry66_
- View URL: https://www.canva.com/d/hXM7cyKsey6Ds-y
- Page count: 5
- Page dimensions: 1920 × 1080
- Repeated picture media ID: `MAHbXkHhMmw`
- Source PPTX: `CANVA_MATCH_MOVE_KEYFRAME_TEST.pptx`
- Source PPTX SHA-256: `d6e55dd5aa21af85466dc4662a973c3ea94c1b4e5e94221370a108e76b84905b`

The same image asset is reused on all five pages. Canva read-back confirms editable pages and image-filled shapes whose positions, dimensions and rotations differ. However, each page has a different element locator ID. The common media ID proves asset reuse only; it does not establish that Canva's transition matcher treats the separate imported elements as one continuous object.

**Status:** keyframe import PASS; editable-content read-back PASS; Match & Move selection NOT_SET; Match & Move playback NOT_VERIFIED. The fixture contains neither a PowerPoint Morph transition nor a Canva Dissolve substitute.

## Canva-native transition procedure

For reliable object continuity, duplicate the source page inside Canva before changing the object. This follows the Canva Match & Move authoring workflow and avoids relying on separately imported PowerPoint elements to retain Canva identity.

1. Open the Canva design in the editor.
2. Select the hero picture on page 1 and duplicate the page.
3. On the duplicate, move, resize and rotate the duplicated hero picture. Do not delete it and insert a new asset.
4. Repeat duplicate-and-adjust to create subsequent keyframes.
5. In page thumbnails, hover between pages 1 and 2, choose **Add transition**, then select **Match & Move** explicitly.
6. Repeat for 2→3, 3→4 and 4→5. Do not choose Dissolve.
7. Preview every pair. Acceptance requires continuous movement/scale/rotation of the same hero element, not a crossfade or static page change.

Canva's official page-transition guide explains selecting the transition control between page thumbnails. Its Match & Move tutorial describes duplicating pages, changing the same elements, and applying Match & Move.

## Integration limitation

The connected Canva tools expose design search, import, page read-back, page listing and content/layout editing. They do not expose a page-transition setter. This integration can prepare and inspect keyframes but cannot apply Match & Move or certify playback automatically. Do not claim success until Match & Move is visibly selected and previewed in Canva.

## Official references

- Canva: Import PowerPoint presentations — https://www.canva.com/help/powerpoint-import/
- Canva: Use page transitions — https://www.canva.com/help/page-transitions/
- Canva Design School: Create animations with Match & Move — https://www.canva.com/design-school/resources/how-to-create-animations-with-match-and-move/


## Draft mask transaction and visual QA — 2026-11-19

- Continued in the existing unsaved Canva editing transaction 2136354799700613472 for design DAHbXq0gvl0. Page 1's original image-filled shape was replaced with a closed cubic-Bezier freeform. The edit API returned applied_unverified; a subsequent transaction read-back confirms the shape path and the original shared image media ID MAHbXkHhMmw are present.
- The page-1 Canva path contains five cubic Bézier commands; pages 2–4 each contain four cubic commands after later draft edits. Page 5 remains rectangular. The resulting command-count mismatch is an unresolved topology-normalization issue. Do not describe this Canva edit as a ten-segment path. The separate PowerPoint custom-mask implementation has its own path-topology checks.
- Page 1 has not passed Canva-render visual QA. The connector returned a signed thumbnail URL, but the available browser/download/runtime routes could not retrieve its image bytes. A local reconstruction was generated from the returned path plus the original asset for geometry inspection only: CANVA_PAGE1_MASK_LOCAL_RECONSTRUCTION.png, SHA-256 61701acc687bcbc6d17285ba62f94ec49c5bd53a0d9a57373eddc78e53eb69ff. It is not a Canva render and cannot establish Canva rendering parity.
- Read-back of pages 2–5 confirms all five pages remain 1920×1080 and use the same image media ID. Their hero object locator IDs differ, so shared asset identity is not proof of Match & Move object continuity. Pages 2–5 were not edited in this transaction.
- The source PPTX fixture's page 4 was rendered individually through LibreOffice and displays the full image correctly. The thin horizontal mark in the earlier contact sheet was a contact-sheet composition artifact, not a page-4 PPTX rendering defect.
- Canva Match & Move remains NOT_SET; playback remains NOT_VERIFIED. The connected Canva edit surface has no page-transition setter. The editing transaction remains open and unsaved; no commit was made.
- GitHub Actions run #199 (44553324904) is still in progress on head 13e4519c6be0454662c846a79977d43dd3a6401a: the Morph dataset audit passed and five of six test matrix jobs passed. The remaining Ubuntu/Python 3.10 job was still in the LibreOffice installation step at the latest poll. Do not claim full CI success until that job completes.
- PR #3 remains open, Draft and unmerged. No changes were made to main, the P0–P9 phase ledger, or research acceptance state.


## Canva draft keyframe visual QA — 2026-11-19 (continued)

- Compared actual saved-before and unsaved-after Canva page thumbnails for pages 1–3 using the signed preview images returned by Canva. Page 1: the original rotated rectangular picture became an organic closed freeform clip; page 2: the picture became a tapered curved mask; page 3: the picture became a smooth elliptical aperture. The same hero image remains visible inside each mask and no large clipping/rendering defect was visible at thumbnail scale. These are static page-preview checks only, not animation checks.
- Page 4's leaf-like four-cubic Bezier replacement was applied and the returned structured document confirms the new path and retained shared media ID. Its after-thumbnail could not be visually inspected because the browser-preview service exhausted its available daily credits. Page 4 remains VISUAL_QA_PENDING; do not edit it again until its before/after thumbnail comparison is performed.
- Page 5 remains untouched and rectangular.
- Full draft read-back confirms all five hero shapes retain media ID MAHbXkHhMmw. Their page-scoped locator IDs are distinct. The path topology is currently inconsistent: page 1 has five cubic Bezier commands; pages 2–4 have four each; page 5 has no cubic commands (rectangular path). Normalize the number and order of path segments before treating this as a valid shape-interpolation sequence. Do not claim Morph or Match & Move from static thumbnails.
- Canva Match & Move remains NOT_SET; playback remains NOT_VERIFIED. The active editing transaction 2136354799700613472 remains open and unsaved. No save/commit action was taken.
- GitHub Actions run #200 (44560253741), for feature-branch commit d71081e0929a7fe72fdf715450d430729bd4549c, completed SUCCESS with 7/7 jobs: the Morph dataset audit and all six Ubuntu/Windows × Python 3.10–3.12 matrix jobs.
- PR #3 remains open, Draft and unmerged. No change was made to main or P0–P9 research governance/acceptance state.


## Canva keyframe rebuild checkpoint — 2026-11-20

- The prior unsaved transaction 2136354799700613472 expired. Read-back of the saved Canva design showed the original rectangular image fills on pages 1–5; the prior draft mask edits had not been committed and did not persist. The earlier page-1 to page-3 Canva thumbnail comparisons belong to that expired transaction and are not evidence for the rebuilt transaction below.
- Opened a fresh edit transaction 7733203254043950927 on design DAHbXq0gvl0 (edit link returned during this transaction: https://www.canva.com/d/5wmDvcy0yam1e1W). Rebuilt all five hero masks from the saved baseline.
- Current mask sequence: page 1 organic freeform; page 2 tapered curve; page 3 elliptical aperture; page 4 leaf aperture; page 5 brush-swash aperture. Each path is closed and has exactly four cubic Bezier commands in the same clockwise segment order.
- Canva read-back confirms all five paths are attached to image-filled shapes referencing the same media ID MAHbXkHhMmw. Their element locator IDs remain page-specific and distinct. Object positions, dimensions and rotations remain the original five keyframes.
- Local geometry audit sampled each cubic path at 1,001 parameter positions and confirmed all five path bounds lie within their respective viewBoxes. All five paths are closed and have four cubic segments. Local preview artifact: CANVA_FIVE_KEYFRAMES_LOCAL_QA.png, SHA-256 bb1312940010220c20a61cab76f129ecb0fe042ca97d01c855b5f827fc7f5950. Structured report: CANVA_FIVE_KEYFRAMES_GEOMETRY_QA.json, SHA-256 7ba4d23f0855cc764621310d51b496fbc00265c922ccfa5441e02ed3826550fb. Both files are local deliverables, not committed to the repository.
- The local preview is a geometry reconstruction from Canva read-back values and the shared source media. It is NOT a Canva-render capture. Current Canva thumbnail URLs could not be inspected through the available browser routes in this run; Canva renderer visual QA remains NOT_VERIFIED for the rebuilt transaction.
- Canva Match & Move remains NOT_SET and playback remains NOT_VERIFIED. The connected Canva editor API still exposes no page-transition setter. Do not substitute Dissolve or claim animation success.
- The active transaction remains OPEN_UNSAVED. No commit/save was made. Obtain a visual review and explicit approval before committing it.
- GitHub Actions run #201 (44562689875) for commit e854b39605aaf5022bd5ba887ea4cfe5e410f9ee completed SUCCESS with 7/7 jobs: Morph dataset audit plus all six Ubuntu/Windows × Python 3.10–3.12 matrix jobs.
- PR #3 remains open, Draft and unmerged. No change to main or P0–P9 research-governance/acceptance state.
