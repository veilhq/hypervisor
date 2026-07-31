"""Convert an SVG to ICO files (individual sizes + combined multi-size).

Rasterizes with PyMuPDF (MuPDF). MuPDF ignores CSS rules in <style> blocks,
so simple `.class { fill: #hex }` rules are inlined as presentation attributes
first — this is the pattern Illustrator/Figma SVG exports use.

Non-square artwork is scaled to fit and centered on a transparent square canvas
so the glyph isn't distorted.

Usage:
    python svg-to-ico.py <input.svg> [output_prefix] [--sizes 16,32,48]
"""
import io
import re
import sys
from pathlib import Path

import fitz
from PIL import Image

DEFAULT_SIZES = [16, 32, 48]
# Render at 4x the largest target for clean downsampling.
SUPERSAMPLE = 4


def inline_css_fills(svg_text: str) -> str:
    """Inline `.cls-N { fill: #hex }` rules as fill="" attributes.

    MuPDF doesn't apply CSS class selectors, so without this every path
    renders with the default black fill.
    """
    style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", svg_text, re.DOTALL)
    if not style_blocks:
        return svg_text

    rules: dict[str, dict[str, str]] = {}
    for block in style_blocks:
        for selector, body in re.findall(r"\.([\w-]+)\s*\{([^}]*)\}", block):
            props = {}
            for decl in body.split(";"):
                if ":" not in decl:
                    continue
                key, _, value = decl.partition(":")
                props[key.strip()] = value.strip()
            if props:
                rules.setdefault(selector, {}).update(props)

    if not rules:
        return svg_text

    def add_attrs(match: re.Match) -> str:
        tag = match.group(0)
        classes = match.group(1).split()
        props: dict[str, str] = {}
        for cls in classes:
            props.update(rules.get(cls, {}))
        if not props:
            return tag
        # Don't clobber an explicit presentation attribute already on the element
        # (a duplicate attribute is an XML syntax error).
        attrs = " ".join(
            f'{k}="{v}"'
            for k, v in props.items()
            if not re.search(rf"\b{re.escape(k)}\s*=", tag)
        )
        if not attrs:
            return tag
        # Insert just after the class="..." value so self-closing `/>` stays intact.
        idx = match.end(1) - match.start(0) + 1
        return tag[:idx] + " " + attrs + tag[idx:]

    return re.sub(r'<[\w:]+\b[^>]*\bclass="([^"]*)"[^>]*/?>', add_attrs, svg_text)


def render_square(svg_text: str, size: int) -> Image.Image:
    """Rasterize the SVG into a transparent square RGBA image of `size` px."""
    doc = fitz.open(stream=svg_text.encode("utf-8"), filetype="svg")
    page = doc[0]
    rect = page.rect

    target = size * SUPERSAMPLE
    scale = target / max(rect.width, rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=True)
    art = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
    doc.close()

    canvas = Image.new("RGBA", (target, target), (0, 0, 0, 0))
    canvas.paste(art, ((target - art.width) // 2, (target - art.height) // 2), art)
    return canvas.resize((size, size), Image.LANCZOS)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    if not args:
        print(__doc__)
        sys.exit(1)

    sizes = DEFAULT_SIZES
    for flag in flags:
        if flag.startswith("--sizes"):
            _, _, value = flag.partition("=")
            if not value and flag == "--sizes":
                print("error: use --sizes=16,32,48")
                sys.exit(1)
            sizes = sorted({int(s) for s in value.split(",") if s.strip()})

    src = Path(args[0])
    if not src.is_file():
        print(f"error: no such file: {src}")
        sys.exit(1)

    prefix = Path(args[1]) if len(args) > 1 else src.with_suffix("")

    svg_text = inline_css_fills(src.read_text(encoding="utf-8"))
    frames = {size: render_square(svg_text, size) for size in sizes}

    for size, img in frames.items():
        out = prefix.with_name(f"{prefix.name}-{size}.ico")
        img.save(out, format="ICO", sizes=[(size, size)])
        print(f"Saved: {out.name} ({out.stat().st_size / 1024:.1f} KB)")

    largest = frames[max(sizes)]
    combined = prefix.with_suffix(".ico")
    largest.save(combined, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Saved: {combined.name} ({combined.stat().st_size / 1024:.1f} KB) — combined {sizes}")


if __name__ == "__main__":
    main()
