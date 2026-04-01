"""Run the campaign monitoring dashboard."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "outreach.campaign_dashboard:app",
        host="0.0.0.0",
        port=8050,
        reload=True,
    )
