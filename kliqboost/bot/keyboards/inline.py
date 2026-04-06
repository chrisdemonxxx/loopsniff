from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("btn_services"), callback_data="menu:services"),
            InlineKeyboardButton(text=t("btn_pricing"), callback_data="menu:pricing"),
        ],
        [
            InlineKeyboardButton(text=t("btn_case_studies"), callback_data="menu:cases"),
            InlineKeyboardButton(text=t("btn_faq"), callback_data="menu:faq"),
        ],
        [
            InlineKeyboardButton(text=t("btn_talk_manager"), callback_data="menu:order"),
            InlineKeyboardButton(text=t("btn_language"), callback_data="menu:lang"),
        ],
    ])


def services_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("svc_google"), callback_data="svc:google")],
        [InlineKeyboardButton(text=t("svc_meta"), callback_data="svc:meta")],
        [InlineKeyboardButton(text=t("svc_taboola"), callback_data="svc:taboola")],
        [InlineKeyboardButton(text=t("svc_outbrain"), callback_data="svc:outbrain")],
        [InlineKeyboardButton(text=t("svc_mediago"), callback_data="svc:mediago")],
        [InlineKeyboardButton(text=t("svc_campaign"), callback_data="svc:campaign")],
        [InlineKeyboardButton(text=t("svc_rental"), callback_data="svc:rental")],
        [InlineKeyboardButton(text=t("btn_back_main"), callback_data="menu:main")],
    ])


def service_detail_kb(t, svc_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("btn_see_pricing"), callback_data=f"price:{svc_key}"),
            InlineKeyboardButton(text=t("btn_order_now"), callback_data="menu:order"),
        ],
        [InlineKeyboardButton(text=t("btn_back"), callback_data="menu:services")],
    ])


def pricing_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Google Ads", callback_data="price:google")],
        [InlineKeyboardButton(text="Meta Ads", callback_data="price:meta")],
        [InlineKeyboardButton(text="Taboola", callback_data="price:taboola")],
        [InlineKeyboardButton(text="Outbrain", callback_data="price:outbrain")],
        [InlineKeyboardButton(text="Mediago", callback_data="price:mediago")],
        [InlineKeyboardButton(text=t("svc_campaign"), callback_data="price:campaign")],
        [InlineKeyboardButton(text=t("svc_rental"), callback_data="price:rental")],
        [InlineKeyboardButton(text=t("btn_bundle_deals"), callback_data="price:bundle")],
        [InlineKeyboardButton(text=t("btn_back_main"), callback_data="menu:main")],
    ])


def pricing_detail_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_order_now"), callback_data="menu:order")],
        [InlineKeyboardButton(text=t("btn_back"), callback_data="menu:pricing")],
    ])


def case_studies_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("case_crypto_btn"), callback_data="case:crypto")],
        [InlineKeyboardButton(text=t("case_nutra_btn"), callback_data="case:nutra")],
        [InlineKeyboardButton(text=t("case_finance_btn"), callback_data="case:finance")],
        [InlineKeyboardButton(text=t("case_sweeps_btn"), callback_data="case:sweeps")],
        [InlineKeyboardButton(text=t("btn_back_main"), callback_data="menu:main")],
    ])


def case_detail_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_get_results"), callback_data="menu:order")],
        [InlineKeyboardButton(text=t("btn_back"), callback_data="menu:cases")],
    ])


def faq_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("faq_1_btn"), callback_data="faq:1")],
        [InlineKeyboardButton(text=t("faq_2_btn"), callback_data="faq:2")],
        [InlineKeyboardButton(text=t("faq_3_btn"), callback_data="faq:3")],
        [InlineKeyboardButton(text=t("faq_4_btn"), callback_data="faq:4")],
        [InlineKeyboardButton(text=t("faq_5_btn"), callback_data="faq:5")],
        [InlineKeyboardButton(text=t("faq_6_btn"), callback_data="faq:6")],
        [InlineKeyboardButton(text=t("faq_7_btn"), callback_data="faq:7")],
        [InlineKeyboardButton(text=t("faq_8_btn"), callback_data="faq:8")],
        [InlineKeyboardButton(text=t("btn_back_main"), callback_data="menu:main")],
    ])


def faq_detail_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_back"), callback_data="menu:faq")],
    ])


def language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        ],
        [InlineKeyboardButton(text="🔙 Back / Назад", callback_data="menu:main")],
    ])


def order_platform_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("order_google"), callback_data="order:plat:Google"),
            InlineKeyboardButton(text=t("order_meta"), callback_data="order:plat:Meta"),
        ],
        [
            InlineKeyboardButton(text=t("order_taboola"), callback_data="order:plat:Taboola"),
            InlineKeyboardButton(text=t("order_outbrain"), callback_data="order:plat:Outbrain"),
        ],
        [
            InlineKeyboardButton(text=t("order_mediago"), callback_data="order:plat:Mediago"),
            InlineKeyboardButton(text=t("order_multiple"), callback_data="order:plat:Multiple"),
        ],
    ])


def order_niche_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("order_finance"), callback_data="order:niche:Finance"),
            InlineKeyboardButton(text=t("order_crypto"), callback_data="order:niche:Crypto"),
        ],
        [
            InlineKeyboardButton(text=t("order_nutra"), callback_data="order:niche:Nutra"),
            InlineKeyboardButton(text=t("order_trading"), callback_data="order:niche:Trading"),
        ],
        [
            InlineKeyboardButton(text=t("order_sweepstakes"), callback_data="order:niche:Sweepstakes"),
            InlineKeyboardButton(text=t("order_other"), callback_data="order:niche:Other"),
        ],
    ])


def order_budget_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("order_budget_1"), callback_data="order:budget:< $1k"),
            InlineKeyboardButton(text=t("order_budget_2"), callback_data="order:budget:$1k-$5k"),
        ],
        [
            InlineKeyboardButton(text=t("order_budget_3"), callback_data="order:budget:$5k-$10k"),
            InlineKeyboardButton(text=t("order_budget_4"), callback_data="order:budget:$10k-$50k"),
        ],
        [
            InlineKeyboardButton(text=t("order_budget_5"), callback_data="order:budget:$50k+"),
        ],
    ])


def order_timing_kb(t) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("order_asap"), callback_data="order:timing:ASAP"),
            InlineKeyboardButton(text=t("order_this_week"), callback_data="order:timing:This week"),
        ],
        [
            InlineKeyboardButton(text=t("order_this_month"), callback_data="order:timing:This month"),
            InlineKeyboardButton(text=t("order_exploring"), callback_data="order:timing:Just exploring"),
        ],
    ])


# ── Checkout flow keyboards ─────────────────────────────────────────────

def checkout_ready_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Ready to Order", callback_data="checkout:start")],
    ])


def checkout_confirm_kb(order_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm Order", callback_data=f"checkout:confirm:{order_code}")],
        [
            InlineKeyboardButton(text="✏️ Modify", callback_data=f"checkout:modify:{order_code}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"checkout:cancel:{order_code}"),
        ],
    ])


def payment_method_kb(order_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₿ Bitcoin (BTC)", callback_data=f"pay:BTC:{order_code}")],
        [InlineKeyboardButton(text="Ξ Ethereum (ETH)", callback_data=f"pay:ETH:{order_code}")],
        [InlineKeyboardButton(text="💲 USDT (ERC-20)", callback_data=f"pay:USDT:{order_code}")],
    ])


def payment_sent_kb(order_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I've Sent Payment", callback_data=f"checkout:sent:{order_code}")],
        [InlineKeyboardButton(text="❌ Cancel Order", callback_data=f"checkout:cancel:{order_code}")],
    ])


def admin_verify_kb(order_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"admin:approve:{order_code}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"admin:reject:{order_code}"),
        ],
    ])
