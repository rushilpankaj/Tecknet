"""The app icon, drawn in code so the tray can show an "off" version.

Every size is drawn on its own (not shrunk from a big image), with lines at
least ~1.5 px wide, so the 16-24 px tray and title-bar icons stay sharp.
"""

from PIL import Image, ImageDraw

ACCENT = (37, 99, 235, 255)
MUTED = (120, 124, 132, 255)
WHITE = (255, 255, 255, 255)
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def app_icon(size=64, enabled=True):
    scale = 4  # draw at 4x, then shrink once, for smooth edges
    big = size * scale
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=big * 0.24, fill=ACCENT if enabled else MUTED)
    stroke = round(max(size * 0.075, 1.6) * scale)
    left, top, right, bottom = big * 0.29, big * 0.15, big * 0.71, big * 0.85
    draw.rounded_rectangle((left, top, right, bottom), radius=(right - left) / 2, outline=WHITE, width=stroke)
    middle = big / 2
    split = big * 0.43
    draw.line((left + stroke / 2, split, right - stroke / 2, split), fill=WHITE, width=stroke)
    draw.line((middle, top + stroke / 2, middle, split), fill=WHITE, width=stroke)
    return image.resize((size, size), Image.LANCZOS)


def save_ico(path, enabled=True, sizes=ICO_SIZES):
    images = [app_icon(size, enabled) for size in sizes]
    images[-1].save(path, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[:-1])
