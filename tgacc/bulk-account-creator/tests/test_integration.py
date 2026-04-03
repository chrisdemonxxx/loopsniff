"""
Minimal POC Test - Proxy + Browser Integration
Tests Proxy-Seller and Roxy Browser without SMS dependency
"""
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.proxy_client import ProxySellerClient
from core.roxy_client import RoxyBrowserClient, generate_roxy_profile


async def test_proxy_browser_integration():
    """
    Test Proxy-Seller + Roxy Browser integration
    
    This validates:
    1. Proxy acquisition from Proxy-Seller
    2. Browser profile creation in Roxy
    3. Profile start/stop functionality
    
    SMS verification can be done manually afterwards
    """
    
    print("=" * 70)
    print("PROXY + BROWSER INTEGRATION TEST")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Initialize clients
    proxy_client = ProxySellerClient(api_key=os.getenv("PROXY_SELLER_KEY"))
    roxy_client = RoxyBrowserClient(
        api_key=os.getenv("ROXY_API_KEY"),
        api_host=os.getenv("ROXY_API_HOST", "http://127.0.0.1:50000")
    )
    
    country = "us"
    
    try:
        # STEP 1: Get proxy
        print("[STEP 1/3] Acquiring residential proxy from Proxy-Seller...")
        proxy = await proxy_client.get_proxy_by_country(country, "resident")
        
        if not proxy:
            print(f"    No {country} proxy found, purchasing...")
            try:
                order = await proxy_client.create_order(
                    proxy_type="resident",
                    count=1,
                    country=country,
                    duration=30
                )
                print(f"    Order placed: {order.get('orderNumber', 'N/A')}")
                
                auth = await proxy_client.get_auth(order['orderNumber'])
                proxy = {**order, **auth}
                print(f"    ✓ Proxy purchased successfully")
            except Exception as e:
                print(f"    ✗ Purchase failed: {e}")
                print(f"    Using existing proxy or skipping...")
                # Try to get any available proxy
                all_proxies = await proxy_client.get_proxy_list()
                if all_proxies:
                    proxy = all_proxies[0]
                    print(f"    ✓ Using fallback proxy: {proxy['ip']}")
                else:
                    raise Exception("No proxies available")
        
        print(f"    ✓ Proxy IP: {proxy['ip']}:{proxy['port']}")
        print(f"    ✓ Type: {proxy.get('type', 'N/A')}")
        print(f"    ✓ Country: {proxy.get('country', 'N/A')}")
        print()
        
        # STEP 2: Create Roxy Browser profile
        print("[STEP 2/3] Creating Roxy Browser profile...")
        proxy_config = proxy_client.format_proxy_config(proxy)
        profile_config = generate_roxy_profile("telegram", country, proxy_config)
        
        profile = await roxy_client.create_profile(profile_config)
        profile_id = profile['id']
        
        print(f"    ✓ Profile ID: {profile_id}")
        print(f"    ✓ Name: {profile['name']}")
        print(f"    ✓ Platform: {profile_config.get('platform', 'N/A')}")
        print(f"    ✓ Browser: {profile_config.get('browser', 'N/A')}")
        print()
        
        # STEP 3: Start and stop profile
        print("[STEP 3/3] Testing profile start/stop...")
        started = await roxy_client.start_profile(profile_id)
        
        print(f"    ✓ Profile started")
        print(f"    ✓ Status: {started['status']}")
        print(f"    ✓ WebSocket: {started.get('ws_endpoint', 'N/A')}")
        
        # Stop profile
        await roxy_client.stop_profile(profile_id)
        print(f"    ✓ Profile stopped")
        
        # SUCCESS
        print()
        print("=" * 70)
        print("✓✓✓ INTEGRATION TEST SUCCESSFUL ✓✓✓")
        print("=" * 70)
        print()
        print("Summary:")
        print(f"  • Profile ID: {profile_id}")
        print(f"  • Proxy: {proxy['ip']}:{proxy['port']}")
        print(f"  • Country: {country}")
        print(f"  • Browser: Roxy Browser (anti-detect)")
        print()
        print("Next Steps:")
        print("  1. Open Roxy Browser desktop app")
        print(f"  2. Find profile: {profile['name']}")
        print("  3. Start the profile manually")
        print("  4. Navigate to https://web.telegram.org")
        print("  5. Get SMS from SMS-Man dashboard manually")
        print("  6. Complete Telegram signup")
        print("  7. Verify account works")
        print()
        print("SMS-Man Manual Steps:")
        print("  1. Login: https://b2b.sms-man.com")
        print("  2. Balance: Check dashboard")
        print("  3. Get number: Service=Telegram, Country=USA")
        print("  4. Copy phone number")
        print("  5. Wait for code in dashboard")
        print("  6. Copy verification code")
        print()
        
        return {
            "success": True,
            "profile_id": profile_id,
            "profile_name": profile['name'],
            "proxy_ip": proxy['ip'],
            "proxy_port": proxy['port'],
            "country": country,
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
        print("  1. Check Proxy-Seller API key")
        print("  2. Verify proxies available in dashboard")
        print("  3. Check Roxy Browser MCP is running")
        print("  4. Verify Roxy API key")
        print()
        
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def main():
    """Run integration test"""
    result = await test_proxy_browser_integration()
    
    # Save result
    import json
    with open("integration_test_result.json", "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"Result saved to: integration_test_result.json")
    
    return result


if __name__ == "__main__":
    asyncio.run(main())
