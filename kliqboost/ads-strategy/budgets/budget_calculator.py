#!/usr/bin/env python3
"""
Telegram Ads ROI Calculator

Calculates expected returns based on campaign parameters.
Usage: python budget_calculator.py
"""

def calculate_roi(
    daily_budget_ton: float = 15.0,
    ton_usd_rate: float = 3.50,
    cpm_ton: float = 0.5,
    ctr_pct: float = 0.4,
    join_rate_pct: float = 30.0,
    bot_interaction_rate_pct: float = 20.0,
    qualification_rate_pct: float = 15.0,
    close_rate_pct: float = 10.0,
    client_ltv_usd: float = 5000.0,
    campaign_days: int = 30,
):
    """Calculate full-funnel ROI for Telegram Ads campaign."""

    daily_budget_usd = daily_budget_ton * ton_usd_rate
    total_budget_usd = daily_budget_usd * campaign_days
    total_budget_ton = daily_budget_ton * campaign_days

    cpm_usd = cpm_ton * ton_usd_rate
    daily_impressions = (daily_budget_ton / cpm_ton) * 1000
    total_impressions = daily_impressions * campaign_days

    total_clicks = total_impressions * (ctr_pct / 100)
    total_joins = total_clicks * (join_rate_pct / 100)
    total_bot_interactions = total_joins * (bot_interaction_rate_pct / 100)
    total_qualified_leads = total_bot_interactions * (qualification_rate_pct / 100)
    total_clients = total_qualified_leads * (close_rate_pct / 100)
    total_revenue = total_clients * client_ltv_usd
    roas = total_revenue / total_budget_usd if total_budget_usd > 0 else 0

    cost_per_click = total_budget_usd / total_clicks if total_clicks > 0 else 0
    cost_per_join = total_budget_usd / total_joins if total_joins > 0 else 0
    cost_per_lead = total_budget_usd / total_qualified_leads if total_qualified_leads > 0 else 0
    cost_per_client = total_budget_usd / total_clients if total_clients > 0 else 0

    print("=" * 60)
    print("  TELEGRAM ADS ROI CALCULATOR")
    print("=" * 60)
    print(f"\n{'INPUT PARAMETERS':^60}")
    print("-" * 60)
    print(f"  Daily Budget:          {daily_budget_ton:.1f} TON (${daily_budget_usd:.2f})")
    print(f"  Campaign Duration:     {campaign_days} days")
    print(f"  TON/USD Rate:          ${ton_usd_rate:.2f}")
    print(f"  CPM Bid:               {cpm_ton:.2f} TON (${cpm_usd:.2f})")
    print(f"  Expected CTR:          {ctr_pct:.1f}%")
    print(f"  Join Rate:             {join_rate_pct:.0f}%")
    print(f"  Bot Interaction Rate:  {bot_interaction_rate_pct:.0f}%")
    print(f"  Qualification Rate:    {qualification_rate_pct:.0f}%")
    print(f"  Close Rate:            {close_rate_pct:.0f}%")
    print(f"  Client LTV:            ${client_ltv_usd:,.0f}")

    print(f"\n{'FUNNEL PROJECTIONS':^60}")
    print("-" * 60)
    print(f"  Total Budget:          {total_budget_ton:.0f} TON (${total_budget_usd:,.0f})")
    print(f"  Total Impressions:     {total_impressions:,.0f}")
    print(f"  Total Clicks:          {total_clicks:,.0f}")
    print(f"  Channel Joins:         {total_joins:,.0f}")
    print(f"  Bot Interactions:      {total_bot_interactions:,.0f}")
    print(f"  Qualified Leads:       {total_qualified_leads:,.1f}")
    print(f"  New Clients:           {total_clients:,.1f}")

    print(f"\n{'COST METRICS':^60}")
    print("-" * 60)
    print(f"  Cost per Click:        ${cost_per_click:.2f}")
    print(f"  Cost per Join:         ${cost_per_join:.2f}")
    print(f"  Cost per Lead:         ${cost_per_lead:.2f}")
    print(f"  Cost per Client:       ${cost_per_client:,.0f}")

    print(f"\n{'ROI ANALYSIS':^60}")
    print("-" * 60)
    print(f"  Total Revenue:         ${total_revenue:,.0f}")
    print(f"  Total Cost:            ${total_budget_usd:,.0f}")
    print(f"  Net Profit:            ${total_revenue - total_budget_usd:,.0f}")
    print(f"  ROAS:                  {roas:.1f}x")
    print("=" * 60)

    return {
        "total_budget_usd": total_budget_usd,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_joins": total_joins,
        "total_qualified_leads": total_qualified_leads,
        "total_clients": total_clients,
        "total_revenue": total_revenue,
        "roas": roas,
        "cost_per_lead": cost_per_lead,
        "cost_per_client": cost_per_client,
    }


if __name__ == "__main__":
    print("\n📊 PHASE 1: DISCOVERY (14 days, conservative)")
    calculate_roi(
        daily_budget_ton=15, campaign_days=14,
        ctr_pct=0.3, join_rate_pct=25, bot_interaction_rate_pct=15,
        qualification_rate_pct=10, close_rate_pct=5,
    )

    print("\n\n📊 PHASE 2: VALIDATION (14 days, optimized)")
    calculate_roi(
        daily_budget_ton=30, campaign_days=14,
        ctr_pct=0.5, join_rate_pct=30, bot_interaction_rate_pct=20,
        qualification_rate_pct=15, close_rate_pct=8,
    )

    print("\n\n📊 PHASE 3: SCALE (30 days, full speed)")
    calculate_roi(
        daily_budget_ton=50, campaign_days=30,
        ctr_pct=0.5, join_rate_pct=35, bot_interaction_rate_pct=25,
        qualification_rate_pct=20, close_rate_pct=10,
    )
