import asyncio
import re
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
import logging

from base_agent import JobAgent, JobPosting, SearchCriteria
from utils.email_verifier import GreenHouseEmailVerifier

class LinkedInAgent(JobAgent):
    """
    LinkedIn job application agent
    Implements the workflow from n8n: Login -> Search -> Filter -> Apply
    """
    
    def __init__(self, config: Dict[str, Any], proxy_config: Optional[Dict[str, str]] = None):
        super().__init__(config, proxy_config)
        self.platform_name = "LinkedIn"
        
        # Email verifier for Greenhouse applications
        email_config = config.get('credentials', {}).get('verification_email', {})
        if email_config.get('address'):
            self.email_verifier = GreenHouseEmailVerifier(
                email_address=email_config['address'],
                email_password=email_config['password'],
                imap_server=email_config.get('imap_server', 'imap.gmail.com'),
                imap_port=email_config.get('imap_port', 993)
            )
        else:
            self.email_verifier = None
            self.logger.warning("No email verification configured")
    
    async def login(self) -> bool:
        """Login to LinkedIn using credentials from config"""
        try:
            credentials = self.config.get('credentials', {}).get('linkedin', {})
            if not credentials.get('email') or not credentials.get('password'):
                self.logger.error("LinkedIn credentials not found in config")
                return False
            
            self.logger.info("Navigating to LinkedIn login page")
            await self.page.goto("https://www.linkedin.com/login", timeout=30000)
            await self.page.wait_for_load_state('domcontentloaded', timeout=30000)
            await self.page.wait_for_timeout(2000)  # Give page time to fully load
            
            # Fill login form
            await self.page.fill('input[name="session_key"]', credentials['email'])
            await self.page.fill('input[name="session_password"]', credentials['password'])
            
            # Click login button
            await self.page.click('button[type="submit"]')
            await self.page.wait_for_timeout(3000)
            
            # Check if login was successful
            current_url = self.page.url
            if 'linkedin.com/feed' in current_url or 'linkedin.com/jobs' in current_url:
                self.logger.info("LinkedIn login successful")
                return True
            elif 'checkpoint' in current_url or 'verify' in current_url:
                self.logger.warning("LinkedIn login requires additional verification")
                # Handle 2FA or verification if needed
                await self.page.wait_for_timeout(10000)  # Wait for manual intervention
                return True
            else:
                self.logger.error("LinkedIn login failed")
                return False
                
        except Exception as e:
            self.logger.error(f"LinkedIn login error: {str(e)}")
            return False
    
    async def search_jobs(self, criteria: SearchCriteria) -> List[JobPosting]:
        """
        Search for jobs on LinkedIn based on criteria
        Implements the n8n workflow: Navigate -> Type keywords -> Apply filters
        """
        try:
            jobs = []
            
            # Navigate to LinkedIn jobs page
            self.logger.info("Navigating to LinkedIn jobs page")
            try:
                await self.page.goto("https://www.linkedin.com/jobs/", timeout=60000)
                await self.page.wait_for_load_state('networkidle', timeout=30000)
            except Exception as e:
                self.logger.warning(f"Initial navigation slow: {str(e)}, continuing...")
                # Try to wait for basic page elements instead
                try:
                    await self.page.wait_for_selector('input[aria-label*="Search"], input[placeholder*="Search"]', timeout=30000)
                except:
                    # Try direct search URL approach
                    search_url = "https://www.linkedin.com/jobs/search/?keywords=Solutions%20Engineer&location=San%20Francisco%20Bay%20Area"
                    self.logger.info("Trying direct search URL approach")
                    await self.page.goto(search_url, timeout=60000)
                    await self.page.wait_for_load_state('domcontentloaded')
            
            # If we're not already on a search results page, try to search
            current_url = self.page.url
            if "/jobs/search" not in current_url:
                # Search for jobs using keywords
                keywords_str = " OR ".join(criteria.keywords)
                locations_str = ", ".join(criteria.locations)
                
                try:
                    # Try multiple selector patterns for search fields
                    search_selectors = [
                        'input[aria-label*="Search by title"]',
                        'input[placeholder*="Search by title"]', 
                        'input[aria-label*="Search jobs"]',
                        'input[aria-label*="Job title"]',
                        'input[data-test*="job-search"]',
                        '.jobs-search-box__text-input[aria-label*="Search"]'
                    ]
                    
                    location_selectors = [
                        'input[aria-label*="City"]',
                        'input[placeholder*="City"]',
                        'input[aria-label*="Location"]',
                        'input[placeholder*="Location"]',
                        'input[data-test*="location"]'
                    ]
                    
                    # Try to fill search field
                    search_filled = False
                    for selector in search_selectors:
                        try:
                            await self.page.wait_for_selector(selector, timeout=5000)
                            await self.page.fill(selector, keywords_str, timeout=5000)
                            search_filled = True
                            self.logger.info(f"Filled search with selector: {selector}")
                            break
                        except:
                            continue
                    
                    # Try to fill location field
                    location_filled = False
                    for selector in location_selectors:
                        try:
                            await self.page.wait_for_selector(selector, timeout=5000)
                            await self.page.fill(selector, locations_str, timeout=5000)
                            location_filled = True
                            self.logger.info(f"Filled location with selector: {selector}")
                            break
                        except:
                            continue
                    
                    if search_filled:
                        # Press enter to search
                        await self.page.keyboard.press('Enter')
                        await self.page.wait_for_timeout(3000)
                        await self.page.wait_for_load_state('domcontentloaded', timeout=30000)
                    
                except Exception as e:
                    self.logger.warning(f"Search form filling failed: {str(e)}, trying to extract jobs from current page")
            
            # Wait a moment for any dynamic content to load
            await self.page.wait_for_timeout(3000)
            
            # Apply filters - following n8n Click operations
            await self._apply_search_filters(criteria)
            
            # Extract job listings
            jobs = await self._extract_job_listings()
            
            self.logger.info(f"Found {len(jobs)} jobs on LinkedIn")
            return jobs
            
        except Exception as e:
            self.logger.error(f"LinkedIn job search error: {str(e)}")
            return []
    
    async def _apply_search_filters(self, criteria: SearchCriteria):
        """Apply search filters similar to n8n Click operations"""
        try:
            # Wait for filters to be available
            await self.page.wait_for_timeout(2000)
            
            # Easy Apply filter (most important from n8n workflow)
            if criteria.easy_apply_only:
                try:
                    # Look for Easy Apply filter button
                    easy_apply_selectors = [
                        'button[aria-label*="Easy Apply"]',
                        'button:has-text("Easy Apply")',
                        'label:has-text("Easy Apply")',
                        '[data-test-id*="easy-apply"]'
                    ]
                    
                    for selector in easy_apply_selectors:
                        if await self.page.is_visible(selector):
                            await self.page.click(selector)
                            self.logger.info("Applied Easy Apply filter")
                            break
                    
                except Exception as e:
                    self.logger.warning(f"Could not apply Easy Apply filter: {str(e)}")
            
            # Date posted filter (from n8n workflow: "Past week")
            if criteria.date_posted:
                try:
                    # Click on "Date posted" filter
                    await self.page.click('button:has-text("Date posted"), button[aria-label*="Date posted"]')
                    await self.page.wait_for_timeout(1000)
                    
                    # Select the appropriate time period
                    date_option_map = {
                        "Past 24 hours": "Past 24 hours",
                        "Past week": "Past week", 
                        "Past month": "Past month"
                    }
                    
                    option_text = date_option_map.get(criteria.date_posted, "Past week")
                    await self.page.click(f'input[value*="{option_text}"], label:has-text("{option_text}")')
                    self.logger.info(f"Applied date filter: {option_text}")
                    
                except Exception as e:
                    self.logger.warning(f"Could not apply date filter: {str(e)}")
            
            # Experience level filter
            if criteria.experience_level:
                try:
                    await self.page.click('button:has-text("Experience level")')
                    await self.page.wait_for_timeout(1000)
                    await self.page.click(f'label:has-text("{criteria.experience_level}")')
                    self.logger.info(f"Applied experience filter: {criteria.experience_level}")
                except Exception as e:
                    self.logger.warning(f"Could not apply experience filter: {str(e)}")
            
            # Remote work filter
            if criteria.remote_options:
                try:
                    await self.page.click('button:has-text("On-site/remote")')
                    await self.page.wait_for_timeout(1000)
                    await self.page.click(f'label:has-text("{criteria.remote_options}")')
                    self.logger.info(f"Applied remote filter: {criteria.remote_options}")
                except Exception as e:
                    self.logger.warning(f"Could not apply remote filter: {str(e)}")
            
            # Wait for filters to apply
            await self.page.wait_for_timeout(3000)
            
        except Exception as e:
            self.logger.error(f"Error applying filters: {str(e)}")
    
    async def _extract_job_listings(self) -> List[JobPosting]:
        """Extract job listings from LinkedIn search results"""
        jobs = []
        
        try:
            # Try multiple selectors for job results container
            results_selectors = [
                '.jobs-search__results-list',
                '.jobs-search-results-list', 
                '.jobs-search-results__list',
                '.search-results-container',
                '[data-test-results-list]',
                '.job-search-results-list'
            ]
            
            results_container = None
            for selector in results_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    results_container = selector
                    self.logger.info(f"Found results container: {selector}")
                    break
                except:
                    continue
            
            if not results_container:
                # Try to find any job-related elements
                await self.page.wait_for_timeout(5000)
                self.logger.warning("Could not find standard results container, trying generic job selectors")
            
            # Try multiple selectors for individual job cards
            job_card_selectors = [
                'li[data-occludable-job-id]',  # Primary LinkedIn job cards
                '[data-job-id]',  # Alternative job elements
                '.job-search-card',
                '.jobs-search-results__list-item',
                '.job-result-card',
                '.base-search-card'
            ]
            
            job_cards = []
            for selector in job_card_selectors:
                try:
                    cards = await self.page.query_selector_all(selector)
                    if cards:
                        job_cards = cards
                        self.logger.info(f"Found {len(cards)} job cards with selector: {selector}")
                        break
                except:
                    continue
            
            for card in job_cards[:20]:  # Limit to first 20 jobs
                try:
                    job = await self._extract_single_job(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    self.logger.warning(f"Error extracting job: {str(e)}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error extracting job listings: {str(e)}")
        
        return jobs
    
    async def _extract_single_job(self, card) -> Optional[JobPosting]:
        """Extract information from a single job card"""
        try:
            # Extract job title - try multiple selectors
            title_selectors = [
                'a[data-test-id*="job-title"]',
                '.job-search-card__title a', 
                '.job-title a',
                'h3 a',
                'a[aria-label*="job"]',
                'a:has-text("Engineer")'  # fallback for engineer jobs
            ]
            
            title_element = None
            for selector in title_selectors:
                title_element = await card.query_selector(selector)
                if title_element:
                    break
            
            if not title_element:
                # Try to get any link within the card
                title_element = await card.query_selector('a')
                if not title_element:
                    return None
            
            title = await title_element.inner_text()
            job_url = await title_element.get_attribute('href')
            
            # Make URL absolute
            if job_url and not job_url.startswith('http'):
                job_url = urljoin('https://www.linkedin.com', job_url)
            
            # Extract job ID from URL
            job_id = self._extract_job_id_from_url(job_url)
            
            # Extract company name - try multiple selectors
            company_selectors = [
                '[data-test-id*="company"]',
                '.job-search-card__subtitle',
                '.job-subtitle', 
                'h4',
                '.base-search-card__subtitle'
            ]
            
            company = "Unknown"
            for selector in company_selectors:
                company_element = await card.query_selector(selector)
                if company_element:
                    company = await company_element.inner_text()
                    break
            
            # Extract location - try multiple selectors  
            location_selectors = [
                '[data-test-id*="location"]',
                '.job-search-card__location',
                '.job-location',
                '.base-search-card__location'
            ]
            
            location = "Unknown"
            for selector in location_selectors:
                location_element = await card.query_selector(selector)
                if location_element:
                    location = await location_element.inner_text()
                    break
            
            # For now, assume all jobs allow Easy Apply since we're on a filtered page
            # We'll check this during application attempt
            
            return JobPosting(
                job_id=job_id,
                title=title.strip(),
                company=company.strip(),
                location=location.strip(),
                url=job_url,
                platform="LinkedIn"
            )
            
        except Exception as e:
            self.logger.warning(f"Error extracting single job: {str(e)}")
            return None
    
    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract LinkedIn job ID from URL"""
        try:
            # LinkedIn job URLs typically contain the job ID
            # Example: https://www.linkedin.com/jobs/view/1234567890/
            if '/jobs/view/' in url:
                return url.split('/jobs/view/')[1].split('/')[0].split('?')[0]
            else:
                # Fallback: use the entire URL as ID
                return url.split('/')[-1].split('?')[0]
        except:
            return url
    
    async def apply_to_job(self, job: JobPosting) -> bool:
        """
        Apply to a specific job using Easy Apply
        Handles Greenhouse verification if needed
        """
        try:
            self.logger.info(f"Applying to {job.title} at {job.company}")
            
            # Navigate to job page
            await self.page.goto(job.url)
            await self.page.wait_for_load_state('networkidle')
            
            # Click Easy Apply button
            easy_apply_selectors = [
                '.jobs-apply-button--top-card',
                'button:has-text("Easy Apply")',
                '[data-test-id*="easy-apply"]',
                '.jobs-apply-button'
            ]
            
            clicked = False
            for selector in easy_apply_selectors:
                try:
                    if await self.page.is_visible(selector):
                        await self.page.click(selector)
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                self.logger.warning(f"Could not find Easy Apply button for {job.title}")
                return False
            
            # Wait for application form to load
            await self.page.wait_for_timeout(2000)
            
            # Handle application process
            success = await self._handle_application_flow(job)
            
            if success:
                self.logger.info(f"Successfully applied to {job.title}")
            else:
                self.logger.warning(f"Application to {job.title} may have failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error applying to {job.title}: {str(e)}")
            return False
    
    async def _handle_application_flow(self, job: JobPosting) -> bool:
        """Handle the multi-step application flow"""
        try:
            max_steps = 5
            current_step = 0
            
            while current_step < max_steps:
                # Check if we're done
                if await self._is_application_complete():
                    return True
                
                # Check for Greenhouse verification
                if self.email_verifier and await self._is_greenhouse_verification():
                    verification_success = await self.email_verifier.handle_greenhouse_verification(self.page)
                    if verification_success:
                        await self.page.wait_for_timeout(3000)
                        continue
                    else:
                        self.logger.error("Greenhouse verification failed")
                        return False
                
                # Fill form fields if present
                await self._fill_application_form()
                
                # Look for Next/Submit/Review buttons
                next_clicked = await self._click_next_button()
                if not next_clicked:
                    # Try to submit
                    submit_clicked = await self._click_submit_button()
                    if submit_clicked:
                        await self.page.wait_for_timeout(3000)
                        return await self._is_application_complete()
                    else:
                        self.logger.warning("Could not find Next or Submit button")
                        return False
                
                current_step += 1
                await self.page.wait_for_timeout(2000)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in application flow: {str(e)}")
            return False
    
    async def _is_application_complete(self) -> bool:
        """Check if application is complete"""
        success_indicators = [
            'application submitted',
            'thank you for applying',
            'application received',
            'successfully submitted',
            'application complete'
        ]
        
        content = await self.page.content()
        return any(indicator in content.lower() for indicator in success_indicators)
    
    async def _is_greenhouse_verification(self) -> bool:
        """Check if current page requires Greenhouse email verification"""
        url = self.page.url
        content = await self.page.content()
        
        greenhouse_indicators = [
            'greenhouse.io' in url.lower(),
            'verify your email' in content.lower(),
            'check your email' in content.lower(),
            'verification link' in content.lower()
        ]
        
        return any(greenhouse_indicators)
    
    async def _fill_application_form(self):
        """Fill common application form fields"""
        try:
            app_settings = self.config.get('application', {}).get('default_answers', {})
            
            # Common form fields and their values
            form_fields = {
                'years of experience': app_settings.get('years_experience', '3-5 years'),
                'willing to relocate': 'Yes' if app_settings.get('willing_to_relocate', False) else 'No',
                'authorized to work': 'Yes' if app_settings.get('authorized_to_work', True) else 'No',
                'require sponsorship': 'Yes' if app_settings.get('require_sponsorship', False) else 'No',
                'salary expectation': app_settings.get('salary_expectation', 'Competitive'),
                'availability': app_settings.get('availability', '2 weeks notice')
            }
            
            # Try to fill text inputs
            inputs = await self.page.query_selector_all('input[type="text"], textarea')
            for input_element in inputs:
                placeholder = await input_element.get_attribute('placeholder') or ''
                label_text = await self._get_input_label(input_element)
                
                # Match field based on placeholder or label
                for field_key, field_value in form_fields.items():
                    if field_key.lower() in placeholder.lower() or field_key.lower() in label_text.lower():
                        await input_element.fill(str(field_value))
                        break
            
            # Handle dropdowns/selects
            selects = await self.page.query_selector_all('select')
            for select_element in selects:
                label_text = await self._get_input_label(select_element)
                
                for field_key, field_value in form_fields.items():
                    if field_key.lower() in label_text.lower():
                        try:
                            await select_element.select_option(label=str(field_value))
                        except:
                            # Try by value if label doesn't work
                            try:
                                await select_element.select_option(value=str(field_value))
                            except:
                                pass
                        break
            
        except Exception as e:
            self.logger.warning(f"Error filling form: {str(e)}")
    
    async def _get_input_label(self, element) -> str:
        """Get the label text associated with an input element"""
        try:
            # Try to find associated label
            element_id = await element.get_attribute('id')
            if element_id:
                label = await self.page.query_selector(f'label[for="{element_id}"]')
                if label:
                    return await label.inner_text()
            
            # Try to find parent label
            parent_label = await element.query_selector('xpath=ancestor::label[1]')
            if parent_label:
                return await parent_label.inner_text()
            
            # Try to find nearby text
            aria_label = await element.get_attribute('aria-label')
            if aria_label:
                return aria_label
                
            return ""
        except:
            return ""
    
    async def _click_next_button(self) -> bool:
        """Click Next/Continue button"""
        next_selectors = [
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'button:has-text("Review")',
            '[data-test-id*="next"]',
            '.artdeco-button--primary:has-text("Next")'
        ]
        
        for selector in next_selectors:
            try:
                if await self.page.is_visible(selector):
                    await self.page.click(selector)
                    return True
            except:
                continue
        
        return False
    
    async def _click_submit_button(self) -> bool:
        """Click Submit/Apply button"""
        submit_selectors = [
            'button:has-text("Submit application")',
            'button:has-text("Submit")',
            'button:has-text("Apply")', 
            'button:has-text("Send application")',
            '[data-test-id*="submit"]',
            '.artdeco-button--primary:has-text("Submit")'
        ]
        
        for selector in submit_selectors:
            try:
                if await self.page.is_visible(selector):
                    await self.page.click(selector)
                    return True
            except:
                continue
        
        return False
    
    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """Get detailed job information from job page"""
        try:
            await self.page.goto(job_url)
            await self.page.wait_for_load_state('networkidle')
            
            # Extract detailed information
            title_element = await self.page.query_selector('.job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title')
            title = await title_element.inner_text() if title_element else "Unknown"
            
            company_element = await self.page.query_selector('.job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name')
            company = await company_element.inner_text() if company_element else "Unknown"
            
            location_element = await self.page.query_selector('.job-details-jobs-unified-top-card__bullet, .jobs-unified-top-card__bullet')
            location = await location_element.inner_text() if location_element else "Unknown"
            
            # Extract job description
            description_element = await self.page.query_selector('.jobs-description-content__text, .jobs-description__content')
            description = await description_element.inner_text() if description_element else None
            
            job_id = self._extract_job_id_from_url(job_url)
            
            return JobPosting(
                job_id=job_id,
                title=title.strip(),
                company=company.strip(),
                location=location.strip(), 
                url=job_url,
                description=description,
                platform="LinkedIn"
            )
            
        except Exception as e:
            self.logger.error(f"Error getting job details: {str(e)}")
            return None