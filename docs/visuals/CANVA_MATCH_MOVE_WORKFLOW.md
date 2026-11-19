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
- The specific Canva path contains four cubic Bézier commands. Do not describe this Canva edit as a ten-segment path. The separate PowerPoint custom-mask implementation has its own path-topology checks.
- Page 1 has not passed Canva-render visual QA. The connector returned a signed thumbnail URL, but the available browser/download/runtime routes could not retrieve its image bytes. A local reconstruction was generated from the returned path plus the original asset for geometry inspection only: CANVA_PAGE1_MASK_LOCAL_RECONSTRUCTION.png, SHA-256 61701acc687bcbc6d17285ba62f94ec49c5bd53a0d9a57373eddc78e53eb69ff. It is not a Canva render and cannot establish Canva rendering parity.
- Read-back of pages 2–5 confirms all five pages remain 1920×1080 and use the same image media ID. Their hero object locator IDs differ, so shared asset identity is not proof of Match & Move object continuity. Pages 2–5 were not edited in this transaction.
- The source PPTX fixture's page 4 was rendered individually through LibreOffice and displays the full image correctly. The thin horizontal mark in the earlier contact sheet was a contact-sheet composition artifact, not a page-4 PPTX rendering defect.
- Canva Match & Move remains NOT_SET; playback remains NOT_VERIFIED. The connected Canva edit surface has no page-transition setter. The editing transaction remains open and unsaved; no commit was made.
- GitHub Actions run #199 (44553324904) is still in progress on head 13e4519c6be0454662c846a79977d43dd3a6401a: the Morph dataset audit passed and five of six test matrix jobs passed. The remaining Ubuntu/Python 3.10 job was still in the LibreOffice installation step at the latest poll. Do not claim full CI success until that job completes.
- PR #3 remains open, Draft and unmerged. No changes were made to main, the P0–P9 phase ledger, or research acceptance state.
