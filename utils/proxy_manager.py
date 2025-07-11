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

class ProxyManager:
    """
    Manages proxy rotation and validation for anonymous web scraping
    Supports multiple proxy providers and automatic failover
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
    
    # Handle single proxy configuration
    if proxy_config.get('host'):
        proxy_configs = [{
            'host': proxy_config['host'],
            'port': proxy_config['port'],
            'username': proxy_config.get('username'),
            'password': proxy_config.get('password'),
            'protocol': proxy_config.get('protocol', 'http')
        }]
    # Handle multiple proxy configurations
    elif proxy_config.get('proxies'):
        proxy_configs = proxy_config['proxies']
    else:
        logging.warning("Proxy enabled but no proxy configuration found")
        return None
    
    return ProxyManager(proxy_configs)

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