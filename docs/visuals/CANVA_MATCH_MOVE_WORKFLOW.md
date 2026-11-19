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
