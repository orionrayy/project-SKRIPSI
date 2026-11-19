# PowerPoint Morph and Visual Geometry Toolkit

## Purpose

The source videos demonstrate five recurring visual techniques: freeform map/cutout composition, curved image galleries, circular image reveals, segmented rings, and brush-stroke photo masks. This toolkit adds reusable structural Morph patching and editable vector/picture helpers to Project-SKRIPSI without changing research-phase governance or adding a mandatory dependency.

Two layers are available:

- Structural Morph patching and inspection use only the Python standard library.
- Native freeform and picture-geometry authoring uses the optional slides extra based on python-pptx.

The demonstration presentation is a separate local artifact. The supplied reference videos, frame captures, and demo imagery are not included in the public repository.

## Install and run

~~~bash
python -m pip install -e '.[slides]'
project-skripsi-pptx inspect presentation.pptx
project-skripsi-pptx apply presentation.pptx --slides 5,7,9 --duration-ms 950 --option byObject
~~~

Slide numbers are one-based displayed order, resolved using the presentation slide list and relationship IDs. A numeric slide-part fallback is used only when a usable slide list is absent.

Supported Morph options are byObject, byWord, and byChar. Morph is attached to the destination slide. For deterministic object matching, reuse an identical, unique name prefixed with two exclamation marks on both slides, for example !!hero-image or !!map-outline. A target name with no preceding object match and duplicate names on the same slide are reported as errors. The source and destination object must actually differ in geometry or formatting for motion to be visible; writing a Morph transition alone does not create motion.

The patcher writes the PowerPoint 2015 Morph element in Markup Compatibility AlternateContent and includes a Fade fallback. The Morph Choice uses `Requires="p159"`, with the `p159` namespace declared on `mc:Choice`. When exact duration is written with the PowerPoint 2010 extension attribute `p14:dur`, its `p14` namespace is declared locally on the Morph `<p:transition>` element; `p14` is not added to the Choice's `Requires` list by this writer. The inspector validates the generated namespace scope, Morph option, duration and fallback. It supports a 1–30,000 ms duration. The patch is written atomically and can be run more than once without accumulating duplicate transition blocks.

## Matching grouped and complex objects

Automatic `byObject` matching can produce an incomplete result when a visual object is represented by a group or its geometry changes substantially between slides. For an object that must match predictably, give the corresponding source and destination shapes the same unique name prefixed by `!!`, such as `!!large-ball`. Keep the object type consistent, reuse that exact name on every adjacent keyframe, and do not assign the same forced name to multiple objects on one slide. The forced name belongs to the PowerPoint shape being matched; for a grouped object, first test the group shape itself. If group-level matching still fails, a separate diagnostic can force-match the nested child shape while leaving the parent group name unchanged. Do not assume both levels must be tagged. For freeform shapes with edit points, Microsoft recommends roughly corresponding point counts and positions, and the same drawing orientation (clockwise or counter-clockwise). Large changes to the freeform path topology can prevent a clean geometric morph.

For diagnosis, compare two copies of the same presentation: one using the original shape names and another with only the failing object's group-level name forced across the slide sequence. Keep all other group membership, child shapes, geometry and transitions identical. Preview both in Microsoft PowerPoint. A structural XML check or LibreOffice render cannot determine which matching strategy actually interpolates in PowerPoint.

## Python API

~~~python
from project_skripsi.pptx.morph import apply_morph, inspect_deck

apply_morph('draft.pptx', [5, 7, 9], duration_ms=950, option='byObject')
report = inspect_deck('draft.pptx')
if not report['ok']:
    raise RuntimeError(report['errors'])
~~~

Native editable shape helper example (requires the slides extra):

~~~python
from project_skripsi.pptx.geometry import add_freeform_shape, set_picture_geometry

land = add_freeform_shape(
    slide,
    [(1.0, 1.0), (2.5, 0.7), (3.1, 1.8), (2.3, 2.7), (1.1, 2.1)],
    name='map-landmass', fill='245E59', line='4C9E8E',
)
photo = slide.shapes.add_picture('landscape.jpg', left, top, width, height)
set_picture_geometry(photo, 'ellipse')
~~~

A freeform path and its nodes remain native PowerPoint vector geometry. An elliptical picture crop remains a picture object with a preset DrawingML geometry; the photograph is not flattened into a screenshot.


## Picture masks with custom freeform geometry

set_picture_freeform_geometry() applies a closed polygon directly to a native PowerPoint picture. Unlike placing a freeform above a rectangular photo, this changes the picture's own DrawingML a:custGeom; its p:pic identity, replaceable image relationship and picture crop remain intact. Coordinates are normalized to the picture bounds, where (0, 0) is top-left and (1, 1) is bottom-right.

~~~python
from project_skripsi.pptx.geometry import set_picture_freeform_geometry, tag_morph_object

photo = slide.shapes.add_picture('map-photo.jpg', left, top, width, height)
set_picture_freeform_geometry(
    photo,
    [(0.50, 0.02), (0.96, 0.18), (0.88, 0.76), (0.56, 0.98), (0.12, 0.82), (0.03, 0.34)],
)
tag_morph_object(photo, 'map-photo-cutout')
~~~

For smooth brush contours and curved apertures, use set_picture_custom_path() with native quadratic or cubic Bezier commands. Each path starts with one move and ends closed automatically. line uses an endpoint; quad uses a control point and endpoint; cubic uses two control points and an endpoint. All coordinate pairs are normalized to the picture bounds.

~~~python
from project_skripsi.pptx.geometry import set_picture_custom_path

set_picture_custom_path(photo, [
    ('move', 0.50, 0.02),
    ('cubic', 0.78, 0.02, 0.98, 0.22, 0.98, 0.50),
    ('cubic', 0.98, 0.78, 0.78, 0.98, 0.50, 0.98),
    ('cubic', 0.22, 0.98, 0.02, 0.78, 0.02, 0.50),
    ('cubic', 0.02, 0.22, 0.22, 0.02, 0.50, 0.02),
])
~~~

Use the polygon helper for map boundaries, shards, sectors and irregular cutouts. Use custom Bezier paths where visibly smooth edges matter. The helper rejects malformed commands, non-finite/out-of-range coordinates, missing or duplicate move commands, and paths with fewer than three distinct anchors. It does not rasterize the image or synthesize a brush texture; the path only defines the mask contour.

For a Morph sequence, keep picture object type, forced name, number/order of path segments, corresponding control points, and winding direction consistent on adjacent slides. Change the control-point coordinates gradually between keyframes. This is a structural authoring constraint, not a guarantee that every PowerPoint build will interpolate the custom picture geometry as intended; preview in Microsoft PowerPoint Desktop.

A local interoperability smoke test creates a picture with a cubic custom mask, saves and reloads the PPTX, checks ZIP integrity, and renders the static slide endpoint through LibreOffice. That proves the package and static mask can be rendered in this environment; it does not verify native Morph playback.


## Merge Shapes and masks

The native PowerPoint Merge Shapes operations are Union, Combine, Fragment, Intersect, and Subtract. They are shape-editing operations, not a live editable history of a Boolean expression. Preserve untouched source geometry before merging when further adjustment may be required.

The segmented-ring and brush-mask examples use replaceable photo assets with alpha masks. Their labels, typography, picture frames, ring outlines, centre aperture and freeform map geometry can remain editable vector/text objects. The photo alpha mask itself is not represented as a live Merge Shapes operation.

## Validation gates

1. Verify PPTX ZIP CRC and required Office Open XML package parts.
2. Resolve the displayed slide order and ensure destination slides exist.
3. Check Morph option, duration and Fade fallback.
4. Check for duplicate forced names and unmatched Morph target objects.
5. Render every slide and inspect crops, clipping, contrast, typography and layout.
6. Open the deck in desktop Microsoft PowerPoint and preview every transition. LibreOffice rendering confirms that the package can be opened and rendered; it does not prove that Microsoft's Morph engine played the transition.
7. Export from PowerPoint and inspect the output before delivery.

## Official references and limits

- Microsoft Support: Use the Morph transition in PowerPoint — https://support.microsoft.com/en-us/powerpoint/training/use-the-morph-transition-in-powerpoint
- Microsoft Support: Morph transition tips and tricks — https://support.microsoft.com/en-gb/powerpoint/morph-transition-tips-and-tricks
- Microsoft Support: Combine and merge shapes — https://support.microsoft.com/en-us/powerpoint/draw-a-picture-by-combining-and-merging-shapes
- Microsoft Open Specifications: Morph option values — https://learn.microsoft.com/en-us/openspecs/office_standards/ms-pptx/22e711ee-35a7-42cb-b87c-1c277ec11070

The validator proves structural properties only. It cannot guarantee playback in every PowerPoint build, visual quality for every audience, or that a photo alpha mask is an editable Boolean shape. Microsoft PowerPoint playback and visual inspection remain required acceptance checks.

## Audited reference corpus

The free reference corpus, source/license notes, technique-to-video mapping and object-pair analysis are maintained in `docs/visuals/morph-dataset/`. The full index contains 54 unique native-Morph PPTX references; the priority A+B set contains 22 files.

Run `python scripts/verify_morph_reference_dataset.py` in CI to fetch and verify the 22 priority files. It validates original file size and SHA-256, ZIP CRC, active slide ordering, native `p159:morph` options, strict object name/type matches and geometry changes. Temporary PPTX binaries are deleted after verification; only the JSON audit report is retained.

Brush-stroke mask libraries that provide editable image masks but do not contain native Morph transitions must remain separately labelled as geometry references. Do not inflate the native-Morph dataset count with static mask templates. Microsoft PowerPoint Desktop playback remains a separate, manual acceptance gate.
