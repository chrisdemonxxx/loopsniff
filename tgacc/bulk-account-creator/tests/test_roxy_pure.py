"""
Simple POC Test - Roxy Browser Profile Creation
Minimal test that creates a browser profile without proxy purchase
"""
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.roxy_client import RoxyBrowserClient, generate_roxy_profile


async def test_roxy_poc():
    """
    Test Roxy Browser profile creation (no proxy required)
    
    This validates:
    1. Roxy Browser API connectivity
    2. Profile creation
    3. Profile start/stop
    
    You can manually add proxy later in Roxy Browser UI
    """
    
    print("=" * 70)
    print("ROXY BROWSER POC TEST")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize client
    roxy_client = RoxyBrowserClient(
        api_key=os.getenv("ROXY_API_KEY"),
        api_host=os.getenv("ROXY_API_HOST", "http://127.0.0.1:50000")
    )
    
    try:
        # STEP 1: Create profile
        print("[STEP 1/3] Creating Roxy Browser profile...")
        profile_config = generate_roxy_profile("telegram", "us", None)  # No proxy for now
        
        profile = await roxy_client.create_profile(profile_config)
        profile_id = profile['id']
        
        print(f"    ✓ Profile ID: {profile_id}")
        print(f"    ✓ Name: {profile['name']}")
        print(f"    ✓ Platform: {profile_config.get('platform', 'N/A')}")
        print(f"    ✓ Browser: {profile_config.get('browser', 'N/A')}")
        print(f"    ✓ Locale: {profile_config.get('locale', 'N/A')}")
        print()
        
        # STEP 2: Start profile
        print("[STEP 2/3] Starting profile...")
        started = await roxy_client.start_profile(profile_id)
        
        print(f"    ✓ Status: {started['status']}")
        print(f"    ✓ WebSocket: {started.get('ws_endpoint', 'N/A')}")
        print(f"    ✓ Profile is now running")
        print()
        
        # STEP 3: Stop profile
        print("[STEP 3/3] Stopping profile...")
        await roxy_client.stop_profile(profile_id)
        print(f"    ✓ Profile stopped")
        
        # SUCCESS
        print()
        print("=" * 70)
        print("✓✓✓ ROXY BROWSER POC SUCCESSFUL ✓✓✓")
        print("=" * 70)
        print()
        print("Summary:")
        print(f"  • Profile ID: {profile_id}")
        print(f"  • Profile Name: {profile['name']}")
        print(f"  • Status: Created and tested successfully")
        print()
        print("Next Steps:")
        print("  1. Open Roxy Browser desktop app")
        print(f"  2. Find profile: {profile['name']}")
        print("  3. Edit profile to add proxy (optional)")
        print("  4. Start the profile")
        print("  5. Navigate to https://web.telegram.org")
        print("  6. Get SMS from SMS-Man (manual)")
        print("  7. Complete signup")
        print()
        print("Manual SMS Steps:")
        print("  1. Login: https://b2b.sms-man.com")
        print("  2. Request: Service=Telegram, Country=USA")
        print("  3. Copy phone number")
        print("  4. Wait for code")
        print("  5. Enter in Telegram Web")
        print()
        print("Notes:")
        print("  • Profile created without proxy (can add in UI)")
        print("  • SMS verification must be done manually")
        print("  • Once manual flow works, automate with MCP Playwright")
        print()
        
        return {
            "success": True,
            "profile_id": profile_id,
            "profile_name": profile['name'],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print()
        print("=" * 70)
        print("✗✗✗ TEST FAILED ✗✗✗")
        print("=" * 70)
        print()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("Troubleshooting:")
        print("  1. Check Roxy API key: {}".format(os.getenv("ROXY_API_KEY")[:10] + "..."))
        print("  2. Verify Roxy MCP server is running")
        print("  3. Check Roxy Browser desktop app installed")
        print()
        
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def main():
    """Run POC test"""
    result = await test_roxy_poc()
    
    # Save result
    import json
    with open("roxy_poc_result.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"Result saved to: roxy_p12_result.json")
    
    return result


if __name__ == "__main__":
    asyncio.run(main())
