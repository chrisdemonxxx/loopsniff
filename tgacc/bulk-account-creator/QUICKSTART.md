# Quick Start Guide - POC Execution

## Overview
This guide walks you through running the Proof of Concept (POC) to create 1 Telegram account using the bulk account creator system.

## Prerequisites

### 1. API Keys Required

You need to obtain API keys from three services:

#### SMS-Man (SMS Verification)
- **Website**: https://sms-man.com
- **Sign up**: Create account at https://b2b.sms-man.com
- **Get API key**: Dashboard → API Settings
- **Cost**: ~$0.10-0.50 per SMS
- **Minimum balance**: $5 recommended for testing

#### Octo Browser (Anti-Detect Browser)
- **Website**: https://octobrowser.net
- **Sign up**: Create free account (10 profiles free)
- **Get API token**: Dashboard → API → Generate Token
- **Cost**: Free tier (10 profiles), then $9/month
- **Note**: RoxyBrowser is an alternative with similar API

#### Proxy-Seller (Proxy Service)
- **Website**: https://proxy-seller.com
- **Sign up**: Create account
- **Get API key**: Dashboard → API Settings
- **Cost**: ~$0.75-2 per residential proxy
- **Minimum**: Buy 1-2 proxies for testing

### 2. System Requirements

```bash
# Check Python version
python3 --version  # Need Python 3.10+

# Check pip
pip3 --version
```

## Installation Steps

### Step 1: Clone/Navigate to Project
```bash
cd /home/cjs/tgacc/bulk-account-creator
```

### Step 2: Install Dependencies
```bash
pip3 install -r requirements.txt
```

### Step 3: Install Playwright Browsers
```bash
playwright install
playwright install-deps  # Install system dependencies
```

### Step 4: Configure API Keys
```bash
# Copy example env file
cp .env.example .env

# Edit with your keys
nano .env  # or use your preferred editor
```

Update `.env` with your actual API keys:
```
SMS_MAN_API_KEY=your_actual_key_here
OCTO_TOKEN=your_actual_token_here
PROXY_SELLER_KEY=your_actual_key_here
```

### Step 5: Verify Configuration
```bash
# Test API connections
python3 -c "
import asyncio
from core.sms_client import SMSManClient
from core.octo_client import OctoBrowserClient
from core.proxy_client import ProxySellerClient
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    sms = SMSManClient(os.getenv('SMS_MAN_API_KEY'))
    octo = OctoBrowserClient(os.getenv('OCTO_TOKEN'))
    proxy = ProxySellerClient(os.getenv('PROXY_SELLER_KEY'))
    
    balance = await sms.get_balance()
    print(f'SMS-Man Balance: ${balance}')
    
    proxies = await proxy.get_proxy_list()
    print(f'Proxy count: {len(proxies)}')
    
    profiles = await octo.list_profiles(limit=5)
    print(f'Octo profiles: {len(profiles)}')

asyncio.run(test())
"
```

## Running the POC Test

### Option 1: Run Full POC Suite
```bash
cd /home/cjs/tgacc/bulk-account-creator
python3 tests/test_poc.py
```

This will attempt to create 1 Telegram account (Gmail and Bing are placeholders for future implementation).

### Option 2: Run Single Test
```bash
python3 -c "
import asyncio
import os
from dotenv import load_dotenv
from core.orchestrator import AccountCreator

load_dotenv()

async def run_poc():
    creator = AccountCreator(
        sms_api_key=os.getenv('SMS_MAN_API_KEY'),
        octo_token=os.getenv('OCTO_TOKEN'),
        proxy_api_key=os.getenv('PROXY_SELLER_KEY')
    )
    
    result = await creator.create_telegram_account(country='us')
    print('\\nResult:', result)
    return result

asyncio.run(run_poc())
"
```

## Expected Output

### Success Case:
```
============================================================
TELEGRAM POC TEST
============================================================
[*] Starting Telegram account creation for us
[1/5] Acquiring proxy...
    ✓ Proxy: 1.2.3.4:8080
[2/5] Creating browser profile...
    ✓ Profile created: 12345
[3/5] Starting browser...
    ✓ Browser started on port 9222
[4/5] Automating Telegram signup...
    Requesting SMS number...
    Got number: +1234567890, waiting for code...
    Waiting for verification code: 12345
    ✓ Successfully logged in
[5/5] Saving session...
    ✓ Profile stopped

✓ TELEGRAM POC SUCCESS
  Profile ID: 12345
  Phone: +1234567890
  Proxy: 1.2.3.4

============================================================
POC SUMMARY
============================================================
TELEGRAM: ✓ PASS
GMAIL: ✗ FAIL (Not implemented)
BING: ✗ FAIL (Not implemented)

Total: 1/3 passed

✓✓✓ POC PHASE SUCCESSFUL ✓✓✓
Ready to proceed to bulk implementation
```

### Failure Case:
```
[*] Starting Telegram account creation for us
[1/5] Acquiring proxy...
    ✗ Error: No US proxy found and purchase failed

✗ TELEGRAM POC FAILED
  Error: Failed to create proxy order

✗✗✗ POC PHASE FAILED ✗✗✗
Debug and retry required
```

## Troubleshooting

### Common Issues:

#### 1. "API Key Invalid"
```
Solution: Double-check API keys in .env file
Verify keys work by testing individual clients
```

#### 2. "Playwright Not Installed"
```bash
Solution: Run: playwright install && playwright install-deps
```

#### 3. "SMS Timeout"
```
Solution: 
- Try different country (uk, ca instead of us)
- Increase timeout: timeout=600 in create_telegram_account()
- Check SMS-Man balance
```

#### 4. "Proxy Connection Failed"
```
Solution:
- Verify proxy is active in Proxy-Seller dashboard
- Check proxy type (use 'resident' not 'datacenter')
- Ensure auth credentials are correct
```

#### 5. "Browser Launch Failed"
```
Solution:
- Check Octo Browser desktop app is running
- Verify API token is valid
- Check profile limits (free tier = 10 profiles)
```

## Success Criteria

The POC is considered successful if:

✓ SMS number acquired from SMS-Man
✓ Browser profile created in Octo Browser
✓ Proxy connection successful
✓ Telegram web page loads
✓ Phone number entered successfully
✓ SMS code received and entered
✓ Account created (can see chat list or profile setup)
✓ Browser session saved

## Next Steps After POC Success

Once POC succeeds:

1. **Verify Account**: Login to Telegram Web with created credentials
2. **Test Persistence**: Stop and restart profile, verify session persists
3. **Scale to Bulk**: Implement `bulk_creator.py` for batch creation
4. **Add Gmail/Bing**: Implement automation scripts for other platforms
5. **Monitor & Optimize**: Track success rates, optimize fingerprints

## Next Steps After POC Failure

If POC fails:

1. **Check Logs**: Review error messages carefully
2. **Test Components Individually**:
   ```bash
   # Test SMS-Man only
   python3 -c "from core.sms_client import SMSManClient; ..."
   
   # Test Octo Browser only
   python3 -c "from core.octo_client import OctoBrowserClient; ..."
   
   # Test Proxy-Seller only
   python3 -c "from core.proxy_client import ProxySellerClient; ..."
   ```
3. **Fix Issues**: Update code based on failures
4. **Retry**: Run POC again

## Cost Estimate for POC

| Service | Cost |
|---------|------|
| SMS-Man (1 SMS) | $0.10-0.50 |
| Proxy-Seller (1 residential) | $0.75-2.00 |
| Octo Browser (free tier) | $0.00 |
| **Total** | **$0.85-2.50** |

## Support & Documentation

- **SMS-Man Docs**: https://b2b.sms-man.com/technical
- **Octo Browser Docs**: https://docs.octobrowser.net
- **Proxy-Seller Docs**: https://docs.proxy-seller.com
- **Implementation Plan**: See IMPLEMENTATION_PLAN.md for full details

---

**Good luck with your POC!** 🚀
