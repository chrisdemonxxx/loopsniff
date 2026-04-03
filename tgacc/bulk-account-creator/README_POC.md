# Run POC Test with Roxy Browser MCP

This script tests the complete flow for creating a Telegram account using:
- **SMS-Man**: Phone verification
- **Proxy-Seller**: Residential proxy
- **Roxy Browser**: Anti-detect browser (via MCP)

## Usage

```bash
cd /home/cjs/tgacc/bulk-account-creator
python3 tests/test_poc_roxy.py
```

## What it does:

1. ✓ Checks SMS-Man balance
2. ✓ Acquires residential proxy from Proxy-Seller
3. ✓ Creates Roxy Browser profile with unique fingerprint
4. ✓ Starts browser profile
5. ✓ Requests SMS verification code
6. ✓ Prepares for Telegram signup automation

## Expected Output:

```
======================================================================
TELEGRAM ACCOUNT CREATION - POC TEST
======================================================================
Started: 2026-03-23 10:30:00

[STEP 1/6] Checking SMS-Man balance...
    ✓ Balance: $50.00

[STEP 2/6] Acquiring residential proxy...
    ✓ Proxy: 1.2.3.4:8080
    ✓ Country: US
    ✓ Type: resident

[STEP 3/6] Creating Roxy Browser profile...
    ✓ Profile ID: roxy_1234567890
    ✓ Name: telegram-us-abc12345

[STEP 4/6] Starting browser profile...
    ✓ Status: running
    ✓ Endpoint: ws://127.0.0.1:9222

[STEP 5/6] Requesting SMS verification code...
    Service: telegram
    Country: us
    ✓ Phone: +1234567890
    ✓ Code: 12345
    ✓ SMS received successfully

[STEP 6/6] Automating Telegram signup...
    ✓ Browser automation ready (MCP tools available)
    ✓ SMS verification complete
    ✓ Profile created in Roxy Browser
    ✓ Profile stopped

======================================================================
✓✓✓ POC TEST SUCCESSFUL ✓✓✓
======================================================================

Summary:
  • Profile ID: roxy_1234567890
  • Phone: +1234567890
  • Verification Code: 12345
  • Proxy: 1.2.3.4:8080
  • Country: us
  • SMS Cost: ~$0.10-0.50
  • Proxy Cost: ~$0.75-2.00

Next Steps:
  1. Manual test: Use Roxy Browser to complete Telegram signup
  2. Verify account can login
  3. Automate browser flow with MCP Playwright tools
  4. Scale to bulk creation

Result saved to: poc_result.json
```

## Manual Verification:

After the POC test succeeds, you can manually verify by:

1. Open Roxy Browser desktop app
2. Find the created profile (telegram-us-*)
3. Start the profile
4. Navigate to https://web.telegram.org
5. Enter the phone number from the test
6. Enter the verification code
7. Complete signup
8. Verify you can access Telegram

## Automation with MCP:

To fully automate the browser flow, use the RoxyBrowser MCP Playwright tools:

```python
# Example: Navigate to Telegram Web
await page.goto("https://web.telegram.org")

# Fill phone number
await page.fill("input[type='tel']", phone_number)

# Submit
await page.click("button[type='submit']")

# Wait for code input
await page.wait_for_selector("input[placeholder*='code']")

# Enter code
await page.fill("input[placeholder*='code']", verification_code)

# Submit code
await page.click("button[type='submit']")
```

## Costs:

- **SMS**: ~$0.10-0.50 (charged by SMS-Man)
- **Proxy**: ~$0.75-2.00 (charged by Proxy-Seller)
- **Browser**: Free (Roxy Browser free tier)
- **Total**: ~$0.85-2.50 per account

## Success Criteria:

✓ SMS balance checked
✓ Proxy acquired (or purchased)
✓ Browser profile created
✓ SMS code received
✓ Ready for automation

If all steps complete without error → **POC SUCCESS**

## Troubleshooting:

### "SMS timeout"
- Try different country (uk, ca, de)
- Increase timeout in code
- Check SMS-Man balance

### "No proxy available"
- Purchase new proxy (automatic in script)
- Try different country
- Check Proxy-Seller dashboard

### "Roxy Browser not responding"
- Ensure MCP server is running
- Check API key in .env
- Verify Roxy Browser desktop app is installed

## Next Steps After Success:

1. **Automate browser flow** using MCP Playwright tools
2. **Test account persistence** (stop/start profile)
3. **Verify login works** after 24 hours
4. **Scale to bulk** (10, 50, 100 accounts)
5. **Add Gmail & Bing** support

---

**Ready to run?** Execute: `python3 tests/test_poc_roxy.py`
