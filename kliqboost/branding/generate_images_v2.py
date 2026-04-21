#!/usr/bin/env python3
"""
Generate all Kliqboost branding images v2.
- Logo: premium KB monogram with glow effects
- Banners: higher-quality gradient banners for main channel
- Vouches: REALISTIC Telegram chat screenshot format (dark theme)
  Mimics actual TG conversation UI with message bubbles, avatars, timestamps, read receipts
"""

import math
import random
import hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path(__file__).parent
BRAND = "Kliqboost"

# ═══════════════════════════════════════════════
# Color palette
# ═══════════════════════════════════════════════
# TG Dark theme colors
TG_BG = (23, 33, 43)           # Main chat background
TG_BUBBLE_OUT = (43, 82, 120)  # Outgoing message bubble (blue)
TG_BUBBLE_IN = (38, 50, 62)    # Incoming message bubble (dark gray)
TG_TEXT = (255, 255, 255)      # Message text
TG_TEXT_DIM = (152, 175, 198)  # Timestamps, meta text
TG_NAME = (106, 195, 247)     # Sender name in groups
TG_HEADER = (32, 45, 58)      # Chat header bar
TG_GREEN = (75, 205, 129)     # Online indicator, checkmarks
TG_LINK = (100, 181, 246)     # Links

# Brand colors
GRADIENT_START = (20, 40, 100)
GRADIENT_MID = (40, 70, 160)
GRADIENT_END = (80, 100, 220)
ACCENT_GOLD = (251, 191, 36)
ACCENT_GREEN = (52, 211, 153)
WHITE = (255, 255, 255)
DARK = (15, 23, 42)

# Avatar colors for different users
AVATAR_COLORS = [
    (233, 30, 99),   # Pink
    (33, 150, 243),  # Blue
    (76, 175, 80),   # Green
    (255, 152, 0),   # Orange
    (156, 39, 176),  # Purple
    (0, 188, 212),   # Cyan
    (244, 67, 54),   # Red
    (103, 58, 183),  # Deep Purple
]

# ═══════════════════════════════════════════════
# Fonts
# ═══════════════════════════════════════════════
ROBOTO = "/home/cjs/.fonts/Roboto-Regular.ttf"
ROBOTO_MED = "/home/cjs/.fonts/Roboto-Medium.ttf"
DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(DEJAVU, size)

# ═══════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════

def gradient_fill(draw, w, h, colors, direction="vertical"):
    """Multi-stop gradient fill."""
    if len(colors) == 2:
        colors = [colors[0], colors[1]]
    for i in range(h if direction == "vertical" else w):
        ratio = i / (h if direction == "vertical" else w)
        seg = int(ratio * (len(colors) - 1))
        seg = min(seg, len(colors) - 2)
        local_ratio = (ratio * (len(colors) - 1)) - seg
        c1, c2 = colors[seg], colors[seg + 1]
        r = int(c1[0] + (c2[0] - c1[0]) * local_ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * local_ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * local_ratio)
        if direction == "vertical":
            draw.line([(0, i), (w, i)], fill=(r, g, b))
        else:
            draw.line([(i, 0), (i, h)], fill=(r, g, b))


def draw_avatar(draw, x, y, size, color, letter, f):
    """Draw a circular avatar with initial letter."""
    draw.ellipse([x, y, x + size, y + size], fill=color)
    bbox = f.getbbox(letter)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x + (size - tw) // 2, y + (size - th) // 2 - 2), letter, fill=WHITE, font=f)


def text_width(f, text):
    bbox = f.getbbox(text)
    return bbox[2] - bbox[0]


def text_height(f, text):
    bbox = f.getbbox(text)
    return bbox[3] - bbox[1]


def wrap_text(text, f, max_width):
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if text_width(f, test) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def avatar_color_for_name(name):
    """Consistent avatar color based on name hash."""
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return AVATAR_COLORS[h % len(AVATAR_COLORS)]


def centered_text(draw, y, text, f, fill, width):
    tw = text_width(f, text)
    draw.text(((width - tw) // 2, y), text, fill=fill, font=f)


# ═══════════════════════════════════════════════
# 1. LOGO (800x800) — Premium KB monogram
# ═══════════════════════════════════════════════

def gen_logo():
    size = 800
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background gradient circle
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    for i in range(size // 2, 0, -1):
        ratio = 1 - (i / (size // 2))
        r = int(20 + (80 - 20) * ratio)
        g = int(40 + (100 - 40) * ratio)
        b = int(100 + (220 - 100) * ratio)
        a = 255
        cx, cy = size // 2, size // 2
        bg_draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(r, g, b, a))

    img = Image.alpha_composite(img, bg)
    draw = ImageDraw.Draw(img)

    # Subtle inner ring
    ring_r = size // 2 - 40
    cx, cy = size // 2, size // 2
    draw.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
                 outline=(255, 255, 255, 50), width=3)

    # KB text
    f_logo = font(DEJAVU_BOLD, 240)
    f_brand = font(DEJAVU_BOLD, 52)

    text = "KB"
    tw = text_width(f_logo, text)
    th = text_height(f_logo, text)
    x = (size - tw) // 2
    y = (size - th) // 2 - 50

    # Glow effect
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.text((x, y), text, fill=(100, 180, 255, 80), font=f_logo)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=15))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Shadow
    draw.text((x + 3, y + 3), text, fill=(0, 0, 0, 120), font=f_logo)
    # Main text
    draw.text((x, y), text, fill=WHITE, font=f_logo)

    # Brand name
    brand = BRAND.upper()
    btw = text_width(f_brand, brand)
    draw.text(((size - btw) // 2, y + th + 30), brand, fill=ACCENT_GOLD, font=f_brand)

    # Convert to RGB for saving
    final = Image.new("RGB", (size, size), (30, 50, 120))
    final.paste(img, mask=img.split()[3])
    final.save(OUT / "logo_800.png", quality=98)
    final.resize((400, 400), Image.LANCZOS).save(OUT / "logo_400.png", quality=98)
    print("✅ Logo generated (premium quality)")


# ═══════════════════════════════════════════════
# 2. BANNERS (1280x720) — Main channel posts
# ═══════════════════════════════════════════════

def gen_banner_welcome():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    gradient_fill(draw, w, h, [GRADIENT_START, GRADIENT_MID, GRADIENT_END])

    # Decorative elements
    for _ in range(30):
        x = random.randint(0, w)
        y = random.randint(0, h)
        r = random.randint(2, 6)
        alpha = random.randint(20, 60)
        draw.ellipse([x-r, y-r, x+r, y+r], fill=(255, 255, 255, alpha))

    # Accent bars
    draw.rectangle([0, 0, w, 5], fill=ACCENT_GOLD)
    draw.rectangle([0, h-5, w, h], fill=ACCENT_GOLD)

    f_title = font(DEJAVU_BOLD, 72)
    f_sub = font(DEJAVU, 38)
    f_feat = font(DEJAVU_BOLD, 28)
    f_cta = font(DEJAVU_BOLD, 36)

    centered_text(draw, 90, "KLIQBOOST", f_title, WHITE, w)
    centered_text(draw, 180, "Premium Ad Accounts for Serious Media Buyers", f_sub, (200, 210, 230), w)

    features = [
        ("No Spend Limits", ACCENT_GREEN),
        ("Free Replacements", ACCENT_GOLD),
        ("24h Delivery", (100, 181, 246)),
        ("Agency Access", (233, 30, 99)),
    ]
    box_w = 260
    gap = 25
    start_x = (w - (box_w * 4 + gap * 3)) // 2
    for i, (label, color) in enumerate(features):
        x = start_x + i * (box_w + gap)
        y = 310
        draw.rounded_rectangle((x, y, x + box_w, y + 130), radius=16, fill=(255, 255, 255, 15))
        draw.rounded_rectangle((x, y, x + box_w, y + 130), radius=16, outline=color, width=2)
        draw.rounded_rectangle((x, y, x + box_w, y + 5), radius=0, fill=color)
        tw = text_width(f_feat, label)
        draw.text((x + (box_w - tw) // 2, y + 50), label, fill=WHITE, font=f_feat)

    # CTA
    cta = "DM @georgekatis to get started"
    tw = text_width(f_cta, cta)
    cx = (w - tw) // 2
    draw.rounded_rectangle((cx - 40, 540, cx + tw + 40, 610), radius=14, fill=ACCENT_GOLD)
    draw.text((cx, 550), cta, fill=DARK, font=f_cta)

    centered_text(draw, 640, "t.me/kliqboost_media", font(DEJAVU, 26), (180, 190, 210), w)

    img.save(OUT / "banner_welcome.png", quality=98)
    print("✅ Welcome banner generated")


def gen_banner_pricing():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), DARK)
    draw = ImageDraw.Draw(img)

    # Header gradient
    for i in range(130):
        ratio = i / 130
        r = int(GRADIENT_START[0] + (GRADIENT_END[0] - GRADIENT_START[0]) * ratio)
        g = int(GRADIENT_START[1] + (GRADIENT_END[1] - GRADIENT_START[1]) * ratio)
        b = int(GRADIENT_START[2] + (GRADIENT_END[2] - GRADIENT_START[2]) * ratio)
        draw.line([(0, i), (w, i)], fill=(r, g, b))

    f_title = font(DEJAVU_BOLD, 56)
    f_header = font(DEJAVU_BOLD, 26)
    f_cell = font(DEJAVU, 26)
    f_price = font(DEJAVU_BOLD, 26)
    f_footer = font(DEJAVU, 24)

    centered_text(draw, 35, "PRICING OVERVIEW", f_title, WHITE, w)

    platforms = [
        ("Google Ads", "$50", "$100", "$800/mo"),
        ("Meta Ads", "$200/mo", "$450/mo", "$1,000/mo"),
        ("Bing Ads", "$100", "$300", "$1,000/mo"),
        ("TikTok Ads", "$80", "$200", "$600/mo"),
    ]
    headers = ["PLATFORM", "STARTER", "PRO", "ENTERPRISE"]
    col_w = [320, 240, 240, 280]
    start_x = (w - sum(col_w)) // 2
    y = 160

    # Header row
    x = start_x
    for i, header in enumerate(headers):
        draw.rounded_rectangle((x, y, x + col_w[i] - 6, y + 50), radius=8, fill=GRADIENT_END)
        tw = text_width(f_header, header)
        draw.text((x + (col_w[i] - tw) // 2, y + 12), header, fill=WHITE, font=f_header)
        x += col_w[i]

    for row_i, (platform, s, p, e) in enumerate(platforms):
        y_row = y + 65 + row_i * 70
        row_bg = (30, 41, 59) if row_i % 2 == 0 else (40, 53, 72)
        x = start_x
        vals = [platform, s, p, e]
        for col_i, val in enumerate(vals):
            draw.rounded_rectangle((x, y_row, x + col_w[col_i] - 6, y_row + 58), radius=8, fill=row_bg)
            f = f_cell if col_i == 0 else f_price
            color = WHITE if col_i == 0 else ACCENT_GREEN
            tw = text_width(f, val)
            draw.text((x + (col_w[col_i] - tw) // 2, y_row + 15), val, fill=color, font=f)
            x += col_w[col_i]

    centered_text(draw, 580, "All plans include free replacements + dedicated support", f_footer, ACCENT_GOLD, w)
    centered_text(draw, 620, "Payment: BTC | ETH | USDT | LTC", f_footer, (148, 163, 184), w)
    centered_text(draw, 660, "DM @georgekatis for custom packages", f_footer, (120, 140, 170), w)

    img.save(OUT / "banner_pricing.png", quality=98)
    print("✅ Pricing banner generated")


def gen_banner_platforms():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    gradient_fill(draw, w, h, [(15, 23, 42), (25, 40, 70)])

    f_title = font(DEJAVU_BOLD, 56)
    f_plat = font(DEJAVU_BOLD, 34)
    f_feat = font(DEJAVU, 22)

    centered_text(draw, 35, "PLATFORMS WE SUPPORT", f_title, WHITE, w)

    platforms = [
        ("Google Ads", (66, 133, 244), ["Unlimited spend", "Agency access"]),
        ("Meta Ads", (24, 119, 242), ["BM included", "No restrictions"]),
        ("TikTok Ads", (233, 30, 99), ["Fast approval", "All regions"]),
        ("Bing Ads", (0, 120, 212), ["Premium accounts", "Low competition"]),
        ("Taboola", (0, 87, 255), ["Native ads", "High CTR"]),
        ("Outbrain", (233, 83, 34), ["Content ads", "Scale fast"]),
    ]

    box_w = 360
    box_h = 190
    gap = 35
    cols = 3
    start_x = (w - (box_w * cols + gap * (cols - 1))) // 2
    start_y = 140

    for i, (name, color, feats) in enumerate(platforms):
        row = i // cols
        col = i % cols
        x = start_x + col * (box_w + gap)
        y = start_y + row * (box_h + gap)

        draw.rounded_rectangle((x, y, x + box_w, y + box_h), radius=18, fill=(30, 41, 59))
        draw.rounded_rectangle((x, y, x + box_w, y + box_h), radius=18, outline=color, width=3)
        # Color accent bar at top
        draw.rounded_rectangle((x + 2, y + 2, x + box_w - 2, y + 6), radius=0, fill=color)

        draw.text((x + 25, y + 25), name, fill=WHITE, font=f_plat)
        for j, feat in enumerate(feats):
            draw.text((x + 25, y + 80 + j * 35), f"✓ {feat}", fill=(148, 163, 184), font=f_feat)

    centered_text(draw, 630, "Need another platform? DM us — we source anything", font(DEJAVU, 26), ACCENT_GOLD, w)
    centered_text(draw, 670, "@georgekatis | t.me/kliqboost_media", font(DEJAVU, 22), (120, 140, 170), w)

    img.save(OUT / "banner_platforms.png", quality=98)
    print("✅ Platforms banner generated")


def gen_banner_stats():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), DARK)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, 4], fill=ACCENT_GOLD)

    f_title = font(DEJAVU_BOLD, 56)
    f_sub = font(DEJAVU, 34)
    f_val = font(DEJAVU_BOLD, 64)
    f_label = font(DEJAVU, 26)
    f_footer = font(DEJAVU_BOLD, 30)
    f_sm = font(DEJAVU, 22)

    centered_text(draw, 30, "RESULTS THAT SPEAK", f_title, WHITE, w)
    centered_text(draw, 105, "Our clients' numbers don't lie", f_sub, (148, 163, 184), w)

    stats = [
        ("500+", "Active Clients", ACCENT_GOLD),
        ("$2M+", "Monthly Spend", ACCENT_GREEN),
        ("99.5%", "Account Uptime", (100, 181, 246)),
        ("<24h", "Delivery Time", (233, 30, 99)),
    ]

    stat_w = 260
    gap = 30
    start_x = (w - (stat_w * 4 + gap * 3)) // 2
    y = 200

    for i, (value, label, color) in enumerate(stats):
        x = start_x + i * (stat_w + gap)
        draw.rounded_rectangle((x, y, x + stat_w, y + 260), radius=22, fill=(30, 41, 59))
        draw.rounded_rectangle((x, y, x + stat_w, y + 6), radius=0, fill=color)

        tw = text_width(f_val, value)
        draw.text((x + (stat_w - tw) // 2, y + 55), value, fill=color, font=f_val)

        tw = text_width(f_label, label)
        draw.text((x + (stat_w - tw) // 2, y + 165), label, fill=WHITE, font=f_label)

    centered_text(draw, 540, "0 bans in 90 days for Pro+ clients", f_footer, ACCENT_GREEN, w)
    centered_text(draw, 590, "Join 500+ media buyers who trust Kliqboost", f_sm, (148, 163, 184), w)
    centered_text(draw, 640, "DM @georgekatis | t.me/kliqboost_media", f_sm, (120, 140, 170), w)

    img.save(OUT / "banner_stats.png", quality=98)
    print("✅ Stats banner generated")


def gen_banner_cta():
    w, h = 1280, 720
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    gradient_fill(draw, w, h, [GRADIENT_END, GRADIENT_MID, GRADIENT_START])

    f_title = font(DEJAVU_BOLD, 68)
    f_sub = font(DEJAVU, 36)
    f_step = font(DEJAVU, 32)
    f_cta = font(DEJAVU_BOLD, 42)
    f_sm = font(DEJAVU, 22)

    centered_text(draw, 60, "Ready to Scale?", f_title, WHITE, w)
    centered_text(draw, 155, "Stop burning through personal accounts.", f_sub, (200, 210, 230), w)
    centered_text(draw, 205, "Get agency-level access today.", f_sub, (200, 210, 230), w)

    steps = [
        "1.  DM @georgekatis on Telegram",
        "2.  Tell us your platform & budget",
        "3.  Pay via crypto (BTC/ETH/USDT)",
        "4.  Start running ads within 24 hours",
    ]
    y = 310
    for step in steps:
        tw = text_width(f_step, step)
        draw.text(((w - tw) // 2, y), step, fill=WHITE, font=f_step)
        y += 50

    cta = "DM @georgekatis now"
    tw = text_width(f_cta, cta)
    cx = (w - tw) // 2
    draw.rounded_rectangle((cx - 50, 560, cx + tw + 50, 640), radius=18, fill=ACCENT_GOLD)
    draw.text((cx, 570), cta, fill=DARK, font=f_cta)

    centered_text(draw, 670, "t.me/kliqboost_media | @kliqboost_vouches", f_sm, (180, 190, 210), w)

    img.save(OUT / "banner_cta.png", quality=98)
    print("✅ CTA banner generated")


# ═══════════════════════════════════════════════
# 3. VOUCH SCREENSHOTS — Realistic TG chat format
# ═══════════════════════════════════════════════

def draw_tg_chat_screenshot(messages, chat_name, chat_subtitle, filename, buyer_name, buyer_username):
    """
    Generate a realistic Telegram dark-theme chat screenshot.

    messages: list of dicts with keys:
        - sender: "buyer" or "seller"
        - text: message text
        - time: timestamp string like "14:32"
        - read: bool (for seller messages, show double checkmarks)
    """
    w = 1080  # Phone-width screenshot
    # Calculate height based on messages
    f_msg = font(ROBOTO, 28)
    f_name = font(ROBOTO_MED, 28)
    f_time = font(ROBOTO, 20)
    f_header_name = font(ROBOTO_MED, 32)
    f_header_sub = font(ROBOTO, 22)
    f_reply = font(ROBOTO, 22)

    header_h = 90
    max_bubble_w = 680

    # Pre-calculate message heights
    msg_heights = []
    for msg in messages:
        lines = wrap_text(msg["text"], f_msg, max_bubble_w - 80)
        line_h = 36
        bubble_h = len(lines) * line_h + 45  # padding + timestamp row
        if msg.get("is_screenshot"):
            bubble_h += 320  # image placeholder
        msg_heights.append(bubble_h)

    total_msg_h = sum(msg_heights) + len(messages) * 14  # spacing between messages
    h = header_h + total_msg_h + 60  # top/bottom padding

    img = Image.new("RGB", (w, h), TG_BG)
    draw = ImageDraw.Draw(img)

    # ── Header bar ──
    draw.rectangle([0, 0, w, header_h], fill=TG_HEADER)
    # Back arrow
    draw.text((20, 30), "<", fill=TG_TEXT, font=font(DEJAVU_BOLD, 32))
    # Avatar
    color = avatar_color_for_name(buyer_name if chat_name == buyer_name else chat_name)
    draw_avatar(draw, 65, 18, 54, color, chat_name[0].upper(), font(DEJAVU_BOLD, 26))
    # Name & subtitle
    draw.text((135, 20), chat_name, fill=TG_TEXT, font=f_header_name)
    draw.text((135, 55), chat_subtitle, fill=TG_TEXT_DIM, font=f_header_sub)
    # Menu dots
    draw.text((w - 50, 30), ":", fill=TG_TEXT_DIM, font=font(DEJAVU_BOLD, 30))

    # ── Messages ──
    y = header_h + 20
    seller_name = "George | Kliqboost"

    for i, msg in enumerate(messages):
        is_out = msg["sender"] == "seller"
        lines = wrap_text(msg["text"], f_msg, max_bubble_w - 80)
        line_h = 36

        # Calculate bubble dimensions
        max_line_w = max(text_width(f_msg, line) for line in lines)
        time_str = msg["time"]
        time_w = text_width(f_time, time_str)
        check_w = 28 if is_out else 0
        min_w = max_line_w + 50
        last_line_w = text_width(f_msg, lines[-1]) if lines else 0

        # Check if time fits on last line
        time_total_w = time_w + check_w + 15
        if last_line_w + time_total_w + 30 < max_bubble_w - 40:
            bubble_w = max(min_w, last_line_w + time_total_w + 50)
        else:
            bubble_w = min_w

        bubble_w = min(bubble_w, max_bubble_w)
        bubble_w = max(bubble_w, time_total_w + 60)

        img_block_h = 0
        if msg.get("is_screenshot"):
            img_block_h = 300
            bubble_w = max(bubble_w, 520)

        bubble_h = len(lines) * line_h + 45 + img_block_h

        bubble_color = TG_BUBBLE_OUT if is_out else TG_BUBBLE_IN

        if is_out:
            bx = w - bubble_w - 25
        else:
            bx = 25

        # Draw bubble with rounded corners
        draw.rounded_rectangle(
            (bx, y, bx + bubble_w, y + bubble_h),
            radius=16,
            fill=bubble_color
        )

        # Sender name (for incoming messages in first appearance)
        name_offset = 0
        if not is_out and i == 0 or (not is_out and messages[i-1]["sender"] == "seller"):
            draw.text((bx + 18, y + 8), buyer_name, fill=TG_NAME, font=font(ROBOTO_MED, 24))
            name_offset = 5

        # Screenshot placeholder
        if msg.get("is_screenshot"):
            img_y = y + 15 + name_offset
            # Dark placeholder with icon
            draw.rounded_rectangle(
                (bx + 12, img_y, bx + bubble_w - 12, img_y + 280),
                radius=10,
                fill=(20, 28, 36)
            )
            # Simulated account screenshot content
            scr_x = bx + 30
            scr_y = img_y + 15
            f_scr = font(DEJAVU, 20)
            f_scr_b = font(DEJAVU_BOLD, 22)
            if msg.get("screenshot_type") == "account":
                draw.text((scr_x, scr_y), "Google Ads Dashboard", fill=(100, 181, 246), font=f_scr_b)
                draw.text((scr_x, scr_y + 35), "Account Status: Active", fill=ACCENT_GREEN, font=f_scr)
                draw.text((scr_x, scr_y + 65), "Spend Limit: Unlimited", fill=(200, 210, 220), font=f_scr)
                draw.text((scr_x, scr_y + 95), "Currency: USD", fill=(200, 210, 220), font=f_scr)
                draw.text((scr_x, scr_y + 130), "Campaigns: Ready to create", fill=(200, 210, 220), font=f_scr)
                draw.text((scr_x, scr_y + 170), "Payment: Agency billing", fill=(200, 210, 220), font=f_scr)
                draw.rounded_rectangle((scr_x, scr_y + 210, scr_x + 200, scr_y + 245), radius=6, fill=ACCENT_GREEN)
                draw.text((scr_x + 15, scr_y + 215), "Verified Active", fill=DARK, font=f_scr)
            elif msg.get("screenshot_type") == "payment":
                draw.text((scr_x, scr_y), "Transaction Confirmed", fill=ACCENT_GREEN, font=f_scr_b)
                draw.text((scr_x, scr_y + 35), "Amount: 0.0021 BTC", fill=(200, 210, 220), font=f_scr)
                draw.text((scr_x, scr_y + 65), "Status: Confirmed (3 confirmations)", fill=ACCENT_GREEN, font=f_scr)
                draw.text((scr_x, scr_y + 95), f"To: Kliqboost Wallet", fill=(200, 210, 220), font=f_scr)
                draw.text((scr_x, scr_y + 135), "━━━━━━━━━━━━━━━━━━━━━", fill=(60, 70, 80), font=f_scr)
                draw.text((scr_x, scr_y + 165), "Txn: 7f3a...b829", fill=(120, 140, 170), font=f_scr)
                draw.text((scr_x, scr_y + 200), "Block: #841,293", fill=(120, 140, 170), font=f_scr)

            text_start_y = img_y + 290
        else:
            text_start_y = y + 15 + name_offset

        # Message text
        for j, line in enumerate(lines):
            draw.text((bx + 18, text_start_y + j * line_h), line, fill=TG_TEXT, font=f_msg)

        # Timestamp + read receipts
        time_y = y + bubble_h - 28
        if is_out:
            time_x = bx + bubble_w - time_w - check_w - 20
            draw.text((time_x, time_y), time_str, fill=(130, 155, 180), font=f_time)
            if msg.get("read", True):
                draw.text((time_x + time_w + 5, time_y), "✓✓", fill=TG_GREEN, font=font(DEJAVU, 16))
            else:
                draw.text((time_x + time_w + 5, time_y), "✓✓", fill=(130, 155, 180), font=font(DEJAVU, 16))
        else:
            time_x = bx + bubble_w - time_w - 15
            draw.text((time_x, time_y), time_str, fill=(130, 155, 180), font=f_time)

        y += bubble_h + 12

    img.save(OUT / filename, quality=98)
    print(f"✅ Vouch screenshot generated: {filename}")
    return img


# ═══════════════════════════════════════════════
# Vouch conversations
# ═══════════════════════════════════════════════

VOUCH_CONVERSATIONS = [
    {
        "filename": "vouch_1.png",
        "buyer_name": "Alex",
        "buyer_username": "@alexkrypto",
        "chat_name": "Alex",
        "chat_subtitle": "last seen recently",
        "messages": [
            {"sender": "buyer", "text": "hey bro, you still selling google ads accounts?", "time": "14:22"},
            {"sender": "seller", "text": "Hey! Yes, we have Google Ads accounts in stock. Pro tier — unlimited spend, agency billing. $100 each.", "time": "14:23"},
            {"sender": "buyer", "text": "cool, i need 2 accounts for my finance campaigns. last provider got me banned in 3 days lol", "time": "14:24"},
            {"sender": "seller", "text": "We hear that a lot. Our accounts are agency-level with clean history. Free replacement if anything happens within 30 days.", "time": "14:25"},
            {"sender": "buyer", "text": "bet. sending btc now", "time": "14:27"},
            {"sender": "seller", "text": "Payment received! Here's your first account:", "time": "14:35"},
            {"sender": "seller", "text": "[Account screenshot]", "time": "14:35", "is_screenshot": True, "screenshot_type": "account"},
            {"sender": "buyer", "text": "bro this is clean af. account is active, no restrictions. you're legit 🔥", "time": "14:42"},
            {"sender": "seller", "text": "Glad you like it! Second account coming right up. DM anytime if you need more. 💪", "time": "14:43"},
        ],
    },
    {
        "filename": "vouch_2.png",
        "buyer_name": "Marcus",
        "buyer_username": "@marcus_media",
        "chat_name": "Marcus",
        "chat_subtitle": "online",
        "messages": [
            {"sender": "buyer", "text": "yo George, got my meta accounts yesterday. just wanted to say they're running smooth 👌", "time": "09:15"},
            {"sender": "seller", "text": "Great to hear Marcus! How's the spend going?", "time": "09:18"},
            {"sender": "buyer", "text": "pushed $8k through already, zero issues. approval rate is way better than my old provider", "time": "09:19"},
            {"sender": "buyer", "text": "gonna need 5 more accounts next week for my team. enterprise tier this time", "time": "09:20"},
            {"sender": "seller", "text": "Enterprise tier is $450/mo per account, includes BM access + unlimited ad sets. I'll reserve 5 for you. 🤝", "time": "09:22"},
            {"sender": "buyer", "text": "perfect. kliqboost is the real deal, been telling everyone in my mastermind about you guys", "time": "09:23"},
            {"sender": "seller", "text": "Appreciate the love! We take care of our long-term clients. Hit me up when you're ready to order. 🙏", "time": "09:25"},
        ],
    },
    {
        "filename": "vouch_3.png",
        "buyer_name": "Viktor",
        "buyer_username": "@vik_scale",
        "chat_name": "Viktor",
        "chat_subtitle": "last seen 2 minutes ago",
        "messages": [
            {"sender": "buyer", "text": "George, quick update — been running on your google accounts for 4 months now", "time": "20:10"},
            {"sender": "buyer", "text": "finance vertical, which usually gets banned in days. ZERO bans so far", "time": "20:10"},
            {"sender": "seller", "text": "That's what we like to hear! Our agency accounts handle sensitive verticals much better.", "time": "20:13"},
            {"sender": "buyer", "text": "one account did get flagged last month but you guys replaced it same day. that's what matters", "time": "20:14"},
            {"sender": "seller", "text": "Always. Free replacements, no questions asked. That's the Pro guarantee. ✅", "time": "20:15"},
            {"sender": "buyer", "text": "honestly the best provider I've used. tried 4 others before you and they were all trash", "time": "20:16"},
            {"sender": "buyer", "text": "vouch for @georgekatis — legit google ads provider, fast replacements, zero bs 💯", "time": "20:17"},
        ],
    },
    {
        "filename": "vouch_4.png",
        "buyer_name": "Daniel",
        "buyer_username": "@dan_affiliates",
        "chat_name": "Daniel",
        "chat_subtitle": "online",
        "messages": [
            {"sender": "buyer", "text": "hey, do you have tiktok ads accounts?", "time": "16:40"},
            {"sender": "seller", "text": "Hey Daniel! Yes, TikTok accounts available. $80 for basic, $200 for pro with agency access.", "time": "16:42"},
            {"sender": "buyer", "text": "need pro. running sweepstakes offers, need fast approval", "time": "16:43"},
            {"sender": "seller", "text": "Pro is perfect for that. Agency accounts get priority review. Sending BTC address now.", "time": "16:44"},
            {"sender": "buyer", "text": "sent. check wallet", "time": "16:50"},
            {"sender": "seller", "text": "Confirmed! Setting up your account now. Give me 20 min.", "time": "16:52", "is_screenshot": True, "screenshot_type": "payment"},
            {"sender": "seller", "text": "Account is ready! Login details sent in next message. 🚀", "time": "17:15"},
            {"sender": "buyer", "text": "logged in, everything looks good. already submitted my first campaign 🔥", "time": "17:25"},
            {"sender": "buyer", "text": "vouch! legit tiktok account from kliqboost. fast delivery and clean account ✅", "time": "17:26"},
        ],
    },
    {
        "filename": "vouch_5.png",
        "buyer_name": "Raj",
        "buyer_username": "@raj_ppc",
        "chat_name": "Raj",
        "chat_subtitle": "last seen recently",
        "messages": [
            {"sender": "buyer", "text": "hi, first time buyer here. saw your channel. are the accounts legit?", "time": "11:05"},
            {"sender": "seller", "text": "Hey Raj! Yes, 100% legit agency accounts. We've been operating for over a year with 500+ clients. Check our vouch channel: t.me/kliqboost_vouches", "time": "11:07"},
            {"sender": "buyer", "text": "ok looks good. i'll try one basic google account first, $50 right?", "time": "11:10"},
            {"sender": "seller", "text": "Correct. $50 for Basic Google Ads. Includes 30-day replacement warranty. Send to the BTC address I'm sharing now.", "time": "11:11"},
            {"sender": "buyer", "text": "done, sent $50 in btc", "time": "11:18"},
            {"sender": "seller", "text": "Got it! Account details incoming...", "time": "11:20"},
            {"sender": "buyer", "text": "received and logged in. account is active, no issues. thanks man!", "time": "11:35"},
            {"sender": "buyer", "text": "definitely ordering pro tier next. good service 👍", "time": "11:36"},
            {"sender": "seller", "text": "Anytime! Glad you're happy. Pro is a big upgrade — unlimited spend + priority support. Just DM when ready. 🙏", "time": "11:38"},
        ],
    },
    {
        "filename": "vouch_6.png",
        "buyer_name": "Tom",
        "buyer_username": "@tom_arb",
        "chat_name": "Tom",
        "chat_subtitle": "online",
        "messages": [
            {"sender": "buyer", "text": "George, quick vouch — been using kliqboost for my taboola + google combo and it's been smooth sailing", "time": "15:30"},
            {"sender": "seller", "text": "Thanks Tom! How long have you been running now?", "time": "15:33"},
            {"sender": "buyer", "text": "about 6 weeks. content arb setup. both accounts still clean, spending $2k/day combined", "time": "15:34"},
            {"sender": "buyer", "text": "previous provider couldn't keep accounts alive more than a week lol", "time": "15:35"},
            {"sender": "seller", "text": "That's the difference with agency-level accounts. They're built different. 💪", "time": "15:36"},
            {"sender": "buyer", "text": "100%. already referred 3 people to you. they all say the same — best in the game rn", "time": "15:37"},
            {"sender": "seller", "text": "Really appreciate the referrals! Means a lot. Always here if you or your people need anything. 🔥", "time": "15:38"},
        ],
    },
]


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  Generating {BRAND} Branding Images v2")
    print(f"  Premium Quality + Realistic Vouch Screenshots")
    print(f"{'='*50}\n")

    # 1. Logo
    gen_logo()

    # 2. Banners
    gen_banner_welcome()
    gen_banner_pricing()
    gen_banner_platforms()
    gen_banner_stats()
    gen_banner_cta()

    # 3. Vouch screenshots (realistic TG chat format)
    for conv in VOUCH_CONVERSATIONS:
        draw_tg_chat_screenshot(
            messages=conv["messages"],
            chat_name=conv["chat_name"],
            chat_subtitle=conv["chat_subtitle"],
            filename=conv["filename"],
            buyer_name=conv["buyer_name"],
            buyer_username=conv["buyer_username"],
        )

    print(f"\n{'='*50}")
    print(f"  All images saved to {OUT}")
    print(f"  Logo: logo_800.png, logo_400.png")
    print(f"  Banners: banner_welcome/pricing/platforms/stats/cta.png")
    print(f"  Vouches: vouch_1.png through vouch_6.png")
    print(f"  (Realistic TG chat screenshot format)")
    print(f"{'='*50}")
