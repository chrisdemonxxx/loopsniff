"""
SMS-Activate API Client
Alternative to SMS-Man with better API accessibility
"""
import aiohttp
import asyncio
from typing import Optional, Dict, Any


class SMsActivateClient:
    """Client for SMS-Activate API integration"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://sms-activate.io/stubs/hands_api.php"
        self.session = None
        
    async def _get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session
    
    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_balance(self) -> float:
        """Get account balance"""
        session = await self._get_session()
        params = {"api_key": self.api_key, "action": "getBalance"}
        
        async with session.get(self.base_url, params=params) as resp:
            text = await resp.text()
            
            if text.startswith("ACCESS_BALANCE:"):
                balance = float(text.split(":")[1])
                return balance
            else:
                raise Exception(f"Error: {text}")
    
    async def get_number(
        self, 
        service: str, 
        country: str = "6"  # 6 = USA by default
    ) -> Dict[str, Any]:
        """
        Get phone number for service
        
        Service codes:
        - tg: Telegram
        - go: Google/Gmail
        - li: LinkedIn/Bing
        
        Country codes:
        - 1: Russia
        - 6: USA
        - 7: Ukraine
        - 13: UK
        - 23: Germany
        """
        session = await self._get_session()
        params = {
            "api_key": self.api_key,
            "action": "getNumber",
            "service": service,
            "country": country
        }
        
        async with session.get(self.base_url, params=params) as resp:
            text = await resp.text()
            
            if text.startswith("ACCESS_NUMBER:"):
                parts = text.split(":")
                order_id = int(parts[1])
                phone = parts[2]
                
                return {
                    "success": True,
                    "id": order_id,
                    "number": phone,
                    "raw": text
                }
            else:
                raise Exception(f"Error: {text}")
    
    async def get_code(self, order_id: int, timeout: int = 300) -> str:
        """Poll for verification code"""
        start_time = asyncio.get_event_loop().time()
        session = await self._get_session()
        
        while True:
            params = {
                "api_key": self.api_key,
                "action": "getStatus",
                "id": order_id
            }
            
            async with session.get(self.base_url, params=params) as resp:
                text = await resp.text()
                
                if text.startswith("STATUS_OK:"):
                    code = text.split(":")[1]
                    return code
                elif text == "STATUS_WAIT_CODE":
                    pass  # Keep waiting
                elif text == "STATUS_CANCEL":
                    raise Exception("Order cancelled")
                else:
                    raise Exception(f"Unknown status: {text}")
            
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                await self.cancel_order(order_id)
                raise TimeoutError(f"Code not received in {timeout}s")
            
            await asyncio.sleep(10)
    
    async def cancel_order(self, order_id: int):
        """Cancel order"""
        session = await self._get_session()
        params = {
            "api_key": self.api_key,
            "action": "setStatus",
            "id": order_id,
            "status": "8"  # 8 = cancel
        }
        async with session.get(self.base_url, params=params) as resp:
            await resp.text()
    
    async def activate_order(self, order_id: int):
        """Activate order (SMS received)"""
        session = await self._get_session()
        params = {
            "api_key": self.api_key,
            "action": "setStatus",
            "id": order_id,
            "status": "1"  # 1 = activate
        }
        async with session.get(self.base_url, params=params) as resp:
            await resp.text()
    
    async def get_verification_code(
        self,
        service: str,
        country: str = "6",
        timeout: int = 300
    ) -> tuple[str, str]:
        """Complete flow: get number and code"""
        print(f"    Requesting {service} number (country {country})...")
        number = await self.get_number(service, country)
        order_id = number['id']
        phone = number['number']
        print(f"    Got: {phone}, ID: {order_id}")
        
        try:
            print(f"    Waiting for code...")
            code = await self.get_code(order_id, timeout)
            await self.activate_order(order_id)
            print(f"    ✓ Code: {code}")
            return phone, code
        except Exception as e:
            print(f"    ✗ Error: {e}")
            raise


# Example usage
async def main():
    client = SMsActivateClient(api_key="YOUR_API_KEY")
    
    try:
        balance = await client.get_balance()
        print(f"Balance: ${balance}")
        
        phone, code = await client.get_verification_code("tg", "6")
        print(f"Phone: {phone}, Code: {code}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
