#!/usr/bin/env python3
"""
Generate realistic Telegram vouch screenshots using HTML + Playwright.
V4: Uses real profile pictures (not colored initials), improved TG UI accuracy.
"""

import asyncio
import base64
from pathlib import Path

OUT = Path(__file__).parent
PICS = OUT / "profile_pics"


def _load_pic_b64(name: str) -> str:
    """Load a profile pic as base64 data URI."""
    jpg = PICS / f"{name}.jpg"
    if jpg.exists():
        return "data:image/jpeg;base64," + base64.b64encode(jpg.read_bytes()).decode()
    png = PICS / f"{name}.png"
    if png.exists():
        return "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()
    return ""


def tg_chat_html(messages, chat_name, chat_subtitle, buyer_pic_b64, seller_pic_b64, time_now="3:15 AM"):
    """Generate HTML that looks exactly like Telegram desktop dark theme with real profile pics."""

    msg_html = ""
    prev_sender = None

    for msg in messages:
        is_out = msg["sender"] == "seller"
        is_first_in_group = (prev_sender != msg["sender"])
        prev_sender = msg["sender"]

        bubble_class = "out" if is_out else "in"
        tail_class = "tail" if is_first_in_group else ""
        time_str = msg["time"]

        checks = '<span class="checks read">✓✓</span>' if is_out else ""

        name_html = ""
        if not is_out and is_first_in_group:
            name_html = f'<div class="sender-name">{chat_name}</div>'

        # Screenshot attachment
        attachment = ""
        if msg.get("is_screenshot"):
            stype = msg.get("screenshot_type", "account")
            if stype == "account":
                attachment = '''
                <div class="screenshot-attach">
                    <div class="screenshot-header">
                        <div class="screenshot-icon">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
                                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                            </svg>
                        </div>
                        <div class="screenshot-title">Google Ads</div>
                    </div>
                    <div class="screenshot-body">
                        <div class="screenshot-row">
                            <span class="screenshot-label">Account Status</span>
                            <span class="screenshot-value active">● Active</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">Spend Limit</span>
                            <span class="screenshot-value">Unlimited</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">Billing</span>
                            <span class="screenshot-value">Agency (Invoicing)</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">Currency</span>
                            <span class="screenshot-value">USD</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">Created</span>
                            <span class="screenshot-value">Mar 2026</span>
                        </div>
                    </div>
                </div>'''
            elif stype == "payment":
                attachment = '''
                <div class="screenshot-attach payment">
                    <div class="screenshot-header">
                        <div class="screenshot-icon btc">₿</div>
                        <div class="screenshot-title">Payment Confirmed</div>
                    </div>
                    <div class="screenshot-body">
                        <div class="screenshot-row">
                            <span class="screenshot-label">Status</span>
                            <span class="screenshot-value active">● Confirmed</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">Amount</span>
                            <span class="screenshot-value">0.0031 BTC</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">Confirmations</span>
                            <span class="screenshot-value">3/3</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">TX Hash</span>
                            <span class="screenshot-value mono">a8f2...c914</span>
                        </div>
                    </div>
                </div>'''

        text = msg["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        msg_html += f'''
        <div class="message {bubble_class} {tail_class}">
            {name_html}
            {attachment}
            <div class="text">{text}</div>
            <div class="meta">
                <span class="time">{time_str}</span>
                {checks}
            </div>
        </div>'''

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    background: #0E1621;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    width: 480px;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
}}

/* Status bar */
.status-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 16px;
    background: #17212B;
    color: #8B9DAF;
    font-size: 12px;
    height: 24px;
}}
.status-bar .time {{ font-weight: 500; }}
.status-bar .icons {{ display: flex; gap: 6px; align-items: center; font-size: 11px; }}
.status-bar .battery {{
    width: 22px; height: 10px;
    border: 1.5px solid #8B9DAF;
    border-radius: 2px;
    position: relative;
}}
.status-bar .battery::after {{
    content: '';
    position: absolute;
    right: -4px; top: 2px;
    width: 2px; height: 5px;
    background: #8B9DAF;
    border-radius: 0 1px 1px 0;
}}
.status-bar .battery-fill {{
    width: 72%; height: 100%;
    background: #8B9DAF;
    border-radius: 1px;
}}

/* Header */
.header {{
    display: flex;
    align-items: center;
    padding: 8px 12px;
    background: #17212B;
    border-bottom: 1px solid rgba(0,0,0,0.3);
    height: 56px;
}}
.header .back {{
    color: #6AB2F2;
    font-size: 24px;
    margin-right: 10px;
    font-weight: 300;
    line-height: 1;
}}
.header .avatar {{
    width: 42px; height: 42px;
    border-radius: 50%;
    margin-right: 12px;
    flex-shrink: 0;
    object-fit: cover;
}}
.header .info .name {{
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.01em;
}}
.header .info .subtitle {{
    color: #6AB2F2;
    font-size: 13px;
    margin-top: 1px;
}}
.header .info .subtitle.offline {{
    color: #8B9DAF;
}}
.header .dots {{
    margin-left: auto;
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 8px;
}}
.header .dots span {{
    width: 4px; height: 4px;
    background: #8B9DAF;
    border-radius: 50%;
    display: block;
}}

/* Chat area */
.chat {{
    padding: 10px 8px 6px;
    background: #0E1621;
    min-height: 200px;
}}

/* Messages */
.message {{
    max-width: 340px;
    margin: 2px 8px;
    padding: 7px 11px 4px;
    border-radius: 12px;
    position: relative;
    line-height: 1.35;
    word-wrap: break-word;
}}
.message.tail {{ margin-top: 6px; }}
.message.in {{
    background: #182533;
    border-radius: 12px;
    margin-right: auto;
    color: #F5F5F5;
}}
.message.in.tail {{
    border-top-left-radius: 4px;
}}
.message.out {{
    background: #2B5278;
    border-radius: 12px;
    margin-left: auto;
    color: #F5F5F5;
}}
.message.out.tail {{
    border-top-right-radius: 4px;
}}

.sender-name {{
    color: #6AB2F2;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 2px;
}}

.text {{
    font-size: 14.5px;
    line-height: 1.4;
}}

.meta {{
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 4px;
    margin-top: 2px;
    float: right;
    margin-left: 12px;
    position: relative;
    bottom: -2px;
}}
.time {{
    font-size: 11px;
    color: rgba(255,255,255,0.45);
}}
.checks {{
    font-size: 13px;
    color: rgba(255,255,255,0.35);
    letter-spacing: -4px;
    margin-left: 1px;
}}
.checks.read {{ color: #4DD0E1; }}

/* Screenshot attachments */
.screenshot-attach {{
    background: #1A2A3A;
    border-radius: 8px;
    margin: 4px 0 6px;
    padding: 10px;
    border-left: 3px solid #6AB2F2;
}}
.screenshot-attach.payment {{
    border-left-color: #4CAF50;
}}
.screenshot-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}}
.screenshot-icon {{
    width: 24px; height: 24px;
    display: flex; align-items: center; justify-content: center;
}}
.screenshot-icon svg {{ width: 20px; height: 20px; }}
.screenshot-icon.btc {{
    color: #F7931A;
    font-size: 18px;
    font-weight: bold;
}}
.screenshot-title {{
    color: #E0E0E0;
    font-size: 13px;
    font-weight: 600;
}}
.screenshot-body {{
    display: flex;
    flex-direction: column;
    gap: 5px;
}}
.screenshot-row {{
    display: flex;
    justify-content: space-between;
    font-size: 12.5px;
}}
.screenshot-label {{ color: #8B9DAF; }}
.screenshot-value {{ color: #D0D0D0; font-weight: 500; }}
.screenshot-value.active {{ color: #4CAF50; }}
.screenshot-value.mono {{ font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11.5px; }}

/* Input bar */
.input-bar {{
    display: flex;
    align-items: center;
    padding: 8px 12px;
    background: #17212B;
    border-top: 1px solid rgba(0,0,0,0.3);
    height: 48px;
    gap: 10px;
}}
.input-field {{
    flex: 1;
    background: transparent;
    color: #8B9DAF;
    font-size: 14px;
    padding: 6px 0;
}}
.attach, .mic {{
    color: #6AB2F2;
    font-size: 20px;
    padding: 0 4px;
}}
</style>
</head>
<body>

<div class="status-bar">
    <span class="time">{time_now}</span>
    <span class="icons">
        <span>LTE</span>
        <span>📶</span>
        <div class="battery"><div class="battery-fill"></div></div>
    </span>
</div>

<div class="header">
    <span class="back">‹</span>
    <img class="avatar" src="{buyer_pic_b64}" alt="">
    <div class="info">
        <div class="name">{chat_name}</div>
        <div class="subtitle {"offline" if "last seen" in chat_subtitle else ""}">{chat_subtitle}</div>
    </div>
    <div class="dots"><span></span><span></span><span></span></div>
</div>

<div class="chat">
{msg_html}
</div>

<div class="input-bar">
    <span class="attach">📎</span>
    <div class="input-field">Message</div>
    <span class="mic">🎤</span>
</div>

</body>
</html>'''


# ═══════════════════════════════════════════════
# Vouch conversations
# ═══════════════════════════════════════════════

CONVERSATIONS = [
    {
        "filename": "vouch_1.png",
        "chat_name": "Alex",
        "chat_subtitle": "last seen recently",
        "profile_pic": "alex",
        "time_now": "2:22 PM",
        "messages": [
            {"sender": "buyer", "text": "hey bro, you still selling google ads accounts?", "time": "2:22 PM"},
            {"sender": "seller", "text": "Hey! Yes we have Google Ads in stock. Pro tier — unlimited spend, agency billing. $100 each", "time": "2:23 PM"},
            {"sender": "buyer", "text": "cool, i need 2 for my finance campaigns. last provider got me banned in 3 days lol", "time": "2:24 PM"},
            {"sender": "seller", "text": "We hear that a lot. Our accounts are agency-level with clean history. Free replacement if anything happens within 30 days", "time": "2:25 PM"},
            {"sender": "buyer", "text": "bet. sending btc now", "time": "2:27 PM"},
            {"sender": "seller", "text": "Payment received! Here's your account:", "time": "2:35 PM", "is_screenshot": True, "screenshot_type": "account"},
            {"sender": "buyer", "text": "bro this is clean af. account is active, no restrictions. you're legit 🔥", "time": "2:42 PM"},
            {"sender": "seller", "text": "Glad you like it! Second one coming right up. DM anytime you need more 💪", "time": "2:43 PM"},
        ],
    },
    {
        "filename": "vouch_2.png",
        "chat_name": "Marcus",
        "chat_subtitle": "online",
        "profile_pic": "marcus",
        "time_now": "9:15 AM",
        "messages": [
            {"sender": "buyer", "text": "yo George, got my meta accounts yesterday. just wanted to say they're running smooth 👌", "time": "9:15 AM"},
            {"sender": "seller", "text": "Great to hear Marcus! How's the spend going?", "time": "9:18 AM"},
            {"sender": "buyer", "text": "pushed $8k through already, zero issues. approval rate is way better than my old provider", "time": "9:19 AM"},
            {"sender": "buyer", "text": "gonna need 5 more next week for my team. enterprise tier", "time": "9:20 AM"},
            {"sender": "seller", "text": "Enterprise is $450/mo per account, includes BM access + unlimited ad sets. I'll reserve 5 for you 🤝", "time": "9:22 AM"},
            {"sender": "buyer", "text": "perfect. kliqboost is the real deal, been telling everyone in my mastermind about you guys", "time": "9:23 AM"},
            {"sender": "seller", "text": "Appreciate the love! We take care of our long-term clients. Hit me up when ready 🙏", "time": "9:25 AM"},
        ],
    },
    {
        "filename": "vouch_3.png",
        "chat_name": "Viktor",
        "chat_subtitle": "last seen 2 min ago",
        "profile_pic": "viktor",
        "time_now": "8:10 PM",
        "messages": [
            {"sender": "buyer", "text": "George, quick update — been running on your google accounts for 4 months now", "time": "8:10 PM"},
            {"sender": "buyer", "text": "finance vertical, which usually gets banned in days. ZERO bans so far", "time": "8:10 PM"},
            {"sender": "seller", "text": "That's what we like to hear! Our agency accounts handle sensitive verticals much better", "time": "8:13 PM"},
            {"sender": "buyer", "text": "one account did get flagged last month but you guys replaced it same day. that's what matters", "time": "8:14 PM"},
            {"sender": "seller", "text": "Always. Free replacements, no questions asked. That's the Pro guarantee ✅", "time": "8:15 PM"},
            {"sender": "buyer", "text": "honestly the best provider I've used. tried 4 others before you and they were all trash", "time": "8:16 PM"},
            {"sender": "buyer", "text": "vouch for @georgekatis — legit google ads provider, fast replacements, zero bs 💯", "time": "8:17 PM"},
        ],
    },
    {
        "filename": "vouch_4.png",
        "chat_name": "Daniel",
        "chat_subtitle": "online",
        "profile_pic": "daniel",
        "time_now": "4:40 PM",
        "messages": [
            {"sender": "buyer", "text": "hey, do you have tiktok ads accounts?", "time": "4:40 PM"},
            {"sender": "seller", "text": "Hey Daniel! Yes, TikTok accounts available. $80 basic, $200 pro with agency access", "time": "4:42 PM"},
            {"sender": "buyer", "text": "need pro. running sweepstakes, need fast approval", "time": "4:43 PM"},
            {"sender": "seller", "text": "Pro is perfect for that. Agency accounts get priority review. Sending BTC address now", "time": "4:44 PM"},
            {"sender": "buyer", "text": "sent. check wallet", "time": "4:50 PM"},
            {"sender": "seller", "text": "Confirmed! Setting up your account, give me 20 min", "time": "4:52 PM", "is_screenshot": True, "screenshot_type": "payment"},
            {"sender": "seller", "text": "Account ready! Login details in next message 🚀", "time": "5:15 PM"},
            {"sender": "buyer", "text": "logged in, everything looks good. already submitted my first campaign 🔥", "time": "5:25 PM"},
            {"sender": "buyer", "text": "vouch! legit tiktok account, fast delivery, clean ✅", "time": "5:26 PM"},
        ],
    },
    {
        "filename": "vouch_5.png",
        "chat_name": "Raj",
        "chat_subtitle": "last seen recently",
        "profile_pic": "raj",
        "time_now": "11:05 AM",
        "messages": [
            {"sender": "buyer", "text": "hi, first time buyer here. saw your channel. are the accounts legit?", "time": "11:05 AM"},
            {"sender": "seller", "text": "Hey Raj! 100% legit agency accounts. 500+ clients, over a year operating. Check our vouches: t.me/kliqboost_vouches", "time": "11:07 AM"},
            {"sender": "buyer", "text": "ok looks good. i'll try one basic google account, $50 right?", "time": "11:10 AM"},
            {"sender": "seller", "text": "Correct. $50 for Basic Google Ads. 30-day replacement warranty. Sending BTC address", "time": "11:11 AM"},
            {"sender": "buyer", "text": "done, sent $50 in btc", "time": "11:18 AM"},
            {"sender": "seller", "text": "Got it! Account details incoming...", "time": "11:20 AM"},
            {"sender": "buyer", "text": "received and logged in. account is active, no issues. thanks man! 👍", "time": "11:35 AM"},
            {"sender": "buyer", "text": "definitely ordering pro tier next. good service", "time": "11:36 AM"},
            {"sender": "seller", "text": "Anytime! Glad you're happy. Pro is a big upgrade — unlimited spend + priority support. Just DM when ready 🙏", "time": "11:38 AM"},
        ],
    },
    {
        "filename": "vouch_6.png",
        "chat_name": "Tom",
        "chat_subtitle": "online",
        "profile_pic": "tom",
        "time_now": "3:30 PM",
        "messages": [
            {"sender": "buyer", "text": "George, quick vouch — been using kliqboost for my taboola + google combo, smooth sailing", "time": "3:30 PM"},
            {"sender": "seller", "text": "Thanks Tom! How long you been running?", "time": "3:33 PM"},
            {"sender": "buyer", "text": "about 6 weeks. content arb setup. both accounts still clean, $2k/day combined", "time": "3:34 PM"},
            {"sender": "buyer", "text": "previous provider couldn't keep accounts alive more than a week lol", "time": "3:35 PM"},
            {"sender": "seller", "text": "That's the difference with agency-level accounts. Built different 💪", "time": "3:36 PM"},
            {"sender": "buyer", "text": "100%. already referred 3 people to you. they all say same thing — best in the game rn", "time": "3:37 PM"},
            {"sender": "seller", "text": "Appreciate the referrals! Means a lot. Always here if you or your people need anything 🔥", "time": "3:38 PM"},
        ],
    },
]


async def render_vouches():
    from playwright.async_api import async_playwright

    # Load seller (George) profile pic
    seller_pic = _load_pic_b64("george_logo")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for conv in CONVERSATIONS:
            buyer_pic = _load_pic_b64(conv["profile_pic"])

            html = tg_chat_html(
                messages=conv["messages"],
                chat_name=conv["chat_name"],
                chat_subtitle=conv["chat_subtitle"],
                buyer_pic_b64=buyer_pic,
                seller_pic_b64=seller_pic,
                time_now=conv["time_now"],
            )

            html_path = OUT / f"_temp_{conv['filename']}.html"
            html_path.write_text(html, encoding="utf-8")

            page = await browser.new_page(
                viewport={"width": 480, "height": 900},
                device_scale_factor=2,
            )
            await page.goto(f"file://{html_path}")
            await page.wait_for_timeout(500)

            body_height = await page.evaluate("document.body.scrollHeight")
            await page.set_viewport_size({"width": 480, "height": body_height})
            await page.wait_for_timeout(300)

            await page.screenshot(
                path=str(OUT / conv["filename"]),
                full_page=True,
                type="png",
            )
            await page.close()
            html_path.unlink()

            from PIL import Image
            img = Image.open(OUT / conv["filename"])
            print(f"✅ {conv['filename']} — {conv['chat_name']} ({img.size[0]}x{img.size[1]}, {(OUT / conv['filename']).stat().st_size/1024:.0f}KB)")

        await browser.close()


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Generating Kliqboost Vouches v4")
    print("  HTML + Playwright + Real Profile Pictures")
    print("=" * 50 + "\n")

    asyncio.run(render_vouches())
    print("\n✅ All vouches generated with real profile pictures!")
