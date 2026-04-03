"""
Octo Browser API Client
Manages anti-detect browser profiles for account creation
"""
import aiohttp
from typing import Optional, Dict, Any, List


class OctoBrowserClient:
    """Client for Octo Browser API integration"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.octobrowser.net/1.0"
        self.headers = {"Authorization": f"Bearer {token}"}
        
    async def create_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new browser profile
        
        Args:
            profile_data: Dict with profile settings:
                - name: Profile name
                - os: Operating system (win, mac, linux, android, ios)
                - browserName: Browser (chrome, firefox, edge)
                - userAgent: Custom user agent string
                - resolution: Screen resolution (e.g., "1920x1080")
                - language: Language locale (e.g., "en-US")
                - timezone: Timezone (e.g., "America/New_York")
                - proxy: Proxy configuration dict
                - cookies: Optional cookies array
                - extensions: Optional extensions array
        
        Returns:
            Profile data including 'id'
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/profiles"
            async with session.post(url, json=profile_data, headers=self.headers) as resp:
                return await resp.json()
    
    async def start_profile(self, profile_id: int) -> Dict[str, Any]:
        """
        Start a browser profile (launches the browser)
        
        Args:
            profile_id: Profile ID from create_profile
        
        Returns:
            Dict with 'status', 'debugPort' for CDP connection
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/profiles/{profile_id}/start"
            async with session.post(url, headers=self.headers) as resp:
                return await resp.json()
    
    async def stop_profile(self, profile_id: int):
        """Stop a running profile"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/profiles/{profile_id}/stop"
            async with session.post(url, headers=self.headers) as resp:
                await resp.json()
    
    async def delete_profile(self, profile_id: int):
        """Delete a profile permanently"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/profiles/{profile_id}"
            async with session.delete(url, headers=self.headers) as resp:
                await resp.json()
    
    async def update_profile(self, profile_id: int, update_data: Dict[str, Any]):
        """Update profile settings"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/profiles/{profile_id}"
            async with session.patch(url, json=update_data, headers=self.headers) as resp:
                return await resp.json()
    
    async def list_profiles(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List all profiles
        
        Args:
            limit: Max results (default: 100)
            offset: Pagination offset (default: 0)
        
        Returns:
            List of profile dicts
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/profiles"
            params = {"limit": limit, "offset": offset}
            async with session.get(url, params=params, headers=self.headers) as resp:
                data = await resp.json()
                return data.get('profiles', [])
    
    async def get_profile(self, profile_id: int) -> Dict[str, Any]:
        """Get single profile details"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/profiles/{profile_id}"
            async with session.get(url, headers=self.headers) as resp:
                return await resp.json()
    
    def get_cdp_url(self, debug_port: int) -> str:
        """
        Build Chrome DevTools Protocol WebSocket URL
        
        Args:
            debug_port: Port from start_profile response
        
        Returns:
            WebSocket URL for CDP connection
        """
        return f"ws://localhost:{debug_port}"


# Helper function to generate profile settings
def generate_telegram_profile(
    country: str = "us",
    proxy_config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Generate optimal profile settings for Telegram account creation
    
    Args:
        country: Target country code
        proxy_config: Proxy configuration from Proxy-Seller
    
    Returns:
        Profile data dict ready for create_profile
    """
    import random
    
    # Randomize fingerprint
    os_choices = ["win", "mac", "linux"]
    browser_choices = ["chrome", "firefox", "edge"]
    resolutions = ["1920x1080", "1366x768", "1440x900", "2560x1440"]
    
    # Country-specific settings
    country_config = {
        "us": {"language": "en-US", "timezone": "America/New_York"},
        "uk": {"language": "en-GB", "timezone": "Europe/London"},
        "ca": {"language": "en-CA", "timezone": "America/Toronto"},
        "au": {"language": "en-AU", "timezone": "Australia/Sydney"},
        "de": {"language": "de-DE", "timezone": "Europe/Berlin"},
    }.get(country, {"language": "en-US", "timezone": "America/New_York"})
    
    profile = {
        "name": f"telegram-{country}-{random.randint(1000, 9999)}",
        "os": random.choice(os_choices),
        "browserName": random.choice(browser_choices),
        "resolution": random.choice(resolutions),
        "language": country_config["language"],
        "timezone": country_config["timezone"],
        "userAgent": "",  # Auto-generated based on OS/browser
        "proxy": proxy_config if proxy_config else {},
    }
    
    return profile


# Example usage
async def main():
    client = OctoBrowserClient(token="YOUR_API_TOKEN")
    
    # List existing profiles
    profiles = await client.list_profiles(limit=10)
    print(f"Found {len(profiles)} profiles")
    
    # Create new profile
    profile_data = generate_telegram_profile("us", {
        "type": "http",
        "host": "1.2.3.4",
        "port": 8080,
        "username": "user",
        "password": "pass"
    })
    
    new_profile = await client.create_profile(profile_data)
    print(f"Created profile: {new_profile['id']}")
    
    # Start profile
    started = await client.start_profile(new_profile['id'])
    print(f"Started on port: {started['debugPort']}")
    
    # Get CDP URL for automation
    cdp_url = client.get_cdp_url(started['debugPort'])
    print(f"CDP URL: {cdp_url}")
    
    # Stop profile when done
    await client.stop_profile(new_profile['id'])


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
