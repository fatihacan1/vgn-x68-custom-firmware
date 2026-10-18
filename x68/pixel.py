"""PC-98 style chrome for Tk: bundled bitmap-style fonts, double-line windows, bevelled buttons.

Fonts are SIL OFL (assets/fonts). Sizes are negative (pixels) and kept on the
fonts' native 8/16 px grids so Windows renders them without blurry scaling.
"""
import sys
import tkinter as tk
import tkinter.font
from pathlib import Path

# Palette: one accent (MINT). PINK and AMBER only carry battery/error state.
DESK = '#0c0916'
WIN = '#1b1430'
FIELD = '#120d22'
LINE_HI = '#ece2ff'
LINE_MID = '#8a76c4'
LINE_DK = '#352862'
TEXT = '#ece2ff'
MUTED = '#a395cf'
DIM = '#5f5488'
MINT = '#7cf2c2'
PINK = '#ff6f9c'
AMBER = '#ffc66b'

BODY = ('DotGothic16', -16)
BIG_BODY = ('DotGothic16', -32)
LABEL = ('Press Start 2P', -8)
HEAD = ('Press Start 2P', -16)
TITLE = ('Press Start 2P', -24)
HUGE = ('Press Start 2P', -40)


def load_fonts(folder):
    """Register the bundled fonts for this process only (Windows). Elsewhere Tk falls back."""
    if sys.platform != 'win32':
        return False
    import ctypes
    ok = True
    for name in ('DotGothic16-Regular.ttf', 'PressStart2P-Regular.ttf'):
        path = Path(folder) / name
        ok &= path.exists() and ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0) > 0
    return ok


def window(parent, title=None, fill=WIN, pad=12):
    """Double-line window frame. Returns (outer, inner); pack/grid the outer, fill the inner."""
    outer = tk.Frame(parent, bg=LINE_DK, padx=2, pady=2)
    hi = tk.Frame(outer, bg=LINE_HI, padx=2, pady=2)
    hi.pack(fill='both', expand=True)
    mid = tk.Frame(hi, bg=LINE_MID, padx=2, pady=2)
    mid.pack(fill='both', expand=True)
    inner = tk.Frame(mid, bg=fill, padx=pad, pady=pad)
    inner.pack(fill='both', expand=True)
    for relx, rely, anchor in ((0, 0, 'nw'), (1, 0, 'ne'), (0, 1, 'sw'), (1, 1, 'se')):
        tk.Frame(outer, bg=MINT, width=6, height=6).place(relx=relx, rely=rely, anchor=anchor)
    if title:
        tk.Label(inner, text=title, font=LABEL, bg=fill, fg=MUTED).pack(anchor='w', pady=(0, 8))
    return outer, inner


class PixelButton(tk.Canvas):
    """Bevelled button drawn on a canvas. Supports configure(text/state/command) and item access."""

    SKINS = {
        'normal': ('#2a2048', '#5d4a9e', '#120d24', LINE_MID, TEXT),
        'accent': (MINT, '#d2ffec', '#2f9a72', '#1d6b4f', '#0f1a17'),
        'disabled': (WIN, WIN, WIN, LINE_DK, DIM),
    }

    def __init__(self, parent, text, command=None, accent=False, bg=WIN, font=BODY):
        super().__init__(parent, height=34, bg=bg, highlightthickness=0, bd=0, cursor='hand2')
        self._text, self._command, self._accent, self._state = text, command, accent, 'normal'
        self._font, self._hover, self._down = font, False, False
        self.bind('<Enter>', lambda e: self._set(hover=True))
        self.bind('<Leave>', lambda e: self._set(hover=False, down=False))
        self.bind('<ButtonPress-1>', lambda e: self._set(down=True))
        self.bind('<ButtonRelease-1>', self._release)
        self._draw()

    def _set(self, **flags):
        for key, value in flags.items():
            setattr(self, '_' + key, value)
        self._draw()

    def _release(self, event):
        fire = self._down and self._state != 'disabled' and 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self._set(down=False)
        if fire and self._command:
            self._command()

    def _draw(self):
        self.delete('all')
        width = tk.font.Font(font=self._font).measure(self._text) + 36
        super().configure(width=width)
        skin = 'disabled' if self._state == 'disabled' else ('accent' if self._accent else 'normal')
        face, light, shadow, edge, ink = self.SKINS[skin]
        if self._hover and skin == 'normal':
            face = '#3a2d63'
        if self._hover and skin == 'accent':
            face = '#a2f7d5'
        if self._down and skin != 'disabled':
            light, shadow = shadow, light
        h, w, dy = 34, width, 2 if self._down and skin != 'disabled' else 0
        self.create_rectangle(0, 0, w, h, fill=edge, outline='')
        self.create_rectangle(2, 2, w - 2, h - 2, fill=face, outline='')
        self.create_rectangle(2, 2, w - 2, 4, fill=light, outline='')
        self.create_rectangle(2, 2, 4, h - 2, fill=light, outline='')
        self.create_rectangle(2, h - 4, w - 2, h - 2, fill=shadow, outline='')
        self.create_rectangle(w - 4, 2, w - 2, h - 2, fill=shadow, outline='')
        self.create_text(w / 2, h / 2 + dy, text=self._text, font=self._font, fill=ink)
        if self._hover and skin != 'disabled':
            self.create_text(9, h / 2 + dy, text='▶', font=LABEL, fill=ink)

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        for key in ('text', 'state', 'command'):
            if key in kw:
                setattr(self, '_' + key, kw.pop(key))
        if kw:
            super().configure(**kw)
        self._draw()

    config = configure

    def __getitem__(self, key):
        if key in ('text', 'state', 'command'):
            return getattr(self, '_' + key)
        return super().__getitem__(key)

    def invoke(self):
        if self._state != 'disabled' and self._command:
            self._command()


def panel(parent, title=None, pad=12):
    """Inset field inside a window: flat FIELD fill with a 2 px dark rule."""
    frame = tk.Frame(parent, bg=FIELD, padx=pad, pady=pad, highlightthickness=2, highlightbackground=LINE_DK)
    if title:
        tk.Label(frame, text=title, font=LABEL, bg=FIELD, fg=MUTED).pack(anchor='w', pady=(0, 10))
    return frame


class Choice(tk.Frame):
    """Menu-style tiles bound to a Tk variable. The selected tile carries the ▶ cursor."""

    def __init__(self, parent, variable, options, columns=1, width=None, bg=FIELD, marks=None):
        super().__init__(parent, bg=bg)
        self.variable, self.tiles, self.marks = variable, {}, marks or (lambda value: False)
        for n, option in enumerate(options):
            value, text = option if isinstance(option, tuple) else (option, str(option))
            tile = tk.Label(self, text=text, font=BODY, bg=bg, fg=MUTED, anchor='w', cursor='hand2', padx=4, pady=2, width=width)
            tile.grid(row=n // columns, column=n % columns, sticky='we', padx=(0, 6), pady=1)
            tile.bind('<Button-1>', lambda e, v=value: variable.set(v))
            tile.bind('<Enter>', lambda e, t=tile: t.configure(bg=LINE_DK))
            tile.bind('<Leave>', lambda e: self.refresh())
            self.tiles[value] = (tile, text)
        variable.trace_add('write', lambda *args: self.refresh())
        self.refresh()

    def refresh(self):
        try:
            current = self.variable.get()
        except tk.TclError:
            current = None
        for value, (tile, text) in self.tiles.items():
            on = value == current
            mark = '·' if self.marks(value) and not on else ' '
            tile.configure(text=('▶' if on else mark) + ' ' + text, fg=MINT if on else (TEXT if self.marks(value) else MUTED), bg=LINE_DK if on else self.cget('bg'))


class Meter(tk.Canvas):
    """Segmented 0..maximum setting, like an options-menu volume bar. Click a block to set it."""

    def __init__(self, parent, variable, maximum=4, bg=FIELD):
        self.count, self.variable = maximum + 1, variable
        super().__init__(parent, width=self.count * 26 + 4, height=22, bg=bg, highlightthickness=0, cursor='hand2')
        self.bind('<Button-1>', lambda e: variable.set(max(0, min(maximum, (e.x - 2) // 26))))
        variable.trace_add('write', lambda *args: self.draw())
        self.draw()

    def draw(self):
        self.delete('all')
        try:
            level = int(self.variable.get())
        except (tk.TclError, ValueError):
            level = 0
        for i in range(self.count):
            x = 2 + i * 26
            self.create_rectangle(x, 2, x + 22, 20, fill=LINE_DK, outline='')
            if i <= level:
                self.create_rectangle(x + 2, 4, x + 20, 18, fill=MINT, outline='')
                self.create_rectangle(x + 2, 4, x + 20, 6, fill='#d2ffec', outline='')


def shade(colour, factor):
    """Lighten (>1) or darken (<1) a #rrggbb colour."""
    try:
        r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, TypeError):
        return colour
    fix = lambda v: max(0, min(255, int(v * factor if factor < 1 else v + (255 - v) * (factor - 1))))
    return f'#{fix(r):02x}{fix(g):02x}{fix(b):02x}'


def keycap(canvas, x, y, w, h, face, legend, ink, cursor=False, pressed=False, font=BODY):
    """Chunky pixel keycap: dark edge, lit top rim, deeper front skirt, legend on the face."""
    x, y, w = int(x), int(y), int(w)
    drop = 2 if pressed else 0
    canvas.create_rectangle(x, y, x + w, y + h, fill='#0c0916', outline='')
    canvas.create_rectangle(x + 2, y + 2 + drop, x + w - 2, y + h - 2, fill=shade(face, 0.62), outline='')
    canvas.create_rectangle(x + 2, y + 2 + drop, x + w - 2, y + h - 8, fill=face, outline='')
    canvas.create_rectangle(x + 4, y + 2 + drop, x + w - 4, y + 4 + drop, fill=shade(face, 1.45), outline='')
    canvas.create_text(x + w / 2, y + (h - 6) / 2 + drop, text=legend, fill=ink, font=font)
    if cursor:
        for (a, b, c, d) in ((x - 4, y - 4, x + w + 4, y - 2), (x - 4, y + h + 2, x + w + 4, y + h + 4),
                             (x - 4, y - 4, x - 2, y + h + 4), (x + w + 2, y - 4, x + w + 4, y + h + 4)):
            canvas.create_rectangle(a, b, c, d, fill=MINT, outline='')


def pixelate(image, native, scale, colors=32):
    """Snap generated art onto a true pixel grid: box-downsample, quantize, nearest-upscale."""
    from PIL import Image
    small = image.convert('RGB').resize(native, Image.Resampling.BOX)
    small = small.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert('RGB')
    return small.resize((native[0] * scale, native[1] * scale), Image.Resampling.NEAREST)

