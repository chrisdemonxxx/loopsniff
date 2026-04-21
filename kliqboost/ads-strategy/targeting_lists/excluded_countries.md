# Country Exclusion Notes

## Default Exclusions (Telegram Platform Enforced)

The following countries are **automatically excluded** by Telegram Ads platform:
- 🇷🇺 **Russian Federation** — Will not be shown
- 🇺🇦 **Ukraine** — Will not be shown
- 🇮🇱 **Israel** — Will not be shown
- 🇵🇸 **Palestine** — Will not be shown

> ⚠️ These exclusions are platform-level and CANNOT be overridden.

## Impact on Our Strategy

### Problem
~90% of our scraped channels have Russian-language audiences, many with RU/UA users.
When targeting these channels, ads will only be shown to subscribers who are NOT in excluded countries.

### Implication
- Russian-language media buyers who are based outside RU/UA (diaspora) WILL see ads
- This includes CIS media buyers in: Kazakhstan, Georgia, Turkey, UAE, Thailand, Bali, Portugal, etc.
- Many top media buyers have relocated from RU/UA — they're still in these channels but in non-excluded geos
- English-language channels are unaffected by these exclusions

### Strategy Adjustments
1. **Don't worry too much** — Many media buyers in RU channels are actually based abroad
2. **Monitor impression delivery** — If you get very low impressions on RU channels, the audience may be too concentrated in excluded countries
3. **Prioritize channels with international audiences** — Channels with EN content or mixed RU/EN tend to have more globally distributed audiences
4. **Add English ad sets** — Use `adset_06_broad_awareness.md` to reach non-RU audiences

### Recommended Additional Exclusions (Optional)
Consider excluding countries with very low commercial value for your business:
- Countries where agency ad accounts aren't needed
- Countries with very low purchasing power
- Set these in the Telegram Ads interface if available via geo-targeting

## Best Geo Targets for Agency Ad Accounts
| Priority | Region | Languages | Notes |
|----------|--------|-----------|-------|
| P0 | CIS diaspora (UAE, Turkey, Thailand, Georgia) | RU | Relocated media buyers, high spend |
| P1 | Western Europe (UK, DE, NL) | EN | Agency market, high LTV |
| P2 | US/Canada | EN | Largest ad market |
| P3 | LATAM (Brazil, Mexico) | ES/PT | Growing affiliate market |
| P4 | South Asia (India) | EN | High volume, lower LTV |
