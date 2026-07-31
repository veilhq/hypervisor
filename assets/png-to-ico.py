"""Convert a PNG to individual ICO files per size and a combined multi-size ICO."""
import sys
from PIL import Image

if len(sys.argv) < 2:
    print("Usage: python png-to-ico.py <input.png> [output_prefix]")
    sys.exit(1)

src = sys.argv[1]
prefix = sys.argv[2] if len(sys.argv) > 2 else src.rsplit(".", 1)[0]

img = Image.open(src).convert("RGBA")

sizes = [256, 48, 32, 16]
for s in sizes:
    out = f"{prefix}-{s}.ico"
    img.save(out, format="ICO", sizes=[(s, s)])
    print(f"Saved: {out}")

# Combined (all sizes)
combined = f"{prefix}.ico"
img.save(combined, format="ICO", sizes=[(s, s) for s in sizes])
print(f"Saved (combined): {combined}")
