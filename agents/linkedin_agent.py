from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from playwright.async_api import Error as PlaywrightError
from base_agent import JobAgent, JobPosting, SearchCriteria
from utils.email_verifier import GreenHouseEmailVerifier


class LinkedInAgent(JobAgent):
    """
    LinkedIn job application agent
    Implements the workflow from n8n: Login -> Search -> Filter -> Apply
    """

    def __init__(self, config: Dict[str, Any],
                 proxy_config: Optional[Dict[str, str]] = None):
        super().__init__(config, proxy_config)
        self.platform_name = "LinkedIn"

        # Email verifier for Greenhouse applications
        email_config = config.get('credentials', {}).get(
            'verification_email', {})
        if email_config.get('address'):
            self.email_verifier = GreenHouseEmailVerifier(email_config)
        else:
            self.email_verifier = None
            self.logger.warning("No email verification configured")

    async def login(self) -> bool:
        """Login to LinkedIn using credentials from config"""
        try:
            credentials = self.config.get(
                'credentials', {}).get('linkedin', {})
            if not credentials.get('email') or not credentials.get('password'):
                self.logger.error("LinkedIn credentials not found in config")
                return False

            self.logger.info("Navigating to LinkedIn login page")
            await self.page.goto("https://www.linkedin.com/login",
                                 timeout=30000)
            await self.page.wait_for_load_state(
                'domcontentloaded', timeout=30000)
            # Give page time to fully load
            await self.page.wait_for_timeout(2000)

            # Fill login form
            await self.page.fill('input[name="session_key"]',
                                 credentials['email'])
            await self.page.fill('input[name="session_password"]',
                                 credentials['password'])

            # Click login button
            await self.page.click('button[type="submit"]')
            await self.page.wait_for_timeout(3000)

            # Check for and handle CAPTCHA after login attempt
            await self.handle_captcha_if_present()

            # Check if login was successful
            current_url = self.page.url
            if ('linkedin.com/feed' in current_url or
                    'linkedin.com/jobs' in current_url):
                self.logger.info("LinkedIn login successful")
                return True
            elif 'checkpoint' in current_url or 'verify' in current_url:
                self.logger.warning(
                    "LinkedIn login requires additional verification")
                # Handle 2FA or verification if needed
                # Wait for manual intervention
                await self.page.wait_for_timeout(10000)
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
                await self.page.goto("https://www.linkedin.com/jobs/",
                                     timeout=60000)
                await self.page.wait_for_load_state(
                    'networkidle', timeout=30000)
            except Exception as e:
                self.logger.warning(
                    f"Initial navigation slow: {str(e)}, continuing...")
                # Try to wait for basic page elements instead
                try:
                    await self.page.wait_for_selector(
                        ('input[aria-label*="Search"], '
                         'input[placeholder*="Search"]'),
                        timeout=30000)
                except PlaywrightError as e:
                    # Try direct search URL approach
                    self.logger.debug(f"Search selector wait failed: {e}")
                    search_url = (
                        "https://www.linkedin.com/jobs/search/"
                        "?keywords=Solutions%20Engineer"
                        "&location=San%20Francisco%20Bay%20Area")
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
                            await self.page.wait_for_selector(
                                selector, timeout=5000)
                            await self.page.fill(
                                selector, keywords_str, timeout=5000)
                            search_filled = True
                            self.logger.info(
                                f"Filled search with selector: {selector}")
                            break
                        except PlaywrightError as e:
                            self.logger.debug(f"Search selector failed: {e}")
                            continue

                    # Try to fill location field
                    for selector in location_selectors:
                        try:
                            await self.page.wait_for_selector(
                                selector, timeout=5000)
                            await self.page.fill(
                                selector, locations_str, timeout=5000)
                            self.logger.info(
                                f"Filled location with selector: {selector}")
                            break
                        except PlaywrightError as e:
                            self.logger.debug(f"Location selector failed: {e}")
                            continue

                    if search_filled:
                        # Press enter to search
                        await self.page.keyboard.press('Enter')
                        await self.page.wait_for_timeout(3000)
                        await self.page.wait_for_load_state(
                            'domcontentloaded', timeout=30000)

                except Exception as e:
                    self.logger.warning(
                        f"Search form filling failed: {str(e)}, "
                        "trying to extract jobs from current page")

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
            await self.page.wait_for_timeout(3000)

            # Try to use URL-based filtering first (more reliable)
            current_url = self.page.url
            filters_applied = await self._apply_url_filters(
                criteria, current_url)

            if filters_applied:
                self.logger.info("Applied filters via URL modification")
                return

            # Fallback to UI-based filtering with shorter timeouts
            # Easy Apply filter (most important from n8n workflow)
            if criteria.easy_apply_only:
                try:
                    # Look for Easy Apply filter button with shorter timeout
                    easy_apply_selectors = [
                        'button[aria-label*="Easy Apply"]',
                        'button:has-text("Easy Apply")',
                        'label:has-text("Easy Apply")',
                        '[data-test-id*="easy-apply"]',
                        '.filter-button:has-text("Easy Apply")',
                        'input[value="Easy Apply"]'
                    ]

                    filter_applied = False
                    for selector in easy_apply_selectors:
                        try:
                            await self.page.wait_for_selector(
                                selector, timeout=3000)
                            if await self.page.is_visible(selector):
                                await self.page.click(selector, timeout=3000)
                                self.logger.info("Applied Easy Apply filter")
                                filter_applied = True
                                break
                        except PlaywrightError as e:
                            self.logger.debug(
                                f"Easy Apply selector failed: {e}")
                            continue

                    if not filter_applied:
                        self.logger.info(
                            "Easy Apply filter not found - continuing without it")

                except Exception as e:
                    self.logger.warning(
                        f"Could not apply Easy Apply filter: {str(e)}")

            # Skip other filters if they're causing timeouts
            # Just proceed with basic search results
            self.logger.info("Skipping additional filters to avoid timeouts")

            # Wait briefly for any applied filters to take effect
            await self.page.wait_for_timeout(2000)

        except Exception as e:
            self.logger.warning(
                f"Filter application failed: {str(e)}, "
                "proceeding with unfiltered results")

    async def _apply_url_filters(self, criteria: SearchCriteria,
                                 current_url: str) -> bool:
        """Apply filters by modifying the URL (more reliable than UI clicks)"""
        try:
            from urllib.parse import urlencode, urlparse, parse_qs

            # Parse current URL
            parsed = urlparse(current_url)
            params = parse_qs(parsed.query)

            # Add Easy Apply filter
            if criteria.easy_apply_only:
                # LinkedIn's Easy Apply filter parameter
                params['f_LF'] = ['f_AL']

            # Add date filter
            if criteria.date_posted:
                date_map = {
                    "Past 24 hours": "r86400",
                    "Past week": "r604800",
                    "Past month": "r2592000"
                }
                if criteria.date_posted in date_map:
                    params['f_TPR'] = [date_map[criteria.date_posted]]

            # Add experience level filter
            if criteria.experience_level:
                exp_map = {
                    "Internship": "1",
                    "Entry level": "2",
                    "Associate": "3",
                    "Mid-Senior level": "4",
                    "Director": "5",
                    "Executive": "6"
                }
                if criteria.experience_level in exp_map:
                    params['f_E'] = [exp_map[criteria.experience_level]]

            # Build new URL
            # Convert single-item lists back to strings for urlencode
            clean_params = {}
            for key, value_list in params.items():
                if value_list:
                    clean_params[key] = (
                        value_list[0] if len(value_list) == 1
                        else value_list)

            new_query = urlencode(clean_params, doseq=True)
            new_url = (
                f"{parsed.scheme}://{parsed.netloc}"
                f"{parsed.path}?{new_query}")

            # Navigate to filtered URL
            await self.page.goto(new_url, timeout=30000)
            await self.page.wait_for_load_state(
                'domcontentloaded', timeout=20000)
            return True

        except Exception as e:
            self.logger.warning(f"URL filtering failed: {str(e)}")
            return False

    async def _extract_job_listings(self) -> List[JobPosting]:
        """Extract job listings from LinkedIn search results"""
        jobs = []

        try:
            # Wait for page to load
            await self.page.wait_for_timeout(5000)

            # Try multiple selectors for job results container
            results_selectors = [
                '.jobs-search__results-list',
                '.jobs-search-results-list',
                '.jobs-search-results__list',
                '.search-results-container',
                '[data-test-results-list]',
                '.job-search-results-list',
                '.jobs-search-results',
                '.scaffold-layout__list-detail',
                '.jobs-search-results-list'
            ]

            results_container = None
            for selector in results_selectors:
                try:
                    if await self.page.query_selector_all(selector):
                        results_container = selector
                        self.logger.info(
                            f"Found results container: {selector}")
                        break
                except (PlaywrightError, AttributeError, TypeError) as e:
                    self.logger.debug(
                        f"Results container selector failed: {e}")
                    continue

            if not results_container:
                self.logger.warning(
                    ("Could not find standard results container, "
                     "trying generic job selectors"))

            # Try multiple selectors for individual job cards
            job_card_selectors = [
                'li[data-occludable-job-id]',  # Primary LinkedIn job cards
                '[data-job-id]',  # Alternative job elements
                '.job-search-card',
                '.jobs-search-results__list-item',
                '.job-result-card',
                '.base-search-card',
                'li[data-entity-urn*="job"]',  # Updated LinkedIn format
                'div[data-entity-urn*="job"]',
                '.entity-result',
                '.result-card',
                'article[data-entity-urn]',
                '.scaffold-layout__list-item',
                'li.jobs-search-results__list-item',
                'div.job-search-card'
            ]

            job_cards = []
            for selector in job_card_selectors:
                try:
                    cards = await self.page.query_selector_all(selector)
                    if cards and len(cards) > 0:
                        job_cards = cards
                        self.logger.info(
                            f"Found {len(cards)} job cards "
                            f"with selector: {selector}")
                        break
                except (PlaywrightError, AttributeError, TypeError) as e:
                    self.logger.debug(f"Job card selector failed: {e}")
                    continue

            # If no structured job cards, try to find job links
            if not job_cards:
                self.logger.info(
                    ("No job cards found, "
                     "trying to find job links directly"))
                try:
                    job_links = await self.page.query_selector_all(
                        'a[href*="/jobs/view/"]')
                    if job_links:
                        self.logger.info(
                            f"Found {len(job_links)} job links as fallback")
                        # Extract minimal job info from links
                        for link in job_links[:20]:
                            try:
                                title = await link.inner_text()
                                url = await link.get_attribute('href')
                                if url and not url.startswith('http'):
                                    url = urljoin(
                                        'https://www.linkedin.com', url)

                                job_id = self._extract_job_id_from_url(url)
                                if title and url and job_id:
                                    jobs.append(JobPosting(
                                        job_id=job_id,
                                        title=title.strip(),
                                        company="Unknown",
                                        location="Unknown",
                                        url=url,
                                        platform="LinkedIn"
                                    ))
                            except (PlaywrightError, AttributeError,
                                    TypeError) as e:
                                self.logger.debug(
                                    f"Job link extraction failed: {e}")
                                continue
                        return jobs
                except (PlaywrightError, AttributeError, TypeError) as e:
                    self.logger.debug(f"Job links fallback failed: {e}")
                    pass

            # Process job cards
            processed_count = 0
            for card in job_cards[:20]:  # Limit to first 20 jobs
                try:
                    job = await self._extract_single_job(card)
                    if job:
                        jobs.append(job)
                        processed_count += 1
                except Exception as e:
                    self.logger.debug(f"Error extracting job: {str(e)}")
                    continue

            self.logger.info(
                f"Successfully extracted {processed_count} jobs "
                f"from {len(job_cards)} cards")

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

            # For now, assume all jobs allow Easy Apply since we're on a
            # filtered page. We'll check this during application attempt

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
        except (AttributeError, TypeError, ValueError) as e:
            self.logger.debug(f"Job ID extraction failed: {e}")
            return url

    async def apply_to_job(self, job: JobPosting,
                           ai_content: Optional[Dict[str, str]] = None) -> bool:
        """
        Apply to a specific job using Easy Apply
        Handles Greenhouse verification and AI-generated content if provided

        Args:
            job: JobPosting object with job details
            ai_content: Optional AI-generated content
                       (cover letter, optimized resume sections)
        """
        try:
            self.logger.info(f"Applying to {job.title} at {job.company}")

            # Navigate to job page
            await self.page.goto(job.url)
            await self.page.wait_for_load_state('networkidle')

            # Check for CAPTCHA after navigation
            await self.handle_captcha_if_present()

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
                except PlaywrightError as e:
                    self.logger.debug(
                        f"Easy Apply button selector failed: {e}")
                    continue

            if not clicked:
                self.logger.warning(
                    f"Could not find Easy Apply button for {job.title}")
                return False

            # Wait for application form to load
            await self.page.wait_for_timeout(2000)

            # Handle application process with AI content
            success = await self._handle_application_flow(job, ai_content)

            if success:
                self.logger.info(f"Successfully applied to {job.title}")
            else:
                self.logger.warning(
                    f"Application to {job.title} may have failed")

            return success

        except Exception as e:
            self.logger.error(f"Error applying to {job.title}: {str(e)}")
            return False

    async def _handle_application_flow(
            self, job: JobPosting,
            ai_content: Optional[Dict[str, str]] = None) -> bool:
        """Handle the multi-step application flow with AI-generated content"""
        try:
            max_steps = 5
            current_step = 0

            while current_step < max_steps:
                # Check if we're done
                if await self._is_application_complete():
                    return True

                # Check for Greenhouse verification
                if (self.email_verifier and
                        await self._is_greenhouse_verification()):
                    verification_success = (
                        await self.email_verifier
                        .handle_greenhouse_verification(self.page))
                    if verification_success:
                        await self.page.wait_for_timeout(3000)
                        continue
                    else:
                        self.logger.error("Greenhouse verification failed")
                        return False

                # Fill form fields if present, using AI content when available
                await self._fill_application_form(ai_content)

                # Look for Next/Submit/Review buttons
                next_clicked = await self._click_next_button()
                if not next_clicked:
                    # Try to submit
                    submit_clicked = await self._click_submit_button()
                    if submit_clicked:
                        await self.page.wait_for_timeout(3000)
                        return await self._is_application_complete()
                    else:
                        self.logger.warning(
                            "Could not find Next or Submit button")
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
        return any(indicator in content.lower()
                   for indicator in success_indicators)

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

    async def _fill_application_form(
            self, ai_content: Optional[Dict[str, str]] = None):
        """Fill common application form fields with AI-generated content
        when available"""
        try:
            # First, try to fill AI-generated content if provided
            if ai_content:
                await self._fill_ai_content(ai_content)

            app_settings = self.config.get(
                'application', {}).get('default_answers', {})

            # Common form fields and their values
            form_fields = {
                'years of experience': app_settings.get(
                    'years_experience', '3-5 years'),
                'willing to relocate': ('Yes' if app_settings.get(
                    'willing_to_relocate', False) else 'No'),
                'authorized to work': ('Yes' if app_settings.get(
                    'authorized_to_work', True) else 'No'),
                'require sponsorship': ('Yes' if app_settings.get(
                    'require_sponsorship', False) else 'No'),
                'salary expectation': app_settings.get(
                    'salary_expectation', 'Competitive'),
                'availability': app_settings.get(
                    'availability', '2 weeks notice')
            }

            # Try to fill text inputs
            inputs = await self.page.query_selector_all(
                'input[type="text"], textarea')
            for input_element in inputs:
                placeholder = (
                    await input_element.get_attribute('placeholder') or '')
                label_text = await self._get_input_label(input_element)

                # Match field based on placeholder or label
                for field_key, field_value in form_fields.items():
                    if (field_key.lower() in placeholder.lower() or
                            field_key.lower() in label_text.lower()):
                        await input_element.fill(str(field_value))
                        break

            # Handle dropdowns/selects
            selects = await self.page.query_selector_all('select')
            for select_element in selects:
                label_text = await self._get_input_label(select_element)

                for field_key, field_value in form_fields.items():
                    if field_key.lower() in label_text.lower():
                        try:
                            await select_element.select_option(
                                label=str(field_value))
                        except PlaywrightError:
                            # Try by value if label doesn't work
                            try:
                                await select_element.select_option(
                                    value=str(field_value))
                            except PlaywrightError as e:
                                self.logger.debug(
                                    f"Select option failed: {e}")
                                pass
                        break

        except Exception as e:
            self.logger.warning(f"Error filling form: {str(e)}")

    async def _fill_ai_content(self, ai_content: Dict[str, str]) -> None:
        """Fill form fields with AI-generated content"""
        try:
            if not ai_content:
                return

            self.logger.info(
                "Filling application form with AI-generated content")

            # Get all text inputs and textareas
            form_elements = await self.page.query_selector_all(
                'textarea, input[type="text"]')

            # Track which fields we've filled
            filled_cover_letter = False
            filled_resume_section = False

            for element in form_elements:
                try:
                    # Get element attributes for identification
                    element_id = await element.get_attribute('id') or ''
                    element_name = await element.get_attribute('name') or ''
                    element_class = await element.get_attribute('class') or ''
                    placeholder = (
                        await element.get_attribute('placeholder') or '')
                    aria_label = (
                        await element.get_attribute('aria-label') or '')

                    # Get associated label text
                    label_text = await self._get_input_label(element)

                    # Combine all text for field identification
                    field_identifiers = (
                        f"{element_id} {element_name} {element_class} "
                        f"{placeholder} {aria_label} {label_text}").lower()

                    # Check if this is a cover letter field
                    cover_letter_indicators = [
                        'cover letter', 'coverletter', 'cover_letter',
                        'motivation', 'why do you want', 'why are you interested',
                        'personal statement', 'message to hiring manager',
                        'additional information', 'tell us about yourself'
                    ]

                    if (not filled_cover_letter and
                            'cover_letter' in ai_content):
                        if any(indicator in field_identifiers
                               for indicator in cover_letter_indicators):
                            self.logger.info(
                                ("Found cover letter field, "
                                 "filling with AI-generated content"))
                            await element.fill(ai_content['cover_letter'])
                            filled_cover_letter = True
                            # Brief pause
                            await self.page.wait_for_timeout(1000)
                            continue

                    # Check if this is a resume/experience field
                    resume_indicators = [
                        'resume', 'experience', 'relevant experience',
                        'background', 'qualifications', 'skills',
                        'work experience', 'professional experience',
                        'paste your resume', 'upload resume text',
                        'summary', 'professional summary'
                    ]

                    # Use optimized summary or skills if available
                    resume_content = None
                    if 'optimized_summary' in ai_content:
                        resume_content = ai_content['optimized_summary']
                    elif 'optimized_skills' in ai_content:
                        resume_content = ai_content['optimized_skills']

                    if not filled_resume_section and resume_content:
                        # Check if this is a large text area
                        # (likely for resume/experience)
                        tag_name = await element.evaluate(
                            'el => el.tagName.toLowerCase()')

                        if (tag_name == 'textarea' and
                                any(indicator in field_identifiers
                                    for indicator in resume_indicators)):
                            self.logger.info(
                                ("Found resume/experience field, "
                                 "filling with AI-optimized content"))
                            await element.fill(resume_content)
                            filled_resume_section = True
                            # Brief pause
                            await self.page.wait_for_timeout(1000)
                            continue

                except Exception as e:
                    self.logger.warning(
                        f"Error processing form element: {e}")
                    continue

            # Log what was filled
            if filled_cover_letter:
                self.logger.info(
                    "Successfully filled cover letter with AI content")
            if filled_resume_section:
                self.logger.info(
                    ("Successfully filled resume section "
                     "with AI-optimized content"))

            if not filled_cover_letter and not filled_resume_section:
                self.logger.info(
                    ("No suitable fields found for AI content, "
                     "will use standard form filling"))

        except Exception as e:
            self.logger.error(f"Error filling AI content: {e}")
            # Don't raise exception - fallback to standard form filling

    async def _get_input_label(self, element) -> str:
        """Get the label text associated with an input element"""
        try:
            # Try to find associated label
            element_id = await element.get_attribute('id')
            if element_id:
                label = await self.page.query_selector(
                    f'label[for="{element_id}"]')
                if label:
                    return await label.inner_text()

            # Try to find parent label
            parent_label = await element.query_selector(
                'xpath=ancestor::label[1]')
            if parent_label:
                return await parent_label.inner_text()

            # Try to find nearby text
            aria_label = await element.get_attribute('aria-label')
            if aria_label:
                return aria_label

            return ""
        except (PlaywrightError, AttributeError, TypeError) as e:
            self.logger.debug(f"Label extraction failed: {e}")
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
            except PlaywrightError as e:
                self.logger.debug(f"Next button click failed: {e}")
                continue

        return False

    async def _click_submit_button(self) -> bool:
        """Click Submit/Apply button"""
        # Check for CAPTCHA before submitting forms
        await self.handle_captcha_if_present()

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
            except PlaywrightError as e:
                self.logger.debug(f"Submit button click failed: {e}")
                continue

        return False

    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """Get detailed job information from job page"""
        try:
            await self.page.goto(job_url)
            await self.page.wait_for_load_state('networkidle')

            # Extract detailed information
            title_element = await self.page.query_selector(
                ('.job-details-jobs-unified-top-card__job-title, '
                 '.jobs-unified-top-card__job-title'))
            title = (await title_element.inner_text()
                     if title_element else "Unknown")

            company_element = await self.page.query_selector(
                ('.job-details-jobs-unified-top-card__company-name, '
                 '.jobs-unified-top-card__company-name'))
            company = (await company_element.inner_text()
                       if company_element else "Unknown")

            location_element = await self.page.query_selector(
                ('.job-details-jobs-unified-top-card__bullet, '
                 '.jobs-unified-top-card__bullet'))
            location = (await location_element.inner_text()
                        if location_element else "Unknown")

            # Extract job description
            description_element = await self.page.query_selector(
                ('.jobs-description-content__text, '
                 '.jobs-description__content'))
            description = (await description_element.inner_text()
                           if description_element else None)

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
