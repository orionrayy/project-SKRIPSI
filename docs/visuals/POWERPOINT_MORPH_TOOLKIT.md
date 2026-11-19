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

The patcher writes the PowerPoint 2015 Morph element in Markup Compatibility AlternateContent and includes a Fade fallback. The Morph Choice uses `Requires="p159"`, with the `p159` namespace declared on `mc:Choice`. When exact duration is written with the PowerPoint 2010 extension attribute `p14:dur`, its `p14` namespace is declared locally on the Morph `<p:transition>` element; `p14` is not added to the Choice's `Requires` list by this writer. The inspector validates the generated namespace scope, Morph option, duration and fallback. It supports a 1–30,000 ms duration. The inspector also checks the slide child order: the Morph AlternateContent block must follow p:cSld and, when present, p:clrMapOvr. The patch is written atomically and can be run more than once without accumulating duplicate transition blocks.

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

There are two different OOXML constructions and they must not be treated as equivalent for Morph authoring:

- p:pic with p:spPr/a:custGeom keeps an image as a native picture object and supports an editable custom clipping path. Use this for static picture masks and picture editing. Do not assume PowerPoint Morph will interpolate this picture-specific custom path merely because its XML is valid.
- p:sp with p:spPr/a:custGeom and p:spPr/a:blipFill keeps the image as a replaceable picture fill inside a native freeform shape. The freeform itself is the Morph-matched object. Prefer this form for Morph experiments involving a changing picture mask.

~~~python
from pptx.enum.shapes import MSO_SHAPE
from project_skripsi.pptx.geometry import (
    set_shape_custom_path,
    set_shape_picture_fill,
    tag_morph_object,
)

mask = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
set_shape_custom_path(mask, [
    ('move', 0.50, 0.02),
    ('cubic', 0.78, 0.02, 0.98, 0.22, 0.98, 0.50),
    ('cubic', 0.98, 0.78, 0.78, 0.98, 0.50, 0.98),
    ('cubic', 0.22, 0.98, 0.02, 0.78, 0.02, 0.50),
    ('cubic', 0.02, 0.22, 0.22, 0.02, 0.50, 0.02),
])
set_shape_picture_fill(mask, 'landscape.jpg')
tag_morph_object(mask, 'hero-photo-mask')
~~~

The current picture-fill helper stretches the image to the shape bounding rectangle. Prepare a crop/focal composition before inserting the fill when required. The shape remains native and editable; its closed path can use line, quadratic Bezier or cubic Bezier segments with coordinates normalized to the shape bounds.

For every adjacent Morph keyframe, keep object type (p:sp), unique forced name, number/order of edit points and winding direction consistent. Move corresponding control points gradually. Microsoft states that custom freeform shapes need roughly corresponding edit-point counts/positions and the same drawing orientation. This is an authoring constraint, not proof that a specific PowerPoint build interpolates a particular path correctly; playback must be checked in PowerPoint.

The five-slide reproducible example uses one native p:sp shape with an image fill per slide, identical forced object names, ten cubic Bezier segments per keyframe, and visibly varying position/size bounds. The regression test verifies that all five serialized geometries are genuinely different and that the shape bounds vary across keyframes, not merely that the paths have the same number of segments. LibreOffice rendering checks static endpoints only; Microsoft PowerPoint playback remains a manual acceptance gate.

A native picture with a custom clipping path can still be authored using set_picture_freeform_geometry() or set_picture_custom_path(). These remain picture-geometry utilities and should not be presented as verified custom-shape Morph playback.

## Canva transition handoff

PowerPoint Morph (`p159:morph`) and Canva Match & Move are separate transition systems. A PPTX import is a conversion to Canva design pages, not a promise that native PowerPoint transition metadata is translated into Canva page transitions. The user tested the custom-mask PPTX import in Canva and reported that no Morph/Match & Move motion appeared. Therefore the current PPTX artifact is **not accepted as a Canva animation deliverable**, regardless of its native PowerPoint Morph XML.

For a Canva-native result, build the page sequence in Canva as keyframes: duplicate the source page, keep the corresponding elements through the duplicate, alter their positions/sizes/appearance, then select the transition control between each pair of pages and explicitly choose **Match & Move**. Preview the result in Canva. Do not assume independently imported same-named PPTX objects retain Canva's internal element identity after conversion. Do not use Dissolve as a substitute.

The connected Canva operations available to this toolkit can search/read designs, import or edit page content, and inspect page previews, but they do not expose a page-transition setter. The integration therefore cannot currently apply Match & Move or verify its playback automatically. Unless a Canva transition-capable operation becomes available, transition selection and preview remain a user-side acceptance step. Do not create a duplicate Canva design unless the target design has been identified and a copy is explicitly wanted.

Official Canva guides:
- PowerPoint import: https://www.canva.com/help/powerpoint-import/
- Page transitions: https://www.canva.com/help/page-transitions/
- Match & Move workflow: https://www.canva.com/design-school/resources/how-to-create-animations-with-match-and-move/

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


## Reproducible custom-mask Morph example

The repository includes a self-contained example generator:

~~~bash
python examples/pptx/custom_picture_mask_morph_demo.py /tmp/custom-mask-morph.pptx --duration-ms 1000
~~~

The current generator creates five native freeform shapes (`p:sp`) filled with a replaceable image relationship (`a:blipFill`). The Morph-matched object is the freeform shape named `!!hero-photo-mask`, not a `p:pic` element. Each keyframe preserves one move command, ten cubic Bezier segments, path order and winding direction while changing the corresponding control points. The shape's position and bounding size also vary across keyframes so that both silhouette deformation and object movement/scale are represented. Native `byObject` Morph is applied to destination slides 2–5.

The companion regression test checks ZIP CRC, active slide order, Morph placement, the native shape/image-fill structure, ten-segment path topology, distinct serialized geometry on all five slides, and changing shape transforms. The Morph AlternateContent wrapper must follow `p:cSld` and `p:clrMapOvr` in the slide-child sequence. These checks establish package structure and distinct static endpoints, not Microsoft Morph playback. PowerPoint Desktop playback remains a separate manual acceptance gate.
