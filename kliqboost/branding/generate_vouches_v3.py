#!/usr/bin/env python3
"""
Generate realistic Telegram vouch screenshots using HTML + Playwright.
Renders pixel-perfect TG dark-theme chat UI in Chromium, then screenshots.
"""

import asyncio
import json
import random
from pathlib import Path

OUT = Path(__file__).parent

# ═══════════════════════════════════════════════
# TG Chat HTML Template
# ═══════════════════════════════════════════════

def tg_chat_html(messages, chat_name, chat_subtitle, buyer_avatar_color, time_now="3:15 AM"):
    """Generate HTML that looks exactly like Telegram desktop dark theme."""

    msg_html = ""
    prev_sender = None

    for i, msg in enumerate(messages):
        is_out = msg["sender"] == "seller"
        is_first_in_group = (prev_sender != msg["sender"])
        prev_sender = msg["sender"]

        bubble_class = "out" if is_out else "in"
        tail_class = "tail" if is_first_in_group else ""
        time_str = msg["time"]

        # Check marks for outgoing
        checks = ""
        if is_out:
            checks = '<span class="checks read">✓✓</span>'

        # Sender name for incoming (first in group)
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
                        <div class="screenshot-icon">G</div>
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
                        <div class="screenshot-title">Transaction Confirmed</div>
                    </div>
                    <div class="screenshot-body">
                        <div class="screenshot-row">
                            <span class="screenshot-label">Amount</span>
                            <span class="screenshot-value">0.0021 BTC (~$200)</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">Status</span>
                            <span class="screenshot-value active">Confirmed (3+)</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">TX Hash</span>
                            <span class="screenshot-value mono">7f3a8b...e829c4</span>
                        </div>
                        <div class="screenshot-row">
                            <span class="screenshot-label">Block</span>
                            <span class="screenshot-value mono">#841,293</span>
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

    seller_avatar_letter = "G"
    seller_avatar_color = "#3B82F6"

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
.status-bar .icons {{ display: flex; gap: 4px; align-items: center; }}
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
    width: 70%; height: 100%;
    background: #8B9DAF;
    border-radius: 1px;
}}

/* Header */
.header {{
    display: flex;
    align-items: center;
    padding: 8px 12px;
    background: #17212B;
    border-bottom: 1px solid #0E1621;
    height: 52px;
}}
.header .back {{
    color: #6AB2F2;
    font-size: 22px;
    margin-right: 12px;
    font-weight: 300;
}}
.header .avatar {{
    width: 40px; height: 40px;
    border-radius: 50%;
    background: {buyer_avatar_color};
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    font-weight: 500;
    margin-right: 12px;
    flex-shrink: 0;
}}
.header .info .name {{
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 500;
}}
.header .info .subtitle {{
    color: #8B9DAF;
    font-size: 13px;
}}
.header .menu {{
    margin-left: auto;
    color: #8B9DAF;
    font-size: 20px;
    cursor: pointer;
}}

/* Chat area */
.chat {{
    padding: 8px 8px;
    background: #0E1621;
    min-height: 200px;
}}

/* Messages */
.message {{
    max-width: 340px;
    margin: 2px 0;
    padding: 6px 10px 4px 10px;
    border-radius: 12px;
    position: relative;
    word-wrap: break-word;
    line-height: 1.35;
}}

.message.in {{
    background: #182533;
    margin-left: 8px;
    margin-right: auto;
    border-bottom-left-radius: 4px;
}}
.message.out {{
    background: #2B5278;
    margin-right: 8px;
    margin-left: auto;
    border-bottom-right-radius: 4px;
}}

.message.tail {{
    margin-top: 6px;
}}
.message.in.tail {{
    border-bottom-left-radius: 4px;
}}
.message.out.tail {{
    border-bottom-right-radius: 4px;
}}

.sender-name {{
    color: #6AB2F2;
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 2px;
}}

.text {{
    color: #F5F5F5;
    font-size: 14.5px;
    line-height: 1.4;
}}

.meta {{
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 3px;
    margin-top: 1px;
}}
.time {{
    color: #5B7B99;
    font-size: 11px;
}}
.checks {{
    font-size: 12px;
    color: #5B7B99;
}}
.checks.read {{
    color: #4FC3F7;
}}

/* Screenshot attachments */
.screenshot-attach {{
    background: #0D1822;
    border-radius: 8px;
    margin: 4px -2px 6px -2px;
    overflow: hidden;
    border: 1px solid #1C2A3A;
}}
.screenshot-header {{
    display: flex;
    align-items: center;
    padding: 10px 12px;
    background: #14202C;
    border-bottom: 1px solid #1C2A3A;
}}
.screenshot-icon {{
    width: 32px; height: 32px;
    border-radius: 8px;
    background: #4285F4;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    font-weight: 700;
    margin-right: 10px;
    flex-shrink: 0;
}}
.screenshot-icon.btc {{
    background: #F7931A;
    font-size: 18px;
}}
.screenshot-title {{
    color: #E0E0E0;
    font-size: 14px;
    font-weight: 600;
}}
.screenshot-body {{
    padding: 8px 12px;
}}
.screenshot-row {{
    display: flex;
    justify-content: space-between;
    padding: 5px 0;
    border-bottom: 1px solid #1A2636;
}}
.screenshot-row:last-child {{
    border-bottom: none;
}}
.screenshot-label {{
    color: #6B8299;
    font-size: 12.5px;
}}
.screenshot-value {{
    color: #C8D8E8;
    font-size: 12.5px;
    font-weight: 500;
}}
.screenshot-value.active {{
    color: #4ADE80;
}}
.screenshot-value.mono {{
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 11.5px;
    color: #8B9DAF;
}}

.screenshot-attach.payment .screenshot-header {{
    background: #1A1500;
    border-bottom-color: #2A2000;
}}

/* Input bar */
.input-bar {{
    display: flex;
    align-items: center;
    padding: 6px 8px;
    background: #17212B;
    border-top: 1px solid #0E1621;
    height: 44px;
}}
.input-bar .attach {{
    color: #6AB2F2;
    font-size: 20px;
    padding: 0 8px;
}}
.input-bar .input-field {{
    flex: 1;
    background: #242F3D;
    border: none;
    border-radius: 20px;
    padding: 8px 16px;
    color: #8B9DAF;
    font-size: 14px;
}}
.input-bar .mic {{
    color: #6AB2F2;
    font-size: 20px;
    padding: 0 8px;
}}
</style>
</head>
<body>

<div class="status-bar">
    <span class="time">{time_now}</span>
    <span class="icons">
        <span>LTE</span>
        <div class="battery"><div class="battery-fill"></div></div>
    </span>
</div>

<div class="header">
    <span class="back">‹</span>
    <div class="avatar">{chat_name[0].upper()}</div>
    <div class="info">
        <div class="name">{chat_name}</div>
        <div class="subtitle">{chat_subtitle}</div>
    </div>
    <span class="menu">⋮</span>
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
        "avatar_color": "#E91E63",
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
        "avatar_color": "#9C27B0",
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
        "avatar_color": "#FF9800",
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
        "avatar_color": "#00BCD4",
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
        "avatar_color": "#4CAF50",
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
        "avatar_color": "#F44336",
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

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for conv in CONVERSATIONS:
            html = tg_chat_html(
                messages=conv["messages"],
                chat_name=conv["chat_name"],
                chat_subtitle=conv["chat_subtitle"],
                buyer_avatar_color=conv["avatar_color"],
                time_now=conv["time_now"],
            )

            html_path = OUT / f"_temp_{conv['filename']}.html"
            html_path.write_text(html, encoding="utf-8")

            page = await browser.new_page(
                viewport={"width": 480, "height": 900},
                device_scale_factor=2,  # Retina for crisp rendering
            )
            await page.goto(f"file://{html_path}")
            await page.wait_for_timeout(300)

            # Get actual content height
            body_height = await page.evaluate("document.body.scrollHeight")
            await page.set_viewport_size({"width": 480, "height": body_height})
            await page.wait_for_timeout(200)

            await page.screenshot(
                path=str(OUT / conv["filename"]),
                full_page=True,
                type="png",
            )
            await page.close()
            html_path.unlink()  # cleanup temp file

            print(f"✅ {conv['filename']} — {conv['chat_name']} conversation")

        await browser.close()


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Generating Kliqboost Vouch Screenshots v3")
    print("  HTML + Playwright (pixel-perfect TG dark theme)")
    print("=" * 50 + "\n")

    asyncio.run(render_vouches())

    print(f"\n✅ All vouches saved to {OUT}")
    print("   vouch_1.png through vouch_6.png")
    print("   (Retina 2x rendering, real browser CSS)")
