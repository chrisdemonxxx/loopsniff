"""Standalone warming runner — launched as a detached background process."""
import asyncio
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from outreach.warming_engine import run_daily_warming

if __name__ == "__main__":
    asyncio.run(run_daily_warming())
