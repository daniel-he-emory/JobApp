from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from base_agent import JobAgent, JobPosting, SearchCriteria
from utils.email_verifier import GreenHouseEmailVerifier


class WellfoundAgent(JobAgent):
    """
    Wellfound (formerly AngelList) job application agent
    Specialized for startup job applications
    """

    def __init__(self, config: Dict[str, Any], proxy_config: Optional[Dict[str, str]] = None):
        super().__init__(config, proxy_config)
        self.platform_name = "Wellfound"

        # Email verifier for Greenhouse applications
        email_config = config.get('credentials', {}).get(
            'verification_email', {})
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
        """Login to Wellfound using credentials from config"""
        try:
            credentials = self.config.get(
                'credentials', {}).get('wellfound', {})
            if not credentials.get('email') or not credentials.get('password'):
                self.logger.error("Wellfound credentials not found in config")
                return False

            self.logger.info("Navigating to Wellfound login page")

            # Try multiple login page URLs
            login_urls = [
                "https://wellfound.com/login",
                "https://wellfound.com/sign_in",
                "https://angel.co/login"  # Legacy URL
            ]

            page_loaded = False
            for url in login_urls:
                try:
                    await self.page.goto(url, timeout=30000)
                    await self.page.wait_for_load_state('domcontentloaded', timeout=20000)
                    page_loaded = True
                    self.logger.info(f"Successfully loaded login page: {url}")
                    break
                except Exception as e:
                    self.logger.warning(f"Failed to load {url}: {str(e)}")
                    continue

            if not page_loaded:
                self.logger.error("Could not load any Wellfound login page")
                return False

            # Wait for login form to be available
            await self.page.wait_for_timeout(3000)

            # Try multiple selectors for email field
            email_selectors = [
                'input[name="user[email]"]',
                'input[type="email"]',
                'input[placeholder*="email"]',
                'input[id*="email"]',
                '#user_email',
                '.email-input'
            ]

            email_filled = False
            for selector in email_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    await self.page.fill(selector, credentials['email'])
                    email_filled = True
                    self.logger.info(f"Filled email with selector: {selector}")
                    break
                except:
                    continue

            if not email_filled:
                self.logger.error("Could not find email input field")
                return False

            # Try multiple selectors for password field
            password_selectors = [
                'input[name="user[password]"]',
                'input[type="password"]',
                'input[placeholder*="password"]',
                'input[id*="password"]',
                '#user_password',
                '.password-input'
            ]

            password_filled = False
            for selector in password_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    await self.page.fill(selector, credentials['password'])
                    password_filled = True
                    self.logger.info(
                        f"Filled password with selector: {selector}")
                    break
                except:
                    continue

            if not password_filled:
                self.logger.error("Could not find password input field")
                return False

            # Try multiple selectors for submit button
            submit_selectors = [
                'input[type="submit"]',
                'button:has-text("Sign in")',
                'button:has-text("Login")',
                'button:has-text("Log in")',
                '.login-button',
                '.signin-button',
                'button[type="submit"]'
            ]

            login_clicked = False
            for selector in submit_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    if await self.page.is_visible(selector):
                        await self.page.click(selector)
                        login_clicked = True
                        self.logger.info(
                            f"Clicked login with selector: {selector}")
                        break
                except:
                    continue

            if not login_clicked:
                # Try pressing Enter as fallback
                try:
                    await self.page.keyboard.press('Enter')
                    login_clicked = True
                    self.logger.info("Submitted login form with Enter key")
                except:
                    self.logger.error("Could not submit login form")
                    return False

            # Wait for login response
            await self.page.wait_for_timeout(5000)

            # Check if login was successful
            await self.page.wait_for_load_state('domcontentloaded', timeout=15000)
            current_url = self.page.url

            # Success indicators
            success_patterns = [
                'wellfound.com/jobs',
                'wellfound.com/dashboard',
                'wellfound.com/candidates',
                'wellfound.com/startup',
                'angel.co/jobs',
                'angel.co/dashboard'
            ]

            for pattern in success_patterns:
                if pattern in current_url:
                    self.logger.info("Wellfound login successful")
                    return True

            # Check for verification requirements
            verification_patterns = ['verify', 'confirm', 'check', 'email']
            page_content = (await self.page.content()).lower()

            for pattern in verification_patterns:
                if pattern in current_url or pattern in page_content:
                    self.logger.warning(
                        "Wellfound login requires verification - proceeding anyway")
                    return True

            # Check if we're still on login page (failed login)
            if 'login' in current_url or 'sign' in current_url:
                self.logger.error(
                    "Wellfound login failed - still on login page")
                return False

            # If we got here, assume success
            self.logger.info("Wellfound login appears successful")
            return True

        except Exception as e:
            self.logger.error(f"Wellfound login error: {str(e)}")
            return False

    async def search_jobs(self, criteria: SearchCriteria) -> List[JobPosting]:
        """Search for jobs on Wellfound based on criteria"""
        try:
            jobs = []

            # Navigate to Wellfound jobs page
            self.logger.info("Navigating to Wellfound jobs page")
            await self.page.goto("https://wellfound.com/jobs")
            await self.page.wait_for_load_state('networkidle')

            # Handle job search
            await self._perform_job_search(criteria)

            # Extract job listings
            jobs = await self._extract_job_listings()

            self.logger.info(f"Found {len(jobs)} jobs on Wellfound")
            return jobs

        except Exception as e:
            self.logger.error(f"Wellfound job search error: {str(e)}")
            return []

    async def _perform_job_search(self, criteria: SearchCriteria):
        """Perform job search with keywords and filters"""
        try:
            # Search by role/keywords
            keywords_str = " ".join(criteria.keywords)

            # Find and fill search input
            search_selectors = [
                'input[placeholder*="Search"]',
                'input[name="query"]',
                'input.search-input',
                '[data-test="JobSearchFilters-keywords"]'
            ]

            for selector in search_selectors:
                try:
                    if await self.page.is_visible(selector):
                        await self.page.fill(selector, keywords_str)
                        await self.page.press(selector, 'Enter')
                        break
                except:
                    continue

            await self.page.wait_for_timeout(2000)

            # Apply location filters
            if criteria.locations:
                await self._apply_location_filter(criteria.locations)

            # Apply remote work filter
            if criteria.remote_options:
                await self._apply_remote_filter(criteria.remote_options)

            # Apply experience level filter
            if criteria.experience_level:
                await self._apply_experience_filter(criteria.experience_level)

            await self.page.wait_for_timeout(3000)

        except Exception as e:
            self.logger.error(f"Error performing job search: {str(e)}")

    async def _apply_location_filter(self, locations: List[str]):
        """Apply location filters"""
        try:
            # Look for location filter
            location_selectors = [
                '[data-test="JobSearchFilters-location"]',
                'input[placeholder*="Location"]',
                'input[name="location"]'
            ]

            for selector in location_selectors:
                try:
                    if await self.page.is_visible(selector):
                        location_str = ", ".join(locations)
                        await self.page.fill(selector, location_str)
                        await self.page.press(selector, 'Enter')
                        break
                except:
                    continue

        except Exception as e:
            self.logger.warning(f"Could not apply location filter: {str(e)}")

    async def _apply_remote_filter(self, remote_option: str):
        """Apply remote work filter"""
        try:
            # Look for remote work options
            if "remote" in remote_option.lower():
                remote_selectors = [
                    'label:has-text("Remote")',
                    'input[value*="remote"]',
                    '[data-test*="remote"]'
                ]

                for selector in remote_selectors:
                    try:
                        if await self.page.is_visible(selector):
                            await self.page.click(selector)
                            break
                    except:
                        continue

        except Exception as e:
            self.logger.warning(f"Could not apply remote filter: {str(e)}")

    async def _apply_experience_filter(self, experience_level: str):
        """Apply experience level filter"""
        try:
            # Map experience levels to Wellfound options
            experience_map = {
                "entry": "Entry level",
                "mid": "Mid level",
                "senior": "Senior level",
                "lead": "Lead",
                "principal": "Principal"
            }

            # Find matching experience option
            for key, value in experience_map.items():
                if key.lower() in experience_level.lower():
                    experience_selectors = [
                        f'label:has-text("{value}")',
                        f'input[value*="{key}"]',
                        f'[data-test*="{key}"]'
                    ]

                    for selector in experience_selectors:
                        try:
                            if await self.page.is_visible(selector):
                                await self.page.click(selector)
                                return
                        except:
                            continue
                    break

        except Exception as e:
            self.logger.warning(f"Could not apply experience filter: {str(e)}")

    async def _extract_job_listings(self) -> List[JobPosting]:
        """Extract job listings from Wellfound search results"""
        jobs = []

        try:
            # Wait for job listings to load
            await self.page.wait_for_selector('.job-card, .startup-job-listing, [data-test*="job"]', timeout=10000)

            # Get all job cards
            job_selectors = [
                '.job-card',
                '.startup-job-listing',
                '[data-test*="job-listing"]',
                '.job-listing'
            ]

            job_cards = []
            for selector in job_selectors:
                cards = await self.page.query_selector_all(selector)
                if cards:
                    job_cards = cards
                    break

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
            # Extract job title and URL
            title_selectors = [
                'a.job-title',
                '.job-title a',
                '[data-test*="job-title"] a',
                'h3 a',
                'h4 a'
            ]

            title_element = None
            for selector in title_selectors:
                title_element = await card.query_selector(selector)
                if title_element:
                    break

            if not title_element:
                return None

            title = await title_element.inner_text()
            job_url = await title_element.get_attribute('href')

            # Make URL absolute
            if job_url and not job_url.startswith('http'):
                job_url = urljoin('https://wellfound.com', job_url)

            # Extract job ID from URL
            job_id = self._extract_job_id_from_url(job_url)

            # Extract company name
            company_selectors = [
                '.startup-name',
                '.company-name',
                '[data-test*="company"] a',
                '.startup-link'
            ]

            company = "Unknown"
            for selector in company_selectors:
                company_element = await card.query_selector(selector)
                if company_element:
                    company = await company_element.inner_text()
                    break

            # Extract location
            location_selectors = [
                '.location',
                '[data-test*="location"]',
                '.job-location'
            ]

            location = "Unknown"
            for selector in location_selectors:
                location_element = await card.query_selector(selector)
                if location_element:
                    location = await location_element.inner_text()
                    break

            return JobPosting(
                job_id=job_id,
                title=title.strip(),
                company=company.strip(),
                location=location.strip(),
                url=job_url,
                platform="Wellfound"
            )

        except Exception as e:
            self.logger.warning(f"Error extracting single job: {str(e)}")
            return None

    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract Wellfound job ID from URL"""
        try:
            # Wellfound job URLs typically look like:
            # https://wellfound.com/company/startup-name/jobs/1234567-job-title
            if '/jobs/' in url:
                job_part = url.split('/jobs/')[1]
                job_id = job_part.split('-')[0]
                return job_id
            else:
                # Fallback: use the entire URL as ID
                return url.split('/')[-1].split('?')[0]
        except:
            return url

    async def apply_to_job(self, job: JobPosting) -> bool:
        """Apply to a specific job on Wellfound"""
        try:
            self.logger.info(f"Applying to {job.title} at {job.company}")

            # Navigate to job page
            await self.page.goto(job.url)
            await self.page.wait_for_load_state('networkidle')

            # Look for apply button
            apply_selectors = [
                'button:has-text("Apply")',
                '.apply-button',
                '[data-test*="apply"]',
                'a:has-text("Apply to")',
                'input[value*="Apply"]'
            ]

            clicked = False
            for selector in apply_selectors:
                try:
                    if await self.page.is_visible(selector):
                        await self.page.click(selector)
                        clicked = True
                        break
                except:
                    continue

            if not clicked:
                self.logger.warning(
                    f"Could not find apply button for {job.title}")
                return False

            # Wait for application form/process
            await self.page.wait_for_timeout(3000)

            # Handle application process
            success = await self._handle_application_flow(job)

            if success:
                self.logger.info(f"Successfully applied to {job.title}")
            else:
                self.logger.warning(
                    f"Application to {job.title} may have failed")

            return success

        except Exception as e:
            self.logger.error(f"Error applying to {job.title}: {str(e)}")
            return False

    async def _handle_application_flow(self, job: JobPosting) -> bool:
        """Handle the Wellfound application flow"""
        try:
            max_steps = 5
            current_step = 0

            while current_step < max_steps:
                # Check if application is complete
                if await self._is_application_complete():
                    return True

                # Check for external redirects (like Greenhouse)
                current_url = self.page.url
                if 'greenhouse.io' in current_url or 'lever.co' in current_url:
                    # Handle external application systems
                    if self.email_verifier and 'greenhouse' in current_url:
                        verification_success = await self.email_verifier.handle_greenhouse_verification(self.page)
                        if verification_success:
                            await self.page.wait_for_timeout(3000)
                            continue
                        else:
                            self.logger.error(
                                "External application verification failed")
                            return False
                    else:
                        # For other external systems, try to proceed normally
                        await self._fill_external_application_form()

                # Fill Wellfound application form
                await self._fill_wellfound_application_form()

                # Try to proceed to next step
                next_clicked = await self._click_next_or_submit_button()
                if not next_clicked:
                    # Check if we're done
                    if await self._is_application_complete():
                        return True
                    else:
                        self.logger.warning(
                            "Could not find next/submit button")
                        return False

                current_step += 1
                await self.page.wait_for_timeout(2000)

            return False

        except Exception as e:
            self.logger.error(f"Error in application flow: {str(e)}")
            return False

    async def _fill_wellfound_application_form(self):
        """Fill Wellfound-specific application form fields"""
        try:
            app_settings = self.config.get(
                'application', {}).get('default_answers', {})

            # Common Wellfound form fields
            form_fields = {
                'why interested': 'I am excited about this opportunity and believe my skills align well with your needs.',
                'years experience': app_settings.get('years_experience', '3-5 years'),
                'salary expectation': app_settings.get('salary_expectation', 'Competitive'),
                'available start': app_settings.get('availability', '2 weeks notice'),
                'relocate': 'Yes' if app_settings.get('willing_to_relocate', False) else 'No',
                'visa sponsorship': 'Yes' if app_settings.get('require_sponsorship', False) else 'No'
            }

            # Fill text areas and inputs
            inputs = await self.page.query_selector_all('input[type="text"], textarea, input:not([type])')
            for input_element in inputs:
                placeholder = await input_element.get_attribute('placeholder') or ''
                name = await input_element.get_attribute('name') or ''
                label_text = await self._get_input_label(input_element)

                field_context = f"{placeholder} {name} {label_text}".lower()

                for field_key, field_value in form_fields.items():
                    if field_key.lower() in field_context:
                        await input_element.fill(str(field_value))
                        break

            # Handle checkboxes
            checkboxes = await self.page.query_selector_all('input[type="checkbox"]')
            for checkbox in checkboxes:
                label_text = await self._get_input_label(checkbox)

                # Handle common checkboxes
                if 'terms' in label_text.lower() or 'agree' in label_text.lower():
                    await checkbox.check()
                elif 'newsletter' in label_text.lower() or 'updates' in label_text.lower():
                    # Optional: uncheck newsletter subscriptions
                    pass

        except Exception as e:
            self.logger.warning(f"Error filling Wellfound form: {str(e)}")

    async def _fill_external_application_form(self):
        """Fill external application forms (Greenhouse, Lever, etc.)"""
        try:
            app_settings = self.config.get(
                'application', {}).get('default_answers', {})

            # Basic form filling for external systems
            inputs = await self.page.query_selector_all('input[type="text"], textarea')
            for input_element in inputs:
                placeholder = await input_element.get_attribute('placeholder') or ''
                name = await input_element.get_attribute('name') or ''

                # Try to match common fields
                field_context = f"{placeholder} {name}".lower()

                if 'first name' in field_context:
                    first_name = self.config.get('application', {}).get(
                        'personal_info', {}).get('first_name', '')
                    if first_name:
                        await input_element.fill(first_name)
                elif 'last name' in field_context:
                    last_name = self.config.get('application', {}).get(
                        'personal_info', {}).get('last_name', '')
                    if last_name:
                        await input_element.fill(last_name)
                elif 'email' in field_context:
                    email = self.config.get('credentials', {}).get(
                        'verification_email', {}).get('address', '')
                    if email:
                        await input_element.fill(email)
                elif 'phone' in field_context:
                    phone_number = self.config.get('application', {}).get(
                        'personal_info', {}).get('phone_number', '')
                    if phone_number:
                        await input_element.fill(phone_number)
                elif 'cover letter' in field_context or 'why' in field_context:
                    await input_element.fill("I am excited about this opportunity and would love to contribute to your team.")

        except Exception as e:
            self.logger.warning(f"Error filling external form: {str(e)}")

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

            # Try aria-label
            aria_label = await element.get_attribute('aria-label')
            if aria_label:
                return aria_label

            return ""
        except:
            return ""

    async def _click_next_or_submit_button(self) -> bool:
        """Click next, continue, or submit button"""
        button_selectors = [
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Continue")',
            'button:has-text("Next")',
            'input[type="submit"]',
            '[data-test*="submit"]',
            '[data-test*="apply"]'
        ]

        for selector in button_selectors:
            try:
                if await self.page.is_visible(selector):
                    await self.page.click(selector)
                    return True
            except:
                continue

        return False

    async def _is_application_complete(self) -> bool:
        """Check if application is complete"""
        success_indicators = [
            'application submitted',
            'thank you for applying',
            'application received',
            'successfully submitted',
            'application complete',
            'we\'ll be in touch',
            'application sent'
        ]

        content = await self.page.content()
        content_lower = content.lower()

        return any(indicator in content_lower for indicator in success_indicators)

    async def get_job_details(self, job_url: str) -> Optional[JobPosting]:
        """Get detailed job information from job page"""
        try:
            await self.page.goto(job_url)
            await self.page.wait_for_load_state('networkidle')

            # Extract detailed information
            title_element = await self.page.query_selector('h1, .job-title')
            title = await title_element.inner_text() if title_element else "Unknown"

            company_element = await self.page.query_selector('.startup-name, .company-name')
            company = await company_element.inner_text() if company_element else "Unknown"

            location_element = await self.page.query_selector('.location, .job-location')
            location = await location_element.inner_text() if location_element else "Unknown"

            # Extract job description
            description_element = await self.page.query_selector('.job-description, .description')
            description = await description_element.inner_text() if description_element else None

            # Extract salary if available
            salary_element = await self.page.query_selector('.salary, .compensation')
            salary = await salary_element.inner_text() if salary_element else None

            job_id = self._extract_job_id_from_url(job_url)

            return JobPosting(
                job_id=job_id,
                title=title.strip(),
                company=company.strip(),
                location=location.strip(),
                url=job_url,
                description=description,
                salary=salary,
                platform="Wellfound"
            )

        except Exception as e:
            self.logger.error(f"Error getting job details: {str(e)}")
            return None
