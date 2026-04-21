#!/usr/bin/env python3
"""Generate all Kliqboost branding images using Pillow."""

import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
BRAND = "Kliqboost"

# Colors
GRADIENT_START = (30, 58, 138)   # Deep blue
GRADIENT_END = (99, 102, 241)    # Indigo
ACCENT = (251, 191, 36)          # Gold/amber
WHITE = (255, 255, 255)
DARK = (15, 23, 42)
LIGHT_BG = (241, 245, 249)
GREEN = (34, 197, 94)
RED = (239, 68, 68)

# Fonts
try:
    FONT_BOLD = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    FONT_REG = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    FONT_SM = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    FONT_XS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    FONT_LOGO = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 200)
    FONT_LOGO_SM = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    FONT_TITLE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    FONT_SUBTITLE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    FONT_STAR = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 44)
except Exception:
    FONT_BOLD = ImageFont.load_default()
    FONT_REG = FONT_BOLD
    FONT_SM = FONT_BOLD
    FONT_XS = FONT_BOLD
    FONT_LOGO = FONT_BOLD
    FONT_LOGO_SM = FONT_BOLD
    FONT_TITLE = FONT_BOLD
    FONT_SUBTITLE = FONT_BOLD
    FONT_STAR = FONT_BOLD


def gradient_fill(draw, width, height, start_color, end_color, direction="vertical"):
    for i in range(height if direction == "vertical" else width):
        ratio = i / (height if direction == "vertical" else width)
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
        if direction == "vertical":
            draw.line([(0, i), (width, i)], fill=(r, g, b))
        else:
            draw.line([(i, 0), (i, height)], fill=(r, g, b))


def draw_rounded_rect(draw, xy, fill, radius=20):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def draw_circle_avatar(draw, center, radius, color, letter, font):
    x, y = center
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)
    bbox = font.getbbox(letter)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x - tw // 2, y - th // 2 - 5), letter, fill=WHITE, font=font)


def centered_text(draw, y, text, font, fill, width):
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, y), text, fill=fill, font=font)


# ════════════════════════════════════════════════════════════════════════
# 1. Logo / Profile Picture (800x800)
# ════════════════════════════════════════════════════════════════════════

def gen_logo():
    size = 800
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    gradient_fill(draw, size, size, GRADIENT_START, GRADIENT_END)

    # Decorative circles
    draw.ellipse([50, 50, 350, 350], fill=(*GRADIENT_END, 40), outline=None)
    draw.ellipse([500, 450, 780, 730], fill=(*GRADIENT_START, 40), outline=None)

    # KB monogram
    text = "KB"
    bbox = FONT_LOGO.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - 60

    # Shadow
    draw.text((x + 4, y + 4), text, fill=(0, 0, 0, 80), font=FONT_LOGO)
    draw.text((x, y), text, fill=WHITE, font=FONT_LOGO)

    # Brand name below
    centered_text(draw, y + th + 20, BRAND.upper(), FONT_LOGO_SM, ACCENT, size)

    img.save(OUT / "logo_800.png", quality=95)
    # Also save a smaller version for profile pics
    img.resize((400, 400), Image.LANCZOS).save(OUT / "logo_400.png", quality=95)
    print("✅ Logo generated")


# ════════════════════════════════════════════════════════════════════════
# 2. Channel Banners (1280x720)
# ════════════════════════════════════════════════════════════════════════

def gen_banner_welcome():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    gradient_fill(draw, w, h, GRADIENT_START, GRADIENT_END)

    # Accent bar
    draw.rectangle([0, 0, w, 8], fill=ACCENT)
    draw.rectangle([0, h - 8, w, h], fill=ACCENT)

    centered_text(draw, 80, "🚀", FONT_TITLE, WHITE, w)
    centered_text(draw, 170, "Welcome to Kliqboost", FONT_TITLE, WHITE, w)
    centered_text(draw, 260, "Premium Ad Accounts for Serious Media Buyers", FONT_SUBTITLE, (*WHITE, 220), w)

    # Feature boxes
    features = [
        ("✅", "No Spend Limits"),
        ("🔄", "Free Replacements"),
        ("⚡", "24h Delivery"),
        ("🛡️", "Agency Accounts"),
    ]
    box_w = 250
    start_x = (w - (box_w * 4 + 30 * 3)) // 2
    for i, (icon, label) in enumerate(features):
        x = start_x + i * (box_w + 30)
        draw_rounded_rect(draw, (x, 380, x + box_w, 520), fill=(255, 255, 255, 25), radius=15)
        draw.rounded_rectangle((x, 380, x + box_w, 520), radius=15, fill=None, outline=(*WHITE, 100), width=2)
        centered_text(draw, 395, icon, FONT_BOLD, WHITE, box_w)
        bbox = FONT_SM.getbbox(label)
        tw = bbox[2] - bbox[0]
        draw.text((x + (box_w - tw) // 2, 460), label, fill=WHITE, font=FONT_SM)

    # CTA
    cta_text = "DM @kliqboost to get started"
    bbox = FONT_REG.getbbox(cta_text)
    tw = bbox[2] - bbox[0]
    cx = (w - tw) // 2
    draw_rounded_rect(draw, (cx - 30, 590, cx + tw + 30, 660), fill=ACCENT, radius=12)
    draw.text((cx, 598), cta_text, fill=DARK, font=FONT_REG)

    img.save(OUT / "banner_welcome.png", quality=95)
    print("✅ Welcome banner generated")


def gen_banner_pricing():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), DARK)
    draw = ImageDraw.Draw(img)

    # Header gradient strip
    for i in range(120):
        ratio = i / 120
        r = int(GRADIENT_START[0] + (GRADIENT_END[0] - GRADIENT_START[0]) * ratio)
        g = int(GRADIENT_START[1] + (GRADIENT_END[1] - GRADIENT_START[1]) * ratio)
        b = int(GRADIENT_START[2] + (GRADIENT_END[2] - GRADIENT_START[2]) * ratio)
        draw.line([(0, i), (w, i)], fill=(r, g, b))

    centered_text(draw, 30, "💰 Pricing Overview", FONT_TITLE, WHITE, w)

    # Pricing table
    platforms = [
        ("Google Ads", "$50", "$100", "$800/mo"),
        ("Meta Ads", "$200/mo", "$450/mo", "$1000/mo"),
        ("Bing Ads", "$100", "$300", "$1000/mo"),
        ("TikTok Ads", "$80", "$200", "$600/mo"),
    ]
    headers = ["Platform", "Basic", "Pro", "Enterprise"]
    col_w = [320, 240, 240, 280]
    start_x = (w - sum(col_w)) // 2
    y = 150

    # Header row
    x = start_x
    for i, header in enumerate(headers):
        draw_rounded_rect(draw, (x, y, x + col_w[i] - 5, y + 55), fill=GRADIENT_END, radius=8)
        bbox = FONT_SM.getbbox(header)
        tw = bbox[2] - bbox[0]
        draw.text((x + (col_w[i] - tw) // 2, y + 12), header, fill=WHITE, font=FONT_SM)
        x += col_w[i]

    # Data rows
    for row_i, (platform, basic, pro, ent) in enumerate(platforms):
        y_row = y + 70 + row_i * 75
        row_bg = (30, 41, 59) if row_i % 2 == 0 else (51, 65, 85)
        x = start_x
        vals = [platform, basic, pro, ent]
        for col_i, val in enumerate(vals):
            draw_rounded_rect(draw, (x, y_row, x + col_w[col_i] - 5, y_row + 60), fill=row_bg, radius=8)
            font = FONT_SM if col_i == 0 else FONT_SM
            color = WHITE if col_i == 0 else GREEN
            bbox = font.getbbox(val)
            tw = bbox[2] - bbox[0]
            draw.text((x + (col_w[col_i] - tw) // 2, y_row + 15), val, fill=color, font=font)
            x += col_w[col_i]

    # Footer
    centered_text(draw, 620, "All plans include free replacements + dedicated support", FONT_SM, ACCENT, w)
    centered_text(draw, 660, "Crypto accepted: BTC • ETH • USDT", FONT_XS, (148, 163, 184), w)

    img.save(OUT / "banner_pricing.png", quality=95)
    print("✅ Pricing banner generated")


def gen_banner_platforms():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    gradient_fill(draw, w, h, (15, 23, 42), (30, 58, 138))

    centered_text(draw, 40, "🌐 Platforms We Support", FONT_TITLE, WHITE, w)

    platforms = [
        ("Google Ads", "🔍", (66, 133, 244)),
        ("Meta Ads", "📘", (24, 119, 242)),
        ("TikTok Ads", "🎵", (0, 0, 0)),
        ("Bing Ads", "🔎", (0, 120, 212)),
        ("Taboola", "📰", (0, 87, 255)),
        ("Outbrain", "📊", (233, 83, 34)),
    ]

    box_w = 350
    box_h = 180
    gap = 40
    cols = 3
    start_x = (w - (box_w * cols + gap * (cols - 1))) // 2
    start_y = 150

    for i, (name, icon, color) in enumerate(platforms):
        row = i // cols
        col = i % cols
        x = start_x + col * (box_w + gap)
        y = start_y + row * (box_h + gap)

        draw_rounded_rect(draw, (x, y, x + box_w, y + box_h), fill=(30, 41, 59), radius=16)
        draw.rounded_rectangle((x, y, x + box_w, y + box_h), radius=16, outline=color, width=3)

        # Icon + name
        draw.text((x + 20, y + 25), icon, fill=WHITE, font=FONT_BOLD)
        draw.text((x + 85, y + 30), name, fill=WHITE, font=FONT_BOLD)

        # Subtitle
        draw.text((x + 20, y + 100), "✅ Full campaign support", fill=(148, 163, 184), font=FONT_XS)
        draw.text((x + 20, y + 130), "✅ No spend limits", fill=(148, 163, 184), font=FONT_XS)

    centered_text(draw, 620, "Need another platform? DM us — we'll figure it out 💪", FONT_SM, ACCENT, w)

    img.save(OUT / "banner_platforms.png", quality=95)
    print("✅ Platforms banner generated")


def gen_banner_stats():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), DARK)
    draw = ImageDraw.Draw(img)

    # Top accent
    draw.rectangle([0, 0, w, 6], fill=ACCENT)

    centered_text(draw, 30, "📊 Results That Speak", FONT_TITLE, WHITE, w)
    centered_text(draw, 110, "Our clients' numbers don't lie", FONT_SUBTITLE, (148, 163, 184), w)

    stats = [
        ("500+", "Active Clients"),
        ("$2M+", "Monthly Ad Spend"),
        ("99.5%", "Uptime"),
        ("< 24h", "Delivery Time"),
    ]

    stat_w = 260
    gap = 30
    start_x = (w - (stat_w * 4 + gap * 3)) // 2
    y = 220

    for i, (value, label) in enumerate(stats):
        x = start_x + i * (stat_w + gap)
        draw_rounded_rect(draw, (x, y, x + stat_w, y + 250), fill=(30, 41, 59), radius=20)

        # Value
        font_val = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        bbox = font_val.getbbox(value)
        tw = bbox[2] - bbox[0]
        draw.text((x + (stat_w - tw) // 2, y + 50), value, fill=ACCENT, font=font_val)

        # Label
        bbox = FONT_SM.getbbox(label)
        tw = bbox[2] - bbox[0]
        draw.text((x + (stat_w - tw) // 2, y + 150), label, fill=WHITE, font=FONT_SM)

    # Bottom bar
    centered_text(draw, 560, "🔥 0 bans in 90 days for Pro+ clients", FONT_REG, GREEN, w)
    centered_text(draw, 620, "Join them → DM @kliqboost", FONT_SM, (148, 163, 184), w)

    img.save(OUT / "banner_stats.png", quality=95)
    print("✅ Stats banner generated")


def gen_banner_cta():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    gradient_fill(draw, w, h, GRADIENT_END, GRADIENT_START)

    centered_text(draw, 100, "Ready to Scale?", FONT_TITLE, WHITE, w)
    centered_text(draw, 200, "Stop burning through personal accounts.", FONT_SUBTITLE, (*WHITE, 200), w)
    centered_text(draw, 260, "Get agency-level access today.", FONT_SUBTITLE, (*WHITE, 200), w)

    # Steps
    steps = [
        ("1️⃣", "DM @kliqboost"),
        ("2️⃣", "Tell us your platform & budget"),
        ("3️⃣", "Pay via crypto"),
        ("4️⃣", "Start running ads in 24h"),
    ]
    y = 370
    for i, (num, text) in enumerate(steps):
        step_y = y + i * 55
        bbox = FONT_REG.getbbox(f"{num}  {text}")
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, step_y), f"{num}  {text}", fill=WHITE, font=FONT_REG)

    # CTA button
    cta = "DM @kliqboost now →"
    bbox = FONT_BOLD.getbbox(cta)
    tw = bbox[2] - bbox[0]
    cx = (w - tw) // 2
    draw_rounded_rect(draw, (cx - 40, 610, cx + tw + 40, 685), fill=ACCENT, radius=16)
    draw.text((cx, 618), cta, fill=DARK, font=FONT_BOLD)

    img.save(OUT / "banner_cta.png", quality=95)
    print("✅ CTA banner generated")


# ════════════════════════════════════════════════════════════════════════
# 3. Vouch Cards (1280x720) — Realistic testimonials
# ════════════════════════════════════════════════════════════════════════

VOUCHES = [
    {
        "username": "@crypto_scalr",
        "name": "Alex M.",
        "platform": "Google Ads",
        "plan": "Pro",
        "duration": "3 months",
        "text": "Been using Kliqboost for 3 months. Google Pro accounts — zero bans. Spent $150K+ without a single interruption. Best provider I've tried.",
        "stars": 5,
        "color": (66, 133, 244),
        "avatar_color": (59, 130, 246),
    },
    {
        "username": "@mediabuyer_rx",
        "name": "Marcus T.",
        "platform": "Meta Ads",
        "plan": "Enterprise",
        "duration": "6 months",
        "text": "Running nutra on Meta. 20 ad accounts across 3 BMs, $50K/day capacity. Approval rate went from 30% to 85%. Never going back.",
        "stars": 5,
        "color": (24, 119, 242),
        "avatar_color": (37, 99, 235),
    },
    {
        "username": "@scale_ninja",
        "name": "Viktor R.",
        "platform": "Google + Bing",
        "plan": "Pro",
        "duration": "4 months",
        "text": "Finance vertical — used to get banned weekly. With Kliqboost Pro, zero bans in 4 months. The replacement policy is clutch.",
        "stars": 5,
        "color": (0, 120, 212),
        "avatar_color": (14, 165, 233),
    },
    {
        "username": "@affking_eu",
        "name": "Daniel K.",
        "platform": "TikTok + Meta",
        "plan": "Enterprise",
        "duration": "5 months",
        "text": "Sweepstakes on TikTok + Meta. Kliqboost handles replacements same day. Support DMs back within minutes. Solid team, highly recommend.",
        "stars": 5,
        "color": (0, 0, 0),
        "avatar_color": (168, 85, 247),
    },
    {
        "username": "@ppc_trader",
        "name": "Raj P.",
        "platform": "Google Ads",
        "plan": "Basic",
        "duration": "2 months",
        "text": "Started with Basic to test them out. Accounts are legit, delivery was 24h. Upgrading to Pro next month. Good value for money.",
        "stars": 4,
        "color": (66, 133, 244),
        "avatar_color": (245, 158, 11),
    },
    {
        "username": "@content_arb",
        "name": "Tom S.",
        "platform": "Taboola + Google",
        "plan": "Basic",
        "duration": "1 month",
        "text": "Content arbitrage setup — Taboola + Google combo. Kliqboost had me running in 24 hours. Great communication, fair prices.",
        "stars": 5,
        "color": (0, 87, 255),
        "avatar_color": (16, 185, 129),
    },
]


def gen_vouch_card(vouch, index):
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), (241, 245, 249))
    draw = ImageDraw.Draw(img)

    # Top color bar
    draw.rectangle([0, 0, w, 10], fill=vouch["color"])

    # Card background
    draw_rounded_rect(draw, (60, 40, w - 60, h - 40), fill=WHITE, radius=24)

    # "Verified Review" badge
    badge_text = "✅ VERIFIED REVIEW"
    bbox = FONT_XS.getbbox(badge_text)
    tw = bbox[2] - bbox[0]
    draw_rounded_rect(draw, (w - tw - 120, 60, w - 80, 95), fill=(220, 252, 231), radius=8)
    draw.text((w - tw - 110, 63), badge_text, fill=(22, 163, 74), font=FONT_XS)

    # Avatar circle
    draw_circle_avatar(draw, (140, 140), 50, vouch["avatar_color"], vouch["name"][0], FONT_BOLD)

    # Name + username
    draw.text((210, 100), vouch["name"], fill=DARK, font=FONT_BOLD)
    draw.text((210, 155), vouch["username"], fill=(100, 116, 139), font=FONT_SM)

    # Stars
    stars = "★" * vouch["stars"] + "☆" * (5 - vouch["stars"])
    draw.text((210, 195), stars, fill=ACCENT, font=FONT_STAR)

    # Testimonial text (word wrap)
    text = f'"{vouch["text"]}"'
    max_chars = 65
    lines = []
    words = text.split()
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = current + " " + word if current else word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    y = 280
    for line in lines:
        draw.text((100, y), line, fill=(30, 41, 59), font=FONT_REG)
        y += 50

    # Platform / Plan / Duration tags
    tags = [
        f"📱 {vouch['platform']}",
        f"📦 {vouch['plan']} Plan",
        f"⏱️ {vouch['duration']}",
    ]
    tag_x = 100
    tag_y = h - 140
    for tag in tags:
        bbox = FONT_XS.getbbox(tag)
        tw = bbox[2] - bbox[0]
        draw_rounded_rect(draw, (tag_x, tag_y, tag_x + tw + 24, tag_y + 40), fill=(241, 245, 249), radius=10)
        draw.text((tag_x + 12, tag_y + 8), tag, fill=(71, 85, 105), font=FONT_XS)
        tag_x += tw + 44

    # Kliqboost watermark
    wm = f"{BRAND} • Verified Client"
    bbox = FONT_XS.getbbox(wm)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, h - 75), wm, fill=(203, 213, 225), font=FONT_XS)

    img.save(OUT / f"vouch_{index + 1}.png", quality=95)
    print(f"✅ Vouch card {index + 1} generated ({vouch['username']})")


# ════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"Generating {BRAND} branding images...\n")

    gen_logo()
    gen_banner_welcome()
    gen_banner_pricing()
    gen_banner_platforms()
    gen_banner_stats()
    gen_banner_cta()

    for i, vouch in enumerate(VOUCHES):
        gen_vouch_card(vouch, i)

    print(f"\n🎉 All images saved to {OUT}")
    print(f"   Logo: logo_800.png, logo_400.png")
    print(f"   Banners: banner_welcome.png, banner_pricing.png, banner_platforms.png, banner_stats.png, banner_cta.png")
    print(f"   Vouches: vouch_1.png through vouch_6.png")
