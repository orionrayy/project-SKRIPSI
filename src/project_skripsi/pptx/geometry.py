"""Native PowerPoint geometry helpers (requires the optional slides extra)."""
from __future__ import annotations

import math
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
def _normalized_point(point, *, index: int) -> tuple[float, float]:
    """Validate one point expressed in normalized picture coordinates."""
    if not isinstance(point, (tuple, list)) or len(point) != 2:
        raise ValueError(f"point {index} must contain exactly two coordinates")
    x, y = point
    if isinstance(x, bool) or isinstance(y, bool):
        raise ValueError(f"point {index} coordinates must be finite numbers")
    try:
        x_value, y_value = float(x), float(y)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"point {index} coordinates must be finite numbers") from exc
    if not math.isfinite(x_value) or not math.isfinite(y_value):
        raise ValueError(f"point {index} coordinates must be finite numbers")
    if not (0.0 <= x_value <= 1.0 and 0.0 <= y_value <= 1.0):
        raise ValueError(f"point {index} must be within normalized picture bounds [0, 1]")
    return x_value, y_value


def _picture_geometry_target(picture):
    """Return the shape-properties element and geometry node for a native picture."""
    element = getattr(picture, "_element", None)
    if element is None or not element.tag.endswith("}pic"):
        raise TypeError("picture must be a python-pptx Picture shape")
    sp_pr = getattr(element, "spPr", None)
    if sp_pr is None:
        raise TypeError("picture must contain DrawingML shape properties")
    old_geometry = sp_pr.prstGeom
    if old_geometry is None:
        old_geometry = sp_pr.custGeom
    if old_geometry is None:
        raise TypeError("picture has no preset or custom geometry to replace")
    return sp_pr, old_geometry


def set_picture_custom_path(
    picture,
    commands: Iterable[tuple],
    *,
    coordinate_scale: int = 21600,
):
    """Clip a native picture to a closed custom path with line and Bezier segments.

    Commands use normalized picture coordinates and this tuple grammar:
    - ("move", x, y): exactly one, and it must be first.
    - ("line", x, y): straight segment endpoint.
    - ("quad", cx, cy, x, y): quadratic control point and endpoint.
    - ("cubic", c1x, c1y, c2x, c2y, x, y): two cubic controls and endpoint.

    The path is automatically closed. The photo remains an editable p:pic
    object and keeps its existing image relationship and picture crop.
    """
    try:
        from pptx.oxml.xmlchemy import OxmlElement
    except ImportError as exc:
        raise RuntimeError("Install the optional extra with pip install project-skripsi-engine[slides]") from exc

    if isinstance(coordinate_scale, bool) or not isinstance(coordinate_scale, int) or coordinate_scale < 2:
        raise ValueError("coordinate_scale must be an integer >= 2")

    arity = {"move": 2, "line": 2, "quad": 4, "cubic": 6}
    normalized_commands: list[tuple[str, tuple[tuple[float, float], ...]]] = []
    for index, command in enumerate(commands):
        if not isinstance(command, (tuple, list)) or not command:
            raise ValueError(f"command {index} must be a non-empty tuple or list")
        kind = command[0]
        if not isinstance(kind, str) or kind.lower() not in arity:
            raise ValueError(f"command {index} must be move, line, quad, or cubic")
        kind = kind.lower()
        if len(command) != arity[kind] + 1:
            raise ValueError(f"{kind} command {index} requires {arity[kind]} coordinates")
        values = [
            _normalized_point(command[offset:offset + 2], index=index)
            for offset in range(1, len(command), 2)
        ]
        if index == 0 and kind != "move":
            raise ValueError("the first custom-path command must be move")
        if index > 0 and kind == "move":
            raise ValueError("a custom picture path must contain exactly one move command")
        normalized_commands.append((kind, tuple(values)))

    if len(normalized_commands) < 3:
        raise ValueError("a closed custom picture path requires move plus at least two segments")
    anchors = [normalized_commands[0][1][-1]] + [
        entry[1][-1] for entry in normalized_commands[1:]
    ]
    if len(set(anchors)) < 3:
        raise ValueError("a closed custom picture path requires at least three distinct anchor points")

    sp_pr, old_geometry = _picture_geometry_target(picture)
    custom_geometry = OxmlElement("a:custGeom")
    for tag in ("a:avLst", "a:gdLst", "a:ahLst", "a:cxnLst"):
        custom_geometry.append(OxmlElement(tag))
    rect = OxmlElement("a:rect")
    rect.set("l", "0")
    rect.set("t", "0")
    rect.set("r", str(coordinate_scale))
    rect.set("b", str(coordinate_scale))
    custom_geometry.append(rect)

    path_list = OxmlElement("a:pathLst")
    path = OxmlElement("a:path")
    path.set("w", str(coordinate_scale))
    path.set("h", str(coordinate_scale))
    path.set("fill", "norm")
    path.set("stroke", "0")
    path.set("extrusionOk", "0")

    command_tags = {
        "move": "a:moveTo",
        "line": "a:lnTo",
        "quad": "a:quadBezTo",
        "cubic": "a:cubicBezTo",
    }
    for kind, coordinates in normalized_commands:
        node = OxmlElement(command_tags[kind])
        for x_value, y_value in coordinates:
            point = OxmlElement("a:pt")
            point.set("x", str(round(x_value * coordinate_scale)))
            point.set("y", str(round(y_value * coordinate_scale)))
            node.append(point)
        path.append(node)
    path.append(OxmlElement("a:close"))
    path_list.append(path)
    custom_geometry.append(path_list)

    sp_pr.replace(old_geometry, custom_geometry)
    return picture


def set_picture_freeform_geometry(
    picture,
    points: Iterable[tuple[float, float]],
    *,
    coordinate_scale: int = 21600,
):
    """Clip a replaceable picture to a custom closed polygon in normalized coordinates.

    The image remains a native p:pic shape with its original relationship and crop.
    For Morph, retain vertex count/order and path winding across adjacent keyframes.
    Use set_picture_custom_path for quadratic or cubic curves.
    """
    raw_points = list(points)
    normalized = [
        _normalized_point(point, index=index) for index, point in enumerate(raw_points)
    ]
    compact: list[tuple[float, float]] = []
    for point in normalized:
        if not compact or point != compact[-1]:
            compact.append(point)
    if len(compact) > 1 and compact[-1] == compact[0]:
        compact.pop()
    if len(set(compact)) < 3:
        raise ValueError("a closed picture freeform requires at least three distinct points")

    commands = [("move", *compact[0])]
    commands.extend(("line", *point) for point in compact[1:])
    return set_picture_custom_path(picture, commands, coordinate_scale=coordinate_scale)
