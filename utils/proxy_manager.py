import random
import time
import logging
from typing import Dict, List, Optional, Any
import requests
from dataclasses import dataclass

@dataclass
class ProxyConfig:
    """Data class for proxy configuration"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"
    country: Optional[str] = None
    sticky_session: bool = False
    provider: Optional[str] = None  # Provider type: 'smartproxy', 'brightdata', 'oxylabs', etc.
    endpoint: Optional[str] = None  # Provider endpoint for residential proxies

class ResidentialProxyManager:
    """
    Manages residential proxy providers with rotating endpoints
    Supports major providers like SmartProxy, BrightData, Oxylabs
    """
    
    PROVIDER_CONFIGS = {
        'smartproxy': {
            'endpoint_format': 'gate.smartproxy.com',
            'port': 10000,
            'supports_country': True,
            'supports_sticky': True
        },
        'brightdata': {
            'endpoint_format': 'brd-customer-{zone}.zproxy.lum-superproxy.io',
            'port': 22225,
            'supports_country': True,
            'supports_sticky': True
        },
        'oxylabs': {
            'endpoint_format': 'pr.oxylabs.io',
            'port': 7777,
            'supports_country': True,
            'supports_sticky': False
        },
        'proxy-cheap': {
            'endpoint_format': 'rotating-residential.proxycheap.com',
            'port': 31112,
            'supports_country': True,
            'supports_sticky': True
        }
    }
    
    def __init__(self, provider: str, username: str, password: str, 
                 country: Optional[str] = None, sticky_session: bool = False,
                 zone: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.provider = provider.lower()
        self.username = username
        self.password = password
        self.country = country
        self.sticky_session = sticky_session
        self.zone = zone  # For BrightData zones
        
        if self.provider not in self.PROVIDER_CONFIGS:
            raise ValueError(f"Unsupported provider: {provider}. Supported: {list(self.PROVIDER_CONFIGS.keys())}")
        
        self.provider_config = self.PROVIDER_CONFIGS[self.provider]
        self.logger.info(f"Initialized residential proxy manager for {provider}")
    
    def get_proxy_config(self) -> ProxyConfig:
        """Generate proxy configuration for the residential provider"""
        endpoint = self._build_endpoint()
        port = self.provider_config['port']
        
        # Build username with country/session parameters
        username = self._build_username()
        
        return ProxyConfig(
            host=endpoint,
            port=port,
            username=username,
            password=self.password,
            protocol="http",
            country=self.country,
            sticky_session=self.sticky_session,
            provider=self.provider,
            endpoint=endpoint
        )
    
    def _build_endpoint(self) -> str:
        """Build the provider endpoint URL"""
        endpoint_format = self.provider_config['endpoint_format']
        
        if self.provider == 'brightdata' and self.zone:
            return endpoint_format.format(zone=self.zone)
        else:
            return endpoint_format
    
    def _build_username(self) -> str:
        """Build username with provider-specific parameters"""
        username = self.username
        
        # Add country parameter if supported and specified
        if self.country and self.provider_config['supports_country']:
            if self.provider == 'smartproxy':
                username += f'-country-{self.country.lower()}'
            elif self.provider == 'brightdata':
                username += f'-country-{self.country.lower()}'
            elif self.provider == 'oxylabs':
                username += f'-country-{self.country.lower()}'
            elif self.provider == 'proxy-cheap':
                username += f'-country-{self.country.lower()}'
        
        # Add sticky session if supported and enabled
        if self.sticky_session and self.provider_config['supports_sticky']:
            if self.provider == 'smartproxy':
                session_id = f"session-{int(time.time())}"
                username += f'-session-{session_id}'
            elif self.provider == 'brightdata':
                session_id = f"session_{int(time.time())}"
                username += f'-session-{session_id}'
            elif self.provider == 'proxy-cheap':
                session_id = f"session{int(time.time())}"
                username += f'-session-{session_id}'
        
        return username
    
    def get_playwright_proxy_config(self, proxy: ProxyConfig) -> Dict[str, Any]:
        """Get proxy configuration for Playwright with provider URL format"""
        # For residential providers, use the full URL format
        proxy_url = f"{proxy.protocol}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        
        return {
            'server': proxy_url
        }

class ProxyManager:
    """
    Manages proxy rotation and validation for anonymous web scraping
    Supports multiple proxy providers and automatic failover
    Supports both traditional proxy lists and residential proxy providers
    """
    
    def __init__(self, proxy_configs: List[Dict[str, Any]]):
        self.logger = logging.getLogger(__name__)
        self.proxy_configs = []
        self.current_proxy_index = 0
        self.failed_proxies = set()
        self.last_rotation_time = 0
        self.rotation_interval = 300  # 5 minutes
        
        # Parse proxy configurations
        for config in proxy_configs:
            self.proxy_configs.append(ProxyConfig(**config))
        
        if not self.proxy_configs:
            self.logger.warning("No proxy configurations provided")
    
    def get_current_proxy(self) -> Optional[ProxyConfig]:
        """Get the currently active proxy configuration"""
        if not self.proxy_configs:
            return None
        
        # Check if rotation is needed
        if self._should_rotate():
            self.rotate_proxy()
        
        if self.current_proxy_index < len(self.proxy_configs):
            return self.proxy_configs[self.current_proxy_index]
        
        return None
    
    def _should_rotate(self) -> bool:
        """Determine if proxy should be rotated"""
        current_time = time.time()
        return (current_time - self.last_rotation_time) > self.rotation_interval
    
    def rotate_proxy(self) -> Optional[ProxyConfig]:
        """Rotate to the next available proxy"""
        if not self.proxy_configs:
            return None
        
        original_index = self.current_proxy_index
        attempts = 0
        max_attempts = len(self.proxy_configs)
        
        while attempts < max_attempts:
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_configs)
            proxy = self.proxy_configs[self.current_proxy_index]
            
            # Skip failed proxies
            proxy_key = f"{proxy.host}:{proxy.port}"
            if proxy_key not in self.failed_proxies:
                self.last_rotation_time = time.time()
                self.logger.info(f"Rotated to proxy: {proxy.host}:{proxy.port}")
                return proxy
            
            attempts += 1
        
        # If all proxies have failed, reset failed list and try again
        if attempts >= max_attempts:
            self.logger.warning("All proxies have failed, resetting failed list")
            self.failed_proxies.clear()
            self.current_proxy_index = original_index
            self.last_rotation_time = time.time()
            return self.proxy_configs[self.current_proxy_index] if self.proxy_configs else None
        
        return None
    
    def mark_proxy_failed(self, proxy: ProxyConfig):
        """Mark a proxy as failed"""
        proxy_key = f"{proxy.host}:{proxy.port}"
        self.failed_proxies.add(proxy_key)
        self.logger.warning(f"Marked proxy as failed: {proxy_key}")
        
        # Try to rotate to next proxy
        self.rotate_proxy()
    
    def validate_proxy(self, proxy: ProxyConfig, timeout: int = 10) -> bool:
        """Validate that a proxy is working"""
        try:
            proxy_url = self._build_proxy_url(proxy)
            
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            # Test with a simple HTTP request
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxies,
                timeout=timeout,
                verify=False
            )
            
            if response.status_code == 200:
                ip_data = response.json()
                self.logger.info(f"Proxy {proxy.host}:{proxy.port} working, IP: {ip_data.get('origin')}")
                return True
            else:
                self.logger.warning(f"Proxy {proxy.host}:{proxy.port} returned status: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Proxy validation failed for {proxy.host}:{proxy.port}: {str(e)}")
            return False
    
    def _build_proxy_url(self, proxy: ProxyConfig) -> str:
        """Build proxy URL for requests library"""
        if proxy.username and proxy.password:
            return f"{proxy.protocol}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        else:
            return f"{proxy.protocol}://{proxy.host}:{proxy.port}"
    
    def get_playwright_proxy_config(self, proxy: ProxyConfig) -> Dict[str, Any]:
        """Get proxy configuration for Playwright"""
        # For residential proxy providers, use URL format with credentials
        if proxy.provider and proxy.provider in ResidentialProxyManager.PROVIDER_CONFIGS:
            proxy_url = f"{proxy.protocol}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
            return {
                'server': proxy_url
            }
        
        # Traditional proxy configuration
        config = {
            'server': f"{proxy.protocol}://{proxy.host}:{proxy.port}"
        }
        
        if proxy.username and proxy.password:
            config['username'] = proxy.username
            config['password'] = proxy.password
        
        return config
    
    def validate_all_proxies(self) -> List[ProxyConfig]:
        """Validate all proxy configurations and return working ones"""
        working_proxies = []
        
        for proxy in self.proxy_configs:
            if self.validate_proxy(proxy):
                working_proxies.append(proxy)
            else:
                self.mark_proxy_failed(proxy)
        
        self.logger.info(f"Validated proxies: {len(working_proxies)}/{len(self.proxy_configs)} working")
        return working_proxies
    
    def get_random_proxy(self) -> Optional[ProxyConfig]:
        """Get a random proxy from available ones"""
        if not self.proxy_configs:
            return None
        
        available_proxies = [
            proxy for proxy in self.proxy_configs
            if f"{proxy.host}:{proxy.port}" not in self.failed_proxies
        ]
        
        if not available_proxies:
            # Reset failed proxies if none available
            self.failed_proxies.clear()
            available_proxies = self.proxy_configs
        
        if available_proxies:
            return random.choice(available_proxies)
        
        return None
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """Get statistics about proxy usage"""
        total_proxies = len(self.proxy_configs)
        failed_proxies = len(self.failed_proxies)
        working_proxies = total_proxies - failed_proxies
        
        return {
            'total_proxies': total_proxies,
            'working_proxies': working_proxies,
            'failed_proxies': failed_proxies,
            'current_proxy_index': self.current_proxy_index,
            'current_proxy': self.get_current_proxy().__dict__ if self.get_current_proxy() else None
        }

class ProxyRotationStrategy:
    """
    Different strategies for proxy rotation
    """
    
    @staticmethod
    def time_based(manager: ProxyManager, interval_seconds: int = 300):
        """Rotate proxy based on time intervals"""
        manager.rotation_interval = interval_seconds
    
    @staticmethod
    def request_based(manager: ProxyManager, requests_per_proxy: int = 50):
        """Rotate proxy based on number of requests (would need request counting)"""
        # This would require integration with the actual request logic
        pass
    
    @staticmethod
    def random_rotation(manager: ProxyManager):
        """Use random proxy for each session"""
        return manager.get_random_proxy()

def create_proxy_manager_from_config(config: Dict[str, Any]) -> Optional[ProxyManager]:
    """Create ProxyManager from configuration dictionary"""
    proxy_config = config.get('proxy', {})
    
    if not proxy_config.get('enabled', False):
        return None
    
    # Check for smartproxy configuration (matches config.yaml structure)
    smartproxy_config = proxy_config.get('smartproxy', {})
    if smartproxy_config.get('enabled', False):
        try:
            # Extract endpoint and port
            endpoint = smartproxy_config.get('endpoint', '')
            if ':' in endpoint:
                host, port = endpoint.split(':', 1)
                port = int(port)
            else:
                host = endpoint
                port = ResidentialProxyManager.PROVIDER_CONFIGS['smartproxy']['port']
            
            # Create residential proxy manager
            residential_manager = ResidentialProxyManager(
                provider='smartproxy',
                username=smartproxy_config['username'],
                password=smartproxy_config['password'],
                country=smartproxy_config.get('country'),
                sticky_session=smartproxy_config.get('session_type') == 'sticky'
            )
            
            # Get proxy config and wrap in traditional ProxyManager
            proxy_config_obj = residential_manager.get_proxy_config()
            proxy_configs = [proxy_config_obj.__dict__]
            
            # Create traditional manager with residential proxy
            manager = ProxyManager(proxy_configs)
            
            # Enhance with residential-specific methods
            def enhanced_get_playwright(proxy):
                return residential_manager.get_playwright_proxy_config(proxy)
            
            manager.get_playwright_proxy_config = enhanced_get_playwright
            manager.residential_manager = residential_manager
            
            logging.getLogger(__name__).info("Created residential proxy manager for smartproxy")
            return manager
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to create smartproxy proxy manager: {e}")
    
    # Fallback to traditional proxy configuration using fallback_proxies
    fallback_proxies = proxy_config.get('fallback_proxies', [])
    if fallback_proxies:
        logging.getLogger(__name__).info("Using fallback proxy configuration")
        return ProxyManager(fallback_proxies)
    
    logging.getLogger(__name__).warning("Proxy enabled but no valid proxy configuration found")
    return None

# Anti-detection utilities
class AntiDetectionManager:
    """
    Manages anti-detection features for web automation
    """
    
    @staticmethod
    def get_random_user_agent() -> str:
        """Get a random realistic user agent"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        return random.choice(user_agents)
    
    @staticmethod
    def get_random_viewport() -> Dict[str, int]:
        """Get a random realistic viewport size"""
        viewports = [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1536, 'height': 864},
            {'width': 1440, 'height': 900},
            {'width': 1280, 'height': 720}
        ]
        return random.choice(viewports)
    
    @staticmethod
    def get_stealth_script() -> str:
        """Get JavaScript code to make browser less detectable"""
        return """
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        
        // Add chrome runtime
        window.chrome = {
            runtime: {},
        };
        
        // Override plugins length
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        
        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """
    
    @staticmethod
    def get_random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> float:
        """Get a random delay to mimic human behavior"""
        return random.uniform(min_seconds, max_seconds)
    
    @staticmethod
    def should_take_break(requests_count: int, break_threshold: int = 20) -> bool:
        """Determine if a longer break should be taken"""
        return requests_count % break_threshold == 0 and requests_count > 0