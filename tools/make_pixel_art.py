"""Snap generated artwork onto true pixel grids for the Tk interface.

Sources in assets/pixel/source are full-resolution generations; outputs are
quantized at native resolution and enlarged by an integer factor.
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from PIL import Image, ImageChops, ImageStat
from x68.pixel import pixelate

SRC, OUT = ROOT / 'assets/pixel/source', ROOT / 'assets/pixel'


def sprite(name, cells=32, scale=2):
    image = Image.open(SRC / name).convert('RGB')
    w, h = image.size
    px = image.load()
    key = lambda c: c[0] > 200 and c[1] < 90 and c[2] > 200
    xs = [x for x in range(w) for y in range(0, h, 4) if not key(px[x, y])]
    ys = [y for y in range(h) for x in range(0, w, 4) if not key(px[x, y])]
    box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    art = image.crop(box)
    # The prompt asked for a 32-cell sprite; the subject box is ~19.8 px per cell.
    # Sample each cell centre: averaging would blend the outline into the key colour.
    step = art.width / cells, art.height / cells
    small = Image.new('RGB', (cells, cells))
    for y in range(cells):
        for x in range(cells):
            small.putpixel((x, y), art.getpixel((int((x + 0.5) * step[0]), int((y + 0.5) * step[1]))))
    small = small.quantize(colors=12, dither=Image.Dither.NONE).convert('RGBA')
    mask = Image.new('L', small.size, 255)
    for y in range(small.height):
        for x in range(small.width):
            if key(small.getpixel((x, y))):
                mask.putpixel((x, y), 0)
    small.putalpha(mask)
    canvas = Image.new('RGBA', (cells, cells), (0, 0, 0, 0))
    canvas.paste(small, ((cells - small.width) // 2, cells - small.height), small)
    canvas.resize((cells * scale, cells * scale), Image.Resampling.NEAREST).save(OUT / name)
    return small.size


def scene(name, native, scale):
    pixelate(Image.open(SRC / name), native, scale).save(OUT / name, optimize=True)


if __name__ == '__main__':
    scene('home-scene.png', (320, 180), 2)
    scene('battery-scene.png', (190, 106), 2)
    print('sprite cells', sprite('bunny-sprite.png'))
