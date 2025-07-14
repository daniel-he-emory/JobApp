from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio
from playwright.async_api import Browser, Page, BrowserContext
import logging
from utils.stealth_browser import StealthBrowserManager


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

    async def initialize_browser(self, headless: bool = None) -> None:
        """Initialize browser with enhanced anti-detection settings"""
        from playwright.async_api import async_playwright

        # Initialize stealth browser manager
        self.stealth_manager = StealthBrowserManager(self.config)

        # Use headless setting from config if not specified
        if headless is None:
            headless = self.config.get('browser', {}).get('headless', False)

        playwright = await async_playwright().start()

        # Get enhanced launch options with anti-detection
        launch_options = self.stealth_manager.get_browser_launch_options()

        # Override headless if specified
        launch_options['headless'] = headless

        # Add proxy configuration if enabled
        proxy_config = self.config.get('proxy', {})
        if proxy_config.get('enabled', False):
            try:
                from utils.proxy_manager import create_proxy_manager_from_config

                # Create proxy manager from config
                self.proxy_manager = create_proxy_manager_from_config(
                    self.config)

                if self.proxy_manager:
                    # Get current proxy (with rotation)
                    current_proxy = self.proxy_manager.get_current_proxy()

                    if current_proxy:
                        # Get Playwright proxy configuration
                        playwright_proxy_config = self.proxy_manager.get_playwright_proxy_config(
                            current_proxy)
                        launch_options['proxy'] = playwright_proxy_config
                        self.logger.info(
                            f"Using proxy: {current_proxy.host}:{current_proxy.port}")
                    else:
                        self.logger.warning("No working proxy available")
                else:
                    self.logger.info(
                        "Proxy enabled but no valid configuration found")

            except Exception as e:
                self.logger.warning(
                    f"Could not configure proxy: {e}, proceeding without proxy")
        else:
            self.proxy_manager = None

        self.browser = await playwright.chromium.launch(**launch_options)

        # Create human-like browser context with enhanced anti-detection
        self.context = await self.stealth_manager.create_human_like_context(self.browser)

        self.page = await self.context.new_page()

        # Apply comprehensive stealth measures to the page
        await self.stealth_manager.apply_stealth_to_page(self.page)
        await self.stealth_manager.add_human_behavior_to_page(self.page)

        # Initialize CAPTCHA solver if enabled
        captcha_config = self.config.get('captcha_solver', {})
        if captcha_config.get('enabled', False):
            try:
                from utils.captcha_solver import create_captcha_solver_from_config
                self.captcha_solver = create_captcha_solver_from_config(
                    self.config)
                if self.captcha_solver:
                    self.logger.info("CAPTCHA solver initialized and ready")
                else:
                    self.logger.warning(
                        "CAPTCHA solver enabled but could not initialize")
            except Exception as e:
                self.logger.warning(
                    f"Could not initialize CAPTCHA solver: {e}")
                self.captcha_solver = None
        else:
            self.captcha_solver = None

    async def handle_captcha_if_present(self) -> bool:
        """
        Detect and solve CAPTCHAs on the current page if CAPTCHA solver is enabled

        Returns:
            True if CAPTCHA was detected and solved, False if no CAPTCHA found

        Raises:
            Exception if CAPTCHA detection fails or solving encounters errors
        """
        if not self.captcha_solver:
            return False

        try:
            self.logger.debug("Scanning page for CAPTCHA challenges...")

            # Check for reCAPTCHA v2 iframe
            recaptcha_iframe = None
            try:
                recaptcha_iframe = await self.page.wait_for_selector(
                    'iframe[src*="recaptcha"], iframe[src*="google.com/recaptcha"]',
                    timeout=2000
                )
            except:
                pass

            if recaptcha_iframe:
                self.logger.info(
                    "reCAPTCHA v2 detected, attempting to solve...")
                return await self._solve_recaptcha_v2()

            # Check for reCAPTCHA v3 (less common in forms)
            recaptcha_v3 = None
            try:
                recaptcha_v3 = await self.page.wait_for_selector(
                    '[data-sitekey], .g-recaptcha[data-sitekey]',
                    timeout=2000
                )
            except:
                pass

            if recaptcha_v3:
                self.logger.info(
                    "reCAPTCHA v3 detected, attempting to solve...")
                return await self._solve_recaptcha_v2()  # Use same method

            # Check for hCaptcha
            hcaptcha = None
            try:
                hcaptcha = await self.page.wait_for_selector(
                    'iframe[src*="hcaptcha"], .h-captcha',
                    timeout=2000
                )
            except:
                pass

            if hcaptcha:
                self.logger.warning(
                    "hCaptcha detected but not currently supported")
                return False

            # No CAPTCHA detected
            return False

        except Exception as e:
            self.logger.error(f"Error during CAPTCHA detection: {str(e)}")
            return False

    async def _solve_recaptcha_v2(self) -> bool:
        """
        Solve reCAPTCHA v2/v3 challenge

        Returns:
            True if solved successfully, False otherwise
        """
        try:
            # Extract site key from page
            site_key = await self._extract_recaptcha_site_key()
            if not site_key:
                self.logger.error(
                    "Could not extract reCAPTCHA site key from page")
                return False

            self.logger.info(
                f"Extracted reCAPTCHA site key: {site_key[:20]}...")

            # Solve CAPTCHA using service
            page_url = self.page.url
            token = await self.captcha_solver.solve_recaptcha_v2(site_key, page_url)

            if not token:
                self.logger.error(
                    "CAPTCHA solving service returned empty token")
                return False

            self.logger.info("CAPTCHA solved successfully, injecting token...")

            # Inject token into page
            await self._inject_recaptcha_token(token)

            # Wait a moment for any page updates
            await asyncio.sleep(1)

            self.logger.info("CAPTCHA token injected successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error solving reCAPTCHA: {str(e)}")
            return False

    async def _extract_recaptcha_site_key(self) -> Optional[str]:
        """Extract reCAPTCHA site key from page HTML"""
        try:
            # Method 1: Check data-sitekey attribute
            site_key = await self.page.evaluate("""
                () => {
                    const element = document.querySelector('[data-sitekey]');
                    return element ? element.getAttribute('data-sitekey') : null;
                }
            """)

            if site_key:
                return site_key

            # Method 2: Check iframe src
            site_key = await self.page.evaluate("""
                () => {
                    const iframe = document.querySelector('iframe[src*="recaptcha"]');
                    if (iframe) {
                        const src = iframe.src;
                        const match = src.match(/[?&]k=([^&]+)/);
                        return match ? match[1] : null;
                    }
                    return null;
                }
            """)

            if site_key:
                return site_key

            # Method 3: Check page source for embedded key
            content = await self.page.content()
            import re
            matches = re.findall(r'data-sitekey=["\']([^"\']+)["\']', content)
            if matches:
                return matches[0]

            matches = re.findall(
                r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)["\']', content)
            if matches:
                return matches[0]

            return None

        except Exception as e:
            self.logger.error(f"Error extracting site key: {str(e)}")
            return None

    async def _inject_recaptcha_token(self, token: str) -> None:
        """Inject solved reCAPTCHA token into page"""
        try:
            # Method 1: Set g-recaptcha-response textarea
            await self.page.evaluate(f"""
                () => {{
                    const textarea = document.querySelector('textarea[name="g-recaptcha-response"]') ||
                                   document.querySelector('#g-recaptcha-response');
                    if (textarea) {{
                        textarea.value = '{token}';
                        textarea.innerHTML = '{token}';
                        
                        // Trigger change event
                        const event = new Event('change', {{ bubbles: true }});
                        textarea.dispatchEvent(event);
                        
                        return true;
                    }}
                    return false;
                }}
            """)

            # Method 2: Try to find and call reCAPTCHA callback
            await self.page.evaluate(f"""
                () => {{
                    // Look for global reCAPTCHA callback
                    if (window.grecaptcha && window.grecaptcha.getResponse) {{
                        // Reset and execute callback
                        try {{
                            const widgetId = 0; // Usually 0 for first widget
                            if (window.grecaptcha.reset) {{
                                window.grecaptcha.reset(widgetId);
                            }}
                            
                            // Set response directly
                            if (window.grecaptcha.enterprise) {{
                                window.grecaptcha.enterprise.execute();
                            }}
                        }} catch (e) {{
                            console.log('reCAPTCHA callback execution failed:', e);
                        }}
                    }}
                    
                    // Look for custom callback functions
                    const forms = document.querySelectorAll('form');
                    forms.forEach(form => {{
                        const recaptcha = form.querySelector('.g-recaptcha, [data-sitekey]');
                        if (recaptcha) {{
                            const callback = recaptcha.getAttribute('data-callback');
                            if (callback && window[callback]) {{
                                try {{
                                    window[callback]('{token}');
                                }} catch (e) {{
                                    console.log('Custom callback execution failed:', e);
                                }}
                            }}
                        }}
                    }});
                }}
            """)

        except Exception as e:
            self.logger.error(f"Error injecting reCAPTCHA token: {str(e)}")
            raise

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
    async def apply_to_job(self, job: JobPosting, ai_content: Optional[Dict[str, str]] = None) -> bool:
        """
        Apply to a specific job

        Args:
            job: JobPosting object with job details
            ai_content: Optional AI-generated content (cover letter, optimized resume sections)

        Returns:
            True if application successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """
        Extract detailed information from a job posting URL
        Returns JobPosting object with full details
        """
        pass

    async def run_automation(self, criteria: SearchCriteria, max_applications: int = 5,
                             ai_content: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
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
                    success = await self.apply_to_job(job, ai_content)
                    if success:
                        applications += 1
                        summary['applied_jobs'].append({
                            'title': job.title,
                            'company': job.company,
                            'url': job.url
                        })
                        self.logger.info(
                            f"Applied to {job.title} at {job.company}")
                    await asyncio.sleep(2)  # Rate limiting
                except Exception as e:
                    self.logger.error(
                        f"Error applying to {job.title}: {str(e)}")
                    summary['errors'] += 1

            summary['applications_submitted'] = applications

        except Exception as e:
            self.logger.error(f"Automation error: {str(e)}")
            summary['errors'] += 1

        finally:
            await self.cleanup()

        return summary
