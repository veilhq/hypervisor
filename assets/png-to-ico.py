"""Convert a PNG to a proper multi-size ICO with transparency preserved."""
import sys
from PIL import Image

if len(sys.argv) < 2:
    print("Usage: python png-to-ico.py <input.png> [output.ico]")
    sys.exit(1)

src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else src.rsplit(".", 1)[0] + ".ico"

img = Image.open(src).convert("RGBA")
img.save(dst, format="ICO", sizes=[(256, 256), (48, 48), (32, 32), (16, 16)])
print(f"Saved: {dst}")
