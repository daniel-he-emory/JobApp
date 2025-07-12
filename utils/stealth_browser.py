"""
Enhanced browser manager with anti-detection capabilities
"""
import random
import json
from typing import Optional, Dict, Any
from playwright.async_api import BrowserContext, Page
try:
    from playwright_stealth import stealth_async
except ImportError:
    # Fallback if stealth_async is not available
    stealth_async = None


class StealthBrowserManager:
    """
    Manages browser instances with advanced anti-detection features
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser_config = config.get('browser', {})
        
    async def apply_stealth_to_page(self, page: Page) -> None:
        """Apply stealth measures to a page"""
        try:
            # Apply playwright-stealth if available
            if self.browser_config.get('stealth_mode', False) and stealth_async:
                await stealth_async(page)
            
            # Override navigator.webdriver
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # Spoof device memory
            device_memory = self.browser_config.get('device_memory', 8)
            await page.add_init_script(f"""
                Object.defineProperty(navigator, 'deviceMemory', {{
                    get: () => {device_memory},
                }});
            """)
            
            # Spoof hardware concurrency (CPU cores)
            cpu_cores = self.browser_config.get('cpu_cores', 4)
            await page.add_init_script(f"""
                Object.defineProperty(navigator, 'hardwareConcurrency', {{
                    get: () => {cpu_cores},
                }});
            """)
            
            # Spoof languages
            await page.add_init_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
            
            # Spoof permissions
            await page.add_init_script("""
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Cypress ? 'denied' : 'granted' }) :
                        originalQuery(parameters)
                );
            """)
            
            # Add realistic screen properties
            await page.add_init_script("""
                Object.defineProperty(screen, 'availWidth', {
                    get: () => window.screen.width,
                });
                Object.defineProperty(screen, 'availHeight', {
                    get: () => window.screen.height - 40, // Account for taskbar
                });
            """)
            
            # Randomize mouse movements
            await page.add_init_script("""
                // Add subtle mouse movement randomization
                const originalMoveTo = window.MouseEvent.prototype.moveTo;
                if (originalMoveTo) {
                    window.MouseEvent.prototype.moveTo = function(x, y) {
                        const jitterX = x + (Math.random() - 0.5) * 2;
                        const jitterY = y + (Math.random() - 0.5) * 2;
                        return originalMoveTo.call(this, jitterX, jitterY);
                    };
                }
            """)
            
        except Exception as e:
            # Don't fail if stealth measures can't be applied
            print(f"Warning: Could not apply some stealth measures: {e}")
    
    def get_browser_launch_options(self) -> Dict[str, Any]:
        """Get browser launch options with anti-detection settings"""
        width = self.browser_config.get('window_size', {}).get('width', 1440)
        height = self.browser_config.get('window_size', {}).get('height', 900)
        
        # Randomize viewport slightly if enabled
        if self.browser_config.get('randomize_viewport', False):
            width += random.randint(-50, 50)
            height += random.randint(-30, 30)
        
        launch_options = {
            'headless': self.browser_config.get('headless', False),
            'args': [
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-blink-features=AutomationControlled',
                '--start-maximized',
                f'--window-size={width},{height}',
            ]
        }
        
        # Add extra args for better stealth
        if not self.browser_config.get('headless', False):
            launch_options['args'].extend([
                '--disable-infobars',
                '--disable-extensions',
                '--no-sandbox',
                '--disable-application-cache',
                '--disable-gpu-process-crash-limit',
                '--disable-gpu-sandbox',
            ])
        
        return launch_options
    
    async def create_human_like_context(self, browser) -> BrowserContext:
        """Create a browser context that mimics human behavior"""
        context_options = {
            'viewport': {
                'width': self.browser_config.get('window_size', {}).get('width', 1440),
                'height': self.browser_config.get('window_size', {}).get('height', 900)
            },
            'user_agent': self.browser_config.get('user_agent'),
            'locale': self.browser_config.get('locale', 'en-US'),
            'timezone_id': self.browser_config.get('timezone', 'America/New_York'),
            'permissions': ['geolocation'],
            'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},  # NYC coordinates
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            }
        }
        
        context = await browser.new_context(**context_options)
        return context
    
    async def add_human_behavior_to_page(self, page: Page) -> None:
        """Add human-like behavior patterns to page interactions"""
        
        # Override click to add human-like delays
        await page.add_init_script("""
            const originalClick = HTMLElement.prototype.click;
            HTMLElement.prototype.click = function() {
                // Add small random delay before click
                setTimeout(() => originalClick.call(this), Math.random() * 100 + 50);
            };
        """)
        
        # Add realistic typing patterns
        page.type = self._create_human_type_function(page.type)
    
    def _create_human_type_function(self, original_type):
        """Create a typing function with human-like patterns"""
        async def human_type(selector, text, **kwargs):
            # Add realistic typing delay
            delay = kwargs.get('delay', random.randint(80, 150))
            kwargs['delay'] = delay
            
            # Occasionally make "typos" and correct them
            if len(text) > 5 and random.random() < 0.1:  # 10% chance of typo
                typo_pos = random.randint(1, len(text) - 1)
                typo_char = chr(ord(text[typo_pos]) + random.choice([-1, 1]))
                typo_text = text[:typo_pos] + typo_char + text[typo_pos+1:]
                
                # Type with typo
                await original_type(selector, typo_text, **kwargs)
                await page.wait_for_timeout(random.randint(500, 1500))
                
                # Correct the typo
                await page.keyboard.press('Backspace')
                await page.wait_for_timeout(random.randint(100, 300))
                await page.keyboard.type(text[typo_pos])
            else:
                await original_type(selector, text, **kwargs)
        
        return human_type