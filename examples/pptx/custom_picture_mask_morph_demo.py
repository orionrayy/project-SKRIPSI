#!/usr/bin/env python3
"""Build a five-slide native freeform picture-fill Morph demo."""
from __future__ import annotations

import argparse
import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from project_skripsi.pptx.geometry import set_shape_custom_path, set_shape_picture_fill, tag_morph_object
from project_skripsi.pptx.morph import apply_morph, inspect_deck


def _landscape(path: Path) -> None:
    """Generate deterministic original landscape artwork without external assets."""
    width, height = 1800, 1080
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        fy = y / height
        for x in range(width):
            fx = x / width
            glow = max(0.0, 1.0 - math.sqrt(((fx - 0.73) / 0.46) ** 2 + ((fy - 0.30) / 0.55) ** 2))
            pixels[x, y] = (
                int(8 + 28 * (1 - fy) + 82 * glow),
                int(22 + 48 * (1 - fy) + 58 * glow),
                int(48 + 82 * (1 - fy) + 22 * glow),
            )
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse((1160, 130, 1570, 540), fill=(255, 174, 108, 225), outline=(255, 220, 185, 185), width=10)
    draw.ellipse((1190, 160, 1540, 510), fill=(255, 198, 145, 65))
    for i in range(12):
        x, y = 160 + i * 155, 180 + (i % 3) * 48
        draw.arc((x, y, x + 250, y + 100), 190, 350, fill=(176, 205, 227, 65), width=7)
    image = Image.alpha_composite(image.convert("RGBA"), layer)
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [(0, 690), (150, 590), (290, 650), (470, 480), (640, 655), (800, 520),
         (980, 670), (1130, 470), (1360, 670), (1550, 520), (1800, 700),
         (1800, 1080), (0, 1080)],
        fill=(24, 56, 79, 255),
    )
    draw.polygon(
        [(0, 830), (220, 730), (420, 790), (650, 680), (840, 820), (1070, 690),
         (1270, 840), (1480, 710), (1800, 850), (1800, 1080), (0, 1080)],
        fill=(15, 42, 57, 255),
    )
    draw.polygon(
        [(800, 1080), (940, 980), (1010, 890), (1030, 820), (1090, 770),
         (1140, 800), (1110, 870), (1070, 945), (1030, 1080)],
        fill=(47, 113, 137, 255),
    )
    draw.line([(1010, 1080), (1050, 980), (1070, 900), (1100, 820)], fill=(159, 210, 209, 180), width=10)
    for i in range(90):
        x, y = (i * 193) % width, 800 + (i * 71) % 260
        draw.line((x, y, x + 35 + (i % 5) * 12, y - 2), fill=(130, 174, 173, 28), width=2)
    image.convert("RGB").filter(ImageFilter.GaussianBlur(0.35)).save(path, quality=94)


def _blob(cx: float, cy: float, rx: float, ry: float, radii: list[float], phase: float):
    return [
        (
            cx + rx * radius * math.cos(-math.pi / 2 + i * 2 * math.pi / len(radii) + phase),
            cy + ry * radius * math.sin(-math.pi / 2 + i * 2 * math.pi / len(radii) + phase),
        )
        for i, radius in enumerate(radii)
    ]


def _commands(anchors: list[tuple[float, float]]):
    """Convert a closed Catmull-Rom loop into the same ten cubic segments."""
    result = [("move", *anchors[0])]
    count = len(anchors)
    for i in range(count):
        p0, p1 = anchors[(i - 1) % count], anchors[i]
        p2, p3 = anchors[(i + 1) % count], anchors[(i + 2) % count]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        c1 = tuple(min(0.98, max(0.02, v)) for v in c1)
        c2 = tuple(min(0.98, max(0.02, v)) for v in c2)
        result.append(("cubic", *c1, *c2, *p2))
    return result


def _keyframes():
    return [
        _blob(.50, .50, .36, .35, [.88, 1.02, .82, 1.00, .87, 1.06, .83, 1.00, .88, .95], -.10),
        _blob(.54, .49, .37, .34, [.72, .98, .90, 1.03, .85, .99, .92, 1.05, .70, .97], .10),
        _blob(.53, .50, .37, .32, [.70, 1.05, .82, 1.03, .68, .96, .78, 1.06, .75, 1.02], .28),
        _blob(.49, .52, .36, .36, [.65, 1.08, .77, 1.12, .68, 1.05, .72, 1.09, .66, 1.02], -.18),
        _blob(.50, .50, .35, .35, [.94, .99, .95, 1.01, .96, .99, .95, 1.02, .95, 1.00], 0.0),
    ]


def build_demo(output: str | Path, *, duration_ms: int = 1000) -> dict:
    """Write the deck, apply native Morph to slides 2–5, and inspect the result."""
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    labels = ["01  ORGANIC CUTOUT", "02  OFFSET / STRETCH", "03  FLOWING SILHOUETTE",
              "04  BRUSH-LIKE EDGE", "05  APERTURE SETTLE"]
    with tempfile.TemporaryDirectory(prefix="project-skripsi-mask-demo-") as temporary:
        image_path = Path(temporary) / "synthetic-landscape.png"
        _landscape(image_path)
        prs = Presentation()
        prs.slide_width, prs.slide_height = Inches(13.333333), Inches(7.5)
        bg, white, muted, accent = (
            RGBColor(8, 16, 27), RGBColor(242, 246, 250),
            RGBColor(151, 170, 191), RGBColor(83, 180, 199),
        )
        for index, anchors in enumerate(_keyframes()):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            slide.background.fill.solid()
            slide.background.fill.fore_color.rgb = bg
            eyebrow = slide.shapes.add_textbox(Inches(.72), Inches(.40), Inches(6.5), Inches(.25))
            p = eyebrow.text_frame.paragraphs[0]
            p.text, p.font.name, p.font.size = "PROJECT-SKRIPSI  /  POWERPOINT MORPH LAB", "Aptos", Pt(9)
            p.font.bold, p.font.color.rgb = True, accent
            title = slide.shapes.add_textbox(Inches(.72), Inches(.83), Inches(8.8), Inches(.54))
            p = title.text_frame.paragraphs[0]
            p.text, p.font.name, p.font.size = "Native freeform shape + image fill → Morph keyframes", "Aptos Display", Pt(25)
            p.font.bold, p.font.color.rgb = True, white
            divider = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(.72), Inches(1.49), Inches(11.9), Inches(.012))
            divider.fill.solid()
            divider.fill.fore_color.rgb = RGBColor(42, 59, 78)
            divider.line.fill.background()
            mask = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2.05), Inches(1.77), Inches(9.23), Inches(5.00))
            set_shape_custom_path(mask, _commands(anchors))
            set_shape_picture_fill(mask, image_path)
            tag_morph_object(mask, "hero-photo-mask")
            footer = slide.shapes.add_textbox(Inches(.76), Inches(6.93), Inches(6.8), Inches(.25))
            p = footer.text_frame.paragraphs[0]
            p.text, p.font.name, p.font.size = labels[index], "Aptos", Pt(9)
            p.font.bold, p.font.color.rgb = True, muted
            hint = slide.shapes.add_textbox(Inches(8.05), Inches(6.93), Inches(4.45), Inches(.25))
            p = hint.text_frame.paragraphs[0]
            p.alignment, p.text = PP_ALIGN.RIGHT, "!!hero-photo-mask   •   p:sp + image fill   •   byObject"
            p.font.name, p.font.size, p.font.color.rgb = "Aptos", Pt(9), muted
        prs.save(output)

    apply_morph(output, [2, 3, 4, 5], duration_ms=duration_ms, option="byObject")
    report = inspect_deck(output)
    if not report.get("ok") or report.get("morph_slides") != [2, 3, 4, 5]:
        raise RuntimeError(f"Generated PPTX failed Morph inspection: {report.get('errors')}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Output .pptx path")
    parser.add_argument("--duration-ms", type=int, default=1000)
    args = parser.parse_args(argv)
    report = build_demo(args.output, duration_ms=args.duration_ms)
    print(f"PASS: {args.output} ({report['slide_count']} slides; Morph on {report['morph_slides']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
