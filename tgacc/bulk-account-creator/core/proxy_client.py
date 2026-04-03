"""
Proxy-Seller API Client — v1 endpoint variant.
Reference: https://docs.proxy-seller.com/
"""
import aiohttp
from typing import Optional, Dict, Any, List

from loguru import logger

# alpha-2 → alpha-3 country code mapping (common countries)
_A2_TO_A3 = {
    "us": "USA", "gb": "GBR", "uk": "GBR", "ca": "CAN", "au": "AUS",
    "de": "DEU", "fr": "FRA", "nl": "NLD", "it": "ITA", "es": "ESP",
    "br": "BRA", "in": "IND", "jp": "JPN", "kr": "KOR", "cn": "CHN",
    "ru": "RUS", "ua": "UKR", "pl": "POL", "cz": "CZE", "ro": "ROU",
    "bg": "BGR", "tr": "TUR", "mx": "MEX", "ar": "ARG", "co": "COL",
    "cl": "CHL", "se": "SWE", "no": "NOR", "fi": "FIN", "dk": "DNK",
    "at": "AUT", "ch": "CHE", "be": "BEL", "pt": "PRT", "ie": "IRL",
    "hk": "HKG", "sg": "SGP", "my": "MYS", "th": "THA", "id": "IDN",
    "ph": "PHL", "vn": "VNM", "za": "ZAF", "ke": "KEN", "ng": "NGA",
    "eg": "EGY", "ge": "GEO", "am": "ARM", "kz": "KAZ", "lv": "LVA",
    "lt": "LTU", "ee": "EST", "bd": "BGD", "il": "ISR",
}


def _to_alpha3(code: str) -> str:
    """Convert 2-letter country code to 3-letter (alpha-3). Pass-through if already 3+."""
    code = code.strip().lower()
    if len(code) <= 2:
        return _A2_TO_A3.get(code, code.upper())
    return code.upper()


class ProxySellerError(Exception):
    """Error from Proxy-Seller API."""
    pass


class ProxySellerClient:
    """Async client for the Proxy-Seller personal API v1.

    Base URL pattern::

        https://proxy-seller.com/personal/api/v1/{API_KEY}/{endpoint}
    """

    BASE = "https://proxy-seller.com/personal/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    # ── session management ───────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── low-level request ────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
    ) -> Any:
        session = await self._get_session()
        url = f"{self.BASE}/{self.api_key}/{endpoint}"

        if method == "GET":
            async with session.get(url, params=params) as resp:
                return await self._handle_response(resp)
        else:
            async with session.post(url, json=json_body) as resp:
                return await self._handle_response(resp)

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> Any:
        text = await resp.text()
        if resp.status != 200:
            raise ProxySellerError(f"HTTP {resp.status}: {text[:300]}")
        try:
            data = await resp.json(content_type=None)
        except Exception:
            raise ProxySellerError(f"Non-JSON response: {text[:300]}")

        if isinstance(data, dict) and data.get("status") == "error":
            errors = data.get("errors", [])
            msg = errors[0].get("message", str(errors)) if errors else str(data)
            raise ProxySellerError(msg)
        return data

    # ── reference / discovery ────────────────────────────────────────────

    async def get_reference(self, proxy_type: str = "resident") -> Dict:
        """Get available countries, periods, and pricing for a proxy type.

        ``proxy_type``: ipv4 | ipv6 | mobile | isp | resident | mix | mix_isp

        Returns the ``items`` dict from the API (contains ``country``, ``period``,
        ``tarifs``, ``target`` depending on type).
        """
        resp = await self._request("GET", f"reference/list/{proxy_type}")
        if isinstance(resp, dict):
            data = resp.get("data", resp)
            if isinstance(data, dict):
                return data.get("items", data)
        return resp

    async def find_country_id(
        self, proxy_type: str, country: str
    ) -> Optional[int]:
        """Resolve a country code/name to its Proxy-Seller ``countryId``.

        Accepts alpha-2 ("us"), alpha-3 ("USA"), or partial name ("Germany").
        """
        ref = await self.get_reference(proxy_type)
        countries = ref.get("country", [])
        if not countries:
            return None

        alpha3 = _to_alpha3(country)
        needle = country.lower()

        for c in countries:
            if not isinstance(c, dict):
                continue
            # Match by alpha3 code first
            if c.get("alpha3", "").upper() == alpha3:
                return c["id"]
            # Fallback: partial name match
            name = (c.get("name") or "").lower()
            if needle in name:
                return c["id"]
        return None

    async def get_balance(self) -> float:
        """Return account balance."""
        resp = await self._request("GET", "balance/get")
        data = resp.get("data", resp) if isinstance(resp, dict) else resp
        return float(data.get("summ", 0)) if isinstance(data, dict) else 0.0

    # ── ordering ─────────────────────────────────────────────────────────

    async def order_make(
        self,
        country_id: int,
        period_id: str,
        quantity: int = 1,
        payment_id: str = "1",
        protocol: str = "HTTPS",
        proxy_type: str = "ipv4",
        generate_auth: str = "Y",
    ) -> Dict:
        """Place an order for ipv4/ipv6/mobile/isp proxies.

        Args:
            country_id: from ``find_country_id()``
            period_id: e.g. ``"1w"``, ``"1m"``, from reference ``period``
            quantity: number of proxies
            payment_id: ``"1"`` = balance
            protocol: ``"HTTPS"`` or ``"SOCKS5"``
            proxy_type: ipv4 / ipv6 / mobile / isp
            generate_auth: ``"Y"`` to auto-generate login/pass
        """
        body = {
            "countryId": country_id,
            "periodId": period_id,
            "quantity": quantity,
            "paymentId": payment_id,
            "protocol": protocol,
            "generateAuth": generate_auth,
        }
        resp = await self._request("POST", f"order/make/{proxy_type}", json_body=body)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    async def order_residential(
        self,
        tariff_id: int,
        quantity: int = 1,
        payment_id: str = "1",
    ) -> Dict:
        """Order residential proxy bandwidth.

        Args:
            tariff_id: from ``get_reference('resident')`` → ``tarifs``
            quantity: number of packages
            payment_id: ``"1"`` = balance
        """
        body = {
            "tarifId": tariff_id,
            "quantity": quantity,
            "paymentId": payment_id,
        }
        resp = await self._request("POST", "order/make/resident", json_body=body)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    async def order_ipv4_usa(
        self,
        period: str = "1w",
        quantity: int = 1,
    ) -> Dict:
        """Convenience: order USA IPv4 proxies with auto-generated auth."""
        cid = await self.find_country_id("ipv4", "us")
        if not cid:
            raise ProxySellerError("Could not find USA country ID for ipv4")
        return await self.order_make(
            country_id=cid, period_id=period, quantity=quantity, proxy_type="ipv4",
        )

    # ── proxy listing ────────────────────────────────────────────────────

    async def get_proxy_list(
        self,
        proxy_type: Optional[str] = None,
        country: Optional[str] = None,
        order_id: Optional[str] = None,
        latest: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return active proxies with full credentials.

        Each item includes: ``id, ip, port_http, port_socks, login, password,
        country, status, order_number, date_start, date_end``.
        """
        endpoint = f"proxy/list/{proxy_type}" if proxy_type else "proxy/list"
        params: Dict[str, str] = {}
        if country:
            params["country"] = _to_alpha3(country)
        if order_id:
            params["orderId"] = order_id
        if latest:
            params["latest"] = "Y"

        resp = await self._request("GET", endpoint, params=params)

        if isinstance(resp, dict):
            data = resp.get("data", resp)
            proxies: List[Dict] = []

            if isinstance(data, dict):
                # Specific type: {"items": [...]}
                if "items" in data and isinstance(data["items"], list):
                    return data["items"]
                # All types: {"ipv4": [...], "resident": [...], ...}
                for key, val in data.items():
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, dict):
                                item.setdefault("type", key)
                                proxies.append(item)
                    elif isinstance(val, dict) and "items" in val:
                        for item in val["items"]:
                            if isinstance(item, dict):
                                item.setdefault("type", key)
                                proxies.append(item)
                return proxies
            if isinstance(data, list):
                return data
        return []

    async def get_proxy_by_country(
        self,
        country: str,
        proxy_type: str = "ipv4",
    ) -> Optional[Dict[str, Any]]:
        """Return the first active proxy matching *country* (alpha-2 or alpha-3)."""
        proxies = await self.get_proxy_list(proxy_type, country=country)
        for p in proxies:
            if p.get("status", "").upper() == "ACTIVE":
                return p
        return proxies[0] if proxies else None

    # ── auth management ──────────────────────────────────────────────────

    async def get_auth_list(self) -> List[Dict]:
        """Return all login/password credentials."""
        resp = await self._request("GET", "auth/list")
        data = resp.get("data", resp) if isinstance(resp, dict) else resp
        return data if isinstance(data, list) else []

    async def create_auth(self, order_number: str, generate: bool = True) -> Dict:
        """Create auth credentials for an order."""
        body: Dict[str, Any] = {"orderNumber": order_number}
        if generate:
            body["generateAuth"] = "Y"
        resp = await self._request("POST", "auth/add", json_body=body)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    async def create_ip_auth(self, order_number: str, ip: str) -> Dict:
        """Whitelist an IP for proxy auth (no user/pass needed)."""
        body = {"orderNumber": order_number, "ip": ip}
        resp = await self._request("POST", "auth/add/ip", json_body=body)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    # ── renewal / extension ──────────────────────────────────────────────

    async def prolong_calc(
        self,
        ids: List[int],
        period_id: str,
        proxy_type: str = "resident",
        payment_id: str = "1",
    ) -> Dict:
        """Calculate the cost of extending proxies."""
        body = {"ids": ids, "periodId": period_id, "paymentId": payment_id, "coupon": ""}
        resp = await self._request("POST", f"prolong/calc/{proxy_type}", json_body=body)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    async def prolong_make(
        self,
        ids: List[int],
        period_id: str,
        proxy_type: str = "resident",
        payment_id: str = "1",
    ) -> Dict:
        """Execute proxy renewal."""
        body = {"ids": ids, "periodId": period_id, "paymentId": payment_id, "coupon": ""}
        resp = await self._request("POST", f"prolong/make/{proxy_type}", json_body=body)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    # ── IP replacement ───────────────────────────────────────────────────

    async def replace_proxy(
        self,
        ids: List[int],
        reason: str = "NOT_WORK",
        comment: str = "",
    ) -> Dict:
        """Request IP replacement (max once/day/proxy).

        ``reason``: NOT_WORK | INCORRECT_LOCATION | CANT_CHANGE_NETWORK |
        LOW_SPEED | CUSTOM
        """
        body: Dict[str, Any] = {"ids": ids, "type": reason}
        if comment:
            body["comment"] = comment
        resp = await self._request("POST", "proxy/replace", json_body=body)
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    # ── residential gateway ─────────────────────────────────────────────

    # Gateway hosts by region (for residential rotating proxies)
    _RES_GATEWAYS = {
        "us": "us.res.proxy-seller.com",
        "eu": "res.proxy-seller.com",       # NL gateway (default)
        "jp": "asia.res.proxy-seller.com",
        "asia": "asia2.res.proxy-seller.com",
    }

    async def get_resident_lists(self) -> List[Dict]:
        """Return all created residential proxy lists."""
        session = await self._get_session()
        url = f"{self.BASE}/{self.api_key}/resident/lists"
        async with session.get(url) as resp:
            data = await self._handle_response(resp)
        items = data.get("data", data) if isinstance(data, dict) else data
        return items if isinstance(items, list) else []

    async def create_resident_list(
        self,
        title: str = "auto",
        country: str = "US",
        whitelist: str = "",
        rotation: int = 0,
        ports: int = 10,
    ) -> Dict:
        """Create a residential proxy list with geo targeting.

        Args:
            title: list name
            country: 2-letter ISO country code (e.g. "US")
            whitelist: comma-separated IPs for IP auth (empty = login/pass)
            rotation: 0 = new IP per request, -1 = sticky, 1-3600 = seconds
            ports: number of simultaneous port slots (max 1000)
        """
        session = await self._get_session()
        url = f"{self.BASE}/{self.api_key}/resident/list/add"
        body = {
            "title": title,
            "whitelist": whitelist,
            "geo": {"country": country.upper()},
            "export": {"ports": ports, "ext": "txt"},
            "rotation": rotation,
        }
        async with session.post(url, json=body) as resp:
            data = await self._handle_response(resp)
        return data.get("data", data) if isinstance(data, dict) else data

    async def get_resident_package(self) -> Dict:
        """Return residential package info (traffic left, expiry, etc.)."""
        resp = await self._request("GET", "resident/package")
        return resp.get("data", resp) if isinstance(resp, dict) else resp

    async def get_residential_proxy(
        self,
        country: str = "us",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a ready-to-use residential proxy dict for the given country.

        Looks up existing lists; creates one if none exist.
        Returns dict with ``host, port, login, password`` keys — ready for
        ``format_proxy_string()`` and Roxy Browser.

        Username is augmented with ``_c_XX`` for country targeting and
        optionally ``_s_ID`` for sticky sessions.
        """
        cc = country.upper() if len(country) == 2 else country[:2].upper()

        # Pick gateway based on country
        if cc == "US":
            gateway = self._RES_GATEWAYS["us"]
        elif cc == "JP":
            gateway = self._RES_GATEWAYS["jp"]
        else:
            gateway = self._RES_GATEWAYS["eu"]

        # Find existing list or create one
        lists = await self.get_resident_lists()
        cred = None
        for lst in lists:
            geos = lst.get("geo", [])
            for g in (geos if isinstance(geos, list) else [geos]):
                if g.get("country", "").upper() == cc:
                    cred = lst
                    break
            if cred:
                break

        if not cred:
            # No list for this country — create one
            logger.info("Creating residential proxy list for {}…", cc)
            cred = await self.create_resident_list(
                title=f"{cc}-auto",
                country=cc,
                rotation=0,
                ports=10,
            )

        login = cred["login"]
        password = cred["password"]

        # Add country targeting to username
        user = f"{login}_c_{cc}"
        if session_id:
            user += f"_s_{session_id}"

        return {
            "ip": gateway,
            "host": gateway,
            "port": 10000,
            "port_http": 10000,
            "login": user,
            "password": password,
            "type": "resident",
            "country": cc,
        }

    # ── formatting helpers ───────────────────────────────────────────────

    @staticmethod
    def format_proxy_string(proxy: Dict[str, Any]) -> str:
        """Format a proxy dict as ``host:port:user:pass`` for Roxy Browser."""
        ip = proxy.get("ip", "")
        port = proxy.get("port_http") or proxy.get("port_socks") or proxy.get("port", "")
        login = proxy.get("login", "")
        password = proxy.get("password", "")
        if login and password:
            return f"{ip}:{port}:{login}:{password}"
        return f"{ip}:{port}"

    @staticmethod
    def format_proxy_url(proxy: Dict[str, Any], socks: bool = False) -> str:
        """Format as ``http://user:pass@ip:port``."""
        ip = proxy.get("ip", "")
        port = proxy.get("port_socks" if socks else "port_http", proxy.get("port", ""))
        login = proxy.get("login", "")
        password = proxy.get("password", "")
        scheme = "socks5" if socks else "http"
        if login and password:
            return f"{scheme}://{login}:{password}@{ip}:{port}"
        return f"{scheme}://{ip}:{port}"
