from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio
from playwright.async_api import Browser, Page, BrowserContext
import logging

@dataclass
class JobPosting:
    """Data class for job posting information"""
    job_id: str
    title: str
    company: str
    location: str
    url: str
    description: Optional[str] = None
    salary: Optional[str] = None
    posted_date: Optional[str] = None
    platform: Optional[str] = None

@dataclass
class SearchCriteria:
    """Data class for job search parameters"""
    keywords: List[str]
    locations: List[str]
    experience_level: Optional[str] = None
    job_type: Optional[str] = None
    remote_options: Optional[str] = None
    date_posted: Optional[str] = None
    easy_apply_only: bool = True

class JobAgent(ABC):
    """
    Abstract base class for job application agents.
    Defines the standard interface that all job board agents must implement.
    """
    
    def __init__(self, config: Dict[str, Any], proxy_config: Optional[Dict[str, str]] = None):
        self.config = config
        self.proxy_config = proxy_config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def initialize_browser(self, headless: bool = True) -> None:
        """Initialize browser with proxy and anti-detection settings"""
        from playwright.async_api import async_playwright
        from utils.proxy_manager import AntiDetectionManager
        
        playwright = await async_playwright().start()
        
        # Enhanced anti-detection arguments
        launch_options = {
            'headless': headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-default-apps'
            ]
        }
        
        # Add proxy configuration if available
        if self.proxy_config:
            if isinstance(self.proxy_config, dict):
                # Handle direct proxy config dict
                launch_options['proxy'] = {
                    'server': f"http://{self.proxy_config['host']}:{self.proxy_config['port']}",
                    'username': self.proxy_config.get('username'),
                    'password': self.proxy_config.get('password')
                }
            else:
                # Handle ProxyManager config
                from utils.proxy_manager import ProxyManager
                if hasattr(self.proxy_config, 'get_current_proxy'):
                    current_proxy = self.proxy_config.get_current_proxy()
                    if current_proxy:
                        launch_options['proxy'] = self.proxy_config.get_playwright_proxy_config(current_proxy)
            
        self.browser = await playwright.chromium.launch(**launch_options)
        
        # Use random user agent and viewport for better anonymity
        context_options = {
            'user_agent': AntiDetectionManager.get_random_user_agent(),
            'viewport': AntiDetectionManager.get_random_viewport(),
            'java_script_enabled': True,
            'permissions': ['geolocation'],
            'ignore_https_errors': True,
            'bypass_csp': True
        }
        
        self.context = await self.browser.new_context(**context_options)
        
        # Add comprehensive stealth scripts
        stealth_script = AntiDetectionManager.get_stealth_script()
        await self.context.add_init_script(stealth_script)
        
        self.page = await self.context.new_page()
        
        # Additional page-level stealth measures
        await self.page.evaluate("""
            // Override webgl vendor and renderer
            const getParameter = WebGLRenderingContext.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) Iris(TM) Graphics 6100';
                }
                return getParameter(parameter);
            };
            
            // Mock battery API
            if ('getBattery' in navigator) {
                navigator.getBattery = function() {
                    return Promise.resolve({
                        charging: true,
                        chargingTime: 0,
                        dischargingTime: Infinity,
                        level: 1
                    });
                };
            }
        """)
        
    async def cleanup(self) -> None:
        """Clean up browser resources"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
    
    @abstractmethod
    async def login(self) -> bool:
        """
        Log into the job platform using credentials from config
        Returns True if login successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def search_jobs(self, criteria: SearchCriteria) -> List[JobPosting]:
        """
        Search for jobs based on given criteria
        Returns list of JobPosting objects
        """
        pass
    
    @abstractmethod
    async def apply_to_job(self, job: JobPosting) -> bool:
        """
        Apply to a specific job
        Returns True if application successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """
        Extract detailed information from a job posting URL
        Returns JobPosting object with full details
        """
        pass
    
    async def run_automation(self, criteria: SearchCriteria, max_applications: int = 5) -> Dict[str, Any]:
        """
        Main automation workflow:
        1. Initialize browser
        2. Login
        3. Search for jobs
        4. Apply to jobs (up to max_applications)
        5. Return summary
        """
        summary = {
            'platform': self.__class__.__name__,
            'jobs_found': 0,
            'applications_submitted': 0,
            'errors': 0,
            'applied_jobs': []
        }
        
        try:
            await self.initialize_browser()
            self.logger.info(f"Starting {self.__class__.__name__} automation")
            
            # Login
            login_success = await self.login()
            if not login_success:
                raise Exception("Login failed")
            
            # Search for jobs
            jobs = await self.search_jobs(criteria)
            summary['jobs_found'] = len(jobs)
            self.logger.info(f"Found {len(jobs)} jobs")
            
            # Apply to jobs
            applications = 0
            for job in jobs[:max_applications]:
                try:
                    success = await self.apply_to_job(job)
                    if success:
                        applications += 1
                        summary['applied_jobs'].append({
                            'title': job.title,
                            'company': job.company,
                            'url': job.url
                        })
                        self.logger.info(f"Applied to {job.title} at {job.company}")
                    await asyncio.sleep(2)  # Rate limiting
                except Exception as e:
                    self.logger.error(f"Error applying to {job.title}: {str(e)}")
                    summary['errors'] += 1
            
            summary['applications_submitted'] = applications
            
        except Exception as e:
            self.logger.error(f"Automation error: {str(e)}")
            summary['errors'] += 1
            
        finally:
            await self.cleanup()
            
        return summary