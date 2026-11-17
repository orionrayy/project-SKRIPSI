"""Native PowerPoint geometry helpers (requires the optional slides extra)."""
from __future__ import annotations

import re
from typing import Iterable


def tag_morph_object(shape, logical_name: str) -> str:
    """Assign the !! name used to force Morph matching across adjacent slides.

    A logical name must be unique on each slide and must be reused exactly on
    the corresponding object in the next slide.
    """
    if not isinstance(logical_name, str) or not logical_name.strip():
        raise ValueError("logical_name must be a non-empty string")
    raw_name = logical_name.strip()
    if raw_name.startswith("!!"):
        raw_name = raw_name[2:]
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw_name).strip("-")
    if not clean:
        raise ValueError("logical_name has no usable characters")
    object_name = f"!!{clean}"
    shape.name = object_name
    return object_name


def add_freeform_shape(
    slide,
    points: Iterable[tuple[float, float]],
    *,
    name: str,
    fill: str | None = None,
    line: str | None = None,
    line_width_pt: float = 1.0,
    close: bool = True,
):
    """Add an editable freeform polygon/path using slide-relative inch coordinates."""
    try:
        from pptx.dml.color import RGBColor
        from pptx.util import Inches, Pt
    except ImportError as exc:
        raise RuntimeError("Install the optional extra with pip install project-skripsi-engine[slides]") from exc

    vertices = list(points)
    if len(vertices) < (3 if close else 2):
        raise ValueError("A closed freeform requires 3 points; an open path requires 2")
    coords = [(int(Inches(float(x))), int(Inches(float(y)))) for x, y in vertices]
    builder = slide.shapes.build_freeform(coords[0][0], coords[0][1], scale=1.0)
    builder.add_line_segments(coords[1:], close=close)
    shape = builder.convert_to_shape()
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(fill.lstrip("#"))
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = RGBColor.from_string(line.lstrip("#"))
        shape.line.width = Pt(line_width_pt)
    tag_morph_object(shape, name)
    return shape


def set_picture_geometry(picture, preset: str = "ellipse"):
    """Apply a native preset crop geometry to an existing PowerPoint picture.

    This changes the picture's DrawingML geometry; it does not rasterize the
    photograph. The picture remains an independent replaceable picture object.
    """
    allowed = {"ellipse", "rect", "roundRect", "triangle", "hexagon", "diamond"}
    if preset not in allowed:
        raise ValueError(f"preset must be one of {sorted(allowed)}")
    element = getattr(picture, "_element", None)
    sp_pr = getattr(element, "spPr", None)
    if sp_pr is None or sp_pr.prstGeom is None:
        raise TypeError("picture must be a python-pptx Picture shape")
    sp_pr.prstGeom.set("prst", preset)
    return picture
