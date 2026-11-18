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
