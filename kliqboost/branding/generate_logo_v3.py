#!/usr/bin/env python3
"""
Generate premium Kliqboost logo using HTML/CSS + Playwright.
Professional gradient, typography, and effects rendered in Chromium.
"""

import asyncio
from pathlib import Path

OUT = Path(__file__).parent

LOGO_HTML = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@700;800;900&family=Outfit:wght@700;800&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    width: 800px;
    height: 800px;
    overflow: hidden;
    background: #0a0a1a;
}

.logo-container {
    width: 800px;
    height: 800px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
    background: radial-gradient(ellipse at 30% 30%, #1a2a5e 0%, #0d1230 40%, #080c20 70%, #050810 100%);
}

/* Subtle background orbs */
.logo-container::before {
    content: '';
    position: absolute;
    top: -100px;
    left: -100px;
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%);
    border-radius: 50%;
}
.logo-container::after {
    content: '';
    position: absolute;
    bottom: -150px;
    right: -100px;
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(139,92,246,0.06) 0%, transparent 70%);
    border-radius: 50%;
}

/* Outer ring */
.ring {
    position: absolute;
    width: 620px;
    height: 620px;
    border-radius: 50%;
    border: 1.5px solid rgba(255,255,255,0.06);
}
.ring-inner {
    position: absolute;
    width: 560px;
    height: 560px;
    border-radius: 50%;
    border: 1px solid rgba(255,255,255,0.03);
}

/* Main monogram */
.monogram {
    font-family: 'Inter', 'Outfit', -apple-system, sans-serif;
    font-weight: 900;
    font-size: 220px;
    letter-spacing: -8px;
    background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 40%, #a5b4fc 70%, #818cf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    position: relative;
    z-index: 2;
    filter: drop-shadow(0 4px 30px rgba(99,102,241,0.3)) drop-shadow(0 0 80px rgba(99,102,241,0.15));
    line-height: 1;
    margin-bottom: 8px;
}

/* Brand name */
.brand-name {
    font-family: 'Inter', 'Outfit', -apple-system, sans-serif;
    font-weight: 700;
    font-size: 48px;
    letter-spacing: 14px;
    text-transform: uppercase;
    background: linear-gradient(90deg, #fbbf24 0%, #f59e0b 50%, #d97706 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    position: relative;
    z-index: 2;
    margin-top: 5px;
    filter: drop-shadow(0 2px 10px rgba(251,191,36,0.2));
}

/* Subtle tagline */
.tagline {
    font-family: 'Inter', -apple-system, sans-serif;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 6px;
    text-transform: uppercase;
    color: rgba(148,163,184,0.5);
    margin-top: 18px;
    z-index: 2;
    position: relative;
}

/* Decorative dots */
.dot {
    position: absolute;
    border-radius: 50%;
    background: rgba(99,102,241,0.15);
    z-index: 1;
}
.dot-1 { width: 6px; height: 6px; top: 15%; left: 20%; }
.dot-2 { width: 4px; height: 4px; top: 25%; right: 22%; background: rgba(251,191,36,0.12); }
.dot-3 { width: 5px; height: 5px; bottom: 28%; left: 18%; background: rgba(52,211,153,0.1); }
.dot-4 { width: 3px; height: 3px; bottom: 20%; right: 25%; }
.dot-5 { width: 8px; height: 8px; top: 12%; right: 35%; background: rgba(99,102,241,0.08); }
</style>
</head>
<body>
<div class="logo-container">
    <div class="ring"></div>
    <div class="ring-inner"></div>
    <div class="dot dot-1"></div>
    <div class="dot dot-2"></div>
    <div class="dot dot-3"></div>
    <div class="dot dot-4"></div>
    <div class="dot dot-5"></div>
    <div class="monogram">KB</div>
    <div class="brand-name">Kliqboost</div>
    <div class="tagline">Premium Ad Accounts</div>
</div>
</body>
</html>'''


async def render_logo():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page(
            viewport={"width": 800, "height": 800},
            device_scale_factor=2,  # 1600x1600 actual pixels
        )

        html_path = OUT / "_temp_logo.html"
        html_path.write_text(LOGO_HTML, encoding="utf-8")

        await page.goto(f"file://{html_path}")
        await page.wait_for_timeout(1000)  # Wait for font loading

        # Full 800px logo
        await page.screenshot(
            path=str(OUT / "logo_800.png"),
            type="png",
            clip={"x": 0, "y": 0, "width": 800, "height": 800},
        )
        print("✅ logo_800.png (1600x1600 retina)")

        await page.close()

        # Resize to 400px version
        from PIL import Image
        img = Image.open(OUT / "logo_800.png")
        img.resize((400, 400), Image.LANCZOS).save(OUT / "logo_400.png", quality=98)
        print("✅ logo_400.png (400x400)")

        html_path.unlink()
        await browser.close()


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Generating Kliqboost Premium Logo")
    print("  HTML/CSS + Playwright (Retina quality)")
    print("=" * 50 + "\n")

    asyncio.run(render_logo())

    from PIL import Image
    img = Image.open(OUT / "logo_800.png")
    print(f"\n  Final: {img.size[0]}x{img.size[1]}")
    print(f"  File: {len(open(OUT / 'logo_800.png', 'rb').read()) / 1024:.0f}KB")
'''

Now let me also render the logo without Google Fonts dependency (fallback to system fonts):
'''
