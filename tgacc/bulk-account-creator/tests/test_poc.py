"""
POC Test Script
Tests single account creation for Telegram, Gmail, and Bing
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import AccountCreator


async def test_telegram_poc():
    """Test Telegram account creation POC"""
    print("=" * 60)
    print("TELEGRAM POC TEST")
    print("=" * 60)
    
    creator = AccountCreator(
        sms_api_key=os.getenv("SMS_MAN_API_KEY", "YOUR_KEY"),
        octo_token=os.getenv("OCTO_TOKEN", "YOUR_TOKEN"),
        proxy_api_key=os.getenv("PROXY_SELLER_KEY", "YOUR_KEY")
    )
    
    result = await creator.create_telegram_account(country="us")
    
    if result['status'] == "success":
        print("\n✓ TELEGRAM POC SUCCESS")
        print(f"  Profile ID: {result['profile_id']}")
        print(f"  Phone: {result['phone']}")
        print(f"  Proxy: {result['proxy_ip']}")
        return True
    else:
        print("\n✗ TELEGRAM POC FAILED")
        print(f"  Error: {result['error']}")
        return False


async def test_gmail_poc():
    """Test Gmail account creation POC"""
    print("\n" + "=" * 60)
    print("GMAIL POC TEST (Not yet implemented)")
    print("=" * 60)
    print("Gmail automation requires additional implementation")
    print("See: browsers/gmail_bot.py")
    return False


async def test_bing_poc():
    """Test Bing/Microsoft account creation POC"""
    print("\n" + "=" * 60)
    print("BING POC TEST (Not yet implemented)")
    print("=" * 60)
    print("Bing automation requires additional implementation")
    print("See: browsers/bing_bot.py")
    return False


async def main():
    """Run all POC tests"""
    print("\n" + "=" * 60)
    print("BULK ACCOUNT CREATOR - POC TEST SUITE")
    print("=" * 60)
    
    results = {
        "telegram": await test_telegram_poc(),
        "gmail": await test_gmail_poc(),
        "bing": await test_bing_poc()
    }
    
    print("\n" + "=" * 60)
    print("POC SUMMARY")
    print("=" * 60)
    
    for service, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{service.upper()}: {status}")
    
    total_success = sum(results.values())
    total_tests = len(results)
    
    print(f"\nTotal: {total_success}/{total_tests} passed")
    
    if total_success > 0:
        print("\n✓✓✓ POC PHASE SUCCESSFUL ✓✓✓")
        print("Ready to proceed to bulk implementation")
    else:
        print("\n✗✗✗ POC PHASE FAILED ✗✗✗")
        print("Debug and retry required")
    
    return results


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    asyncio.run(main())
