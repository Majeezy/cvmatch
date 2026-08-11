"""Generate app_icon.ico and logo.svg for Job Application Assistant."""
import os
from pathlib import Path

ROOT = Path(__file__).parent

# ── SVG Logo (saved as file and embedded in HTML) ─────────────────────────────

SVG_LOGO = '''<svg width="200" height="200" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect width="200" height="200" rx="40" fill="#58a6ff"/>
  <!-- Briefcase body -->
  <rect x="35" y="105" width="130" height="75" rx="10" fill="#0d1117"/>
  <!-- Briefcase handle -->
  <path d="M72 105V88C72 76 128 76 128 88V105"
        stroke="#0d1117" stroke-width="12" fill="none" stroke-linecap="round"/>
  <!-- Center divider line -->
  <rect x="35" y="138" width="130" height="5" fill="#58a6ff"/>
  <!-- Clasp -->
  <rect x="82" y="125" width="36" height="26" rx="6" fill="#58a6ff"/>
  <!-- Keyhole -->
  <circle cx="100" cy="136" r="5" fill="#0d1117"/>
  <rect x="97" y="136" width="6" height="9" rx="2" fill="#0d1117"/>
  <!-- Stars / sparkles at top -->
  <circle cx="55" cy="58" r="5" fill="#0d1117" opacity="0.6"/>
  <circle cx="100" cy="42" r="7" fill="#0d1117" opacity="0.8"/>
  <circle cx="145" cy="58" r="5" fill="#0d1117" opacity="0.6"/>
  <circle cx="75" cy="75" r="3" fill="#0d1117" opacity="0.4"/>
  <circle cx="125" cy="75" r="3" fill="#0d1117" opacity="0.4"/>
</svg>'''

# ── ICO generator ──────────────────────────────────────────────────────────────

def make_icon_image(size: int):
    from PIL import Image, ImageDraw, ImageFont

    bg_color = (88, 166, 255, 255)       # --accent blue
    body_color = (13, 17, 23, 255)        # --bg dark
    accent2 = (88, 166, 255, 255)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded square background
    r = max(2, size // 5)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=bg_color)

    if size >= 32:
        # Briefcase body
        pad = size // 7
        bx1 = pad
        bx2 = size - pad
        by1 = size // 2
        by2 = size - pad + 2

        body_r = max(1, size // 16)
        draw.rounded_rectangle([bx1, by1, bx2, by2], radius=body_r, fill=body_color)

        # Handle
        hw = (bx2 - bx1) * 5 // 12
        hx1 = (size - hw) // 2
        hx2 = hx1 + hw
        handle_top = by1 - size // 6
        thickness = max(2, size // 18)
        draw.rounded_rectangle(
            [hx1, handle_top, hx2, by1 + thickness],
            radius=max(1, size // 14),
            fill=None,
            outline=body_color,
            width=thickness,
        )

        # Center stripe
        mid = (by1 + by2) // 2
        stripe_h = max(1, size // 28)
        draw.rectangle([bx1, mid - stripe_h, bx2, mid + stripe_h], fill=bg_color)

        # Clasp
        if size >= 48:
            clasp_w = size // 6
            clasp_h = size // 10
            cx = (size - clasp_w) // 2
            cy = mid - clasp_h // 2
            draw.rounded_rectangle(
                [cx, cy, cx + clasp_w, cy + clasp_h],
                radius=max(1, size // 28),
                fill=bg_color,
            )
    else:
        # Tiny sizes: just a simple "J" letter
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", max(6, size * 2 // 3))
        except Exception:
            font = ImageFont.load_default()
        text = "J"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((size - tw) // 2 - bbox[0], (size - th) // 2 - bbox[1]),
            text,
            fill=body_color,
            font=font,
        )

    return img


def create_ico():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [make_icon_image(s) for s in sizes]

    out = ROOT / "app_icon.ico"
    images[0].save(
        out,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"[OK] ICO saved  -> {out}")
    return out


def create_svg():
    out = ROOT / "logo.svg"
    out.write_text(SVG_LOGO, encoding="utf-8")
    print(f"[OK] SVG saved  -> {out}")
    return out


if __name__ == "__main__":
    create_svg()
    create_ico()
    print("\nDone! Run setup_shortcut.ps1 to create the desktop shortcut.")
