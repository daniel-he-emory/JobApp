import imaplib
import email
import re
import time
from typing import Optional, Dict, Any
import logging
from urllib.parse import urlparse


class GreenHouseEmailVerifier:
    """
    Handles email verification for Greenhouse job applications
    Connects to Gmail to find verification emails and extract links
    """

    def __init__(self, config: Dict[str, Any]):
        self.email_address = config.get('address')
        self.email_password = config.get('password')
        self.imap_server = config.get('imap_server', 'imap.gmail.com')
        self.imap_port = config.get('imap_port', 993)
        self.logger = logging.getLogger(__name__)

    def connect_to_email(self) -> Optional[imaplib.IMAP4_SSL]:
        """Connect to email server"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
            return mail
        except Exception as e:
            self.logger.error(f"Failed to connect to email: {str(e)}")
            return None

    def find_verification_email(self, timeout_minutes: int = 5) -> Optional[str]:
        """
        Search for Greenhouse verification email and extract verification link
        Returns the verification URL if found, None otherwise
        """
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        while time.time() - start_time < timeout_seconds:
            mail = self.connect_to_email()
            if not mail:
                time.sleep(10)
                continue

            try:
                mail.select('inbox')

                # Search for recent emails from Greenhouse
                search_criteria = [
                    '(FROM "greenhouse.io")',
                    '(FROM "greenhouse")',
                    '(SUBJECT "verify")',
                    '(SUBJECT "confirmation")',
                    '(SUBJECT "application")'
                ]

                for criteria in search_criteria:
                    # Search for emails from the last hour
                    status, messages = mail.search(None, criteria)
                    if status == 'OK' and messages[0]:
                        message_ids = messages[0].split()

                        # Check the most recent emails first
                        # Check last 10 emails
                        for msg_id in reversed(message_ids[-10:]):
                            verification_link = self._extract_verification_link(
                                mail, msg_id)
                            if verification_link:
                                mail.logout()
                                return verification_link

                mail.logout()

            except Exception as e:
                self.logger.error(f"Error searching emails: {str(e)}")
                if mail:
                    try:
                        mail.logout()
                    except:
                        pass

            # Wait before checking again
            time.sleep(30)

        self.logger.warning(
            f"No verification email found within {timeout_minutes} minutes")
        return None

    def _extract_verification_link(self, mail: imaplib.IMAP4_SSL, msg_id: bytes) -> Optional[str]:
        """Extract verification link from a specific email"""
        try:
            status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                return None

            email_body = msg_data[0][1]
            email_message = email.message_from_bytes(email_body)

            # Check if this is a Greenhouse email
            from_header = email_message.get('From', '').lower()
            subject = email_message.get('Subject', '').lower()

            if 'greenhouse' not in from_header and 'greenhouse' not in subject:
                return None

            # Extract text content
            content = self._get_email_content(email_message)
            if not content:
                return None

            # Look for verification links
            verification_patterns = [
                r'https?://[^\s]+greenhouse[^\s]*verify[^\s]*',
                r'https?://[^\s]+verify[^\s]*greenhouse[^\s]*',
                r'https?://[^\s]+confirm[^\s]*application[^\s]*',
                r'https?://boards\.greenhouse\.io/[^\s]+/verify[^\s]*',
                r'https?://[^\s]*\.greenhouse\.io[^\s]*'
            ]

            for pattern in verification_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    # Return the first match, clean it up
                    link = matches[0].strip('.,;!?')
                    if self._is_valid_verification_link(link):
                        self.logger.info(f"Found verification link: {link}")
                        return link

            # Also check for generic links in Greenhouse emails
            url_pattern = r'https?://[^\s<>"\';,!?)]+'
            urls = re.findall(url_pattern, content)
            for url in urls:
                url = url.strip('.,;!?')
                if 'greenhouse' in url.lower() and ('verify' in url.lower() or 'confirm' in url.lower()):
                    if self._is_valid_verification_link(url):
                        self.logger.info(f"Found verification link: {url}")
                        return url

        except Exception as e:
            self.logger.error(f"Error extracting verification link: {str(e)}")

        return None

    def _get_email_content(self, email_message) -> str:
        """Extract text content from email message"""
        content = ""

        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain" or content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            content += payload.decode('utf-8',
                                                      errors='ignore') + "\n"
                    except Exception:
                        continue
        else:
            try:
                payload = email_message.get_payload(decode=True)
                if payload:
                    content = payload.decode('utf-8', errors='ignore')
            except Exception:
                pass

        return content

    def _is_valid_verification_link(self, url: str) -> bool:
        """Validate that the URL looks like a legitimate verification link"""
        try:
            parsed = urlparse(url)

            # Must be HTTPS for security
            if parsed.scheme != 'https':
                return False

            # Must have a valid domain
            if not parsed.netloc:
                return False

            # Should contain greenhouse-related domains or verification keywords
            domain_lower = parsed.netloc.lower()
            path_lower = parsed.path.lower()
            query_lower = parsed.query.lower()

            greenhouse_indicators = [
                'greenhouse.io' in domain_lower,
                'greenhouse' in domain_lower,
                'verify' in path_lower or 'verify' in query_lower,
                'confirm' in path_lower or 'confirm' in query_lower
            ]

            return any(greenhouse_indicators)

        except Exception:
            return False

    async def handle_greenhouse_verification(self, page, timeout_minutes: int = 5) -> bool:
        """
        Check if current page is a Greenhouse verification page
        If so, find verification email and navigate to the link
        Returns True if verification was successful, False otherwise
        """
        try:
            # Check if current page is a Greenhouse verification page
            url = page.url
            content = await page.content()

            greenhouse_verification_indicators = [
                'greenhouse.io' in url.lower(),
                'verify your email' in content.lower(),
                'check your email' in content.lower(),
                'verification link' in content.lower(),
                'confirm your application' in content.lower()
            ]

            if not any(greenhouse_verification_indicators):
                return False

            self.logger.info(
                "Detected Greenhouse verification page, checking email...")

            # Find verification email
            verification_link = self.find_verification_email(timeout_minutes)

            if verification_link:
                self.logger.info(
                    f"Navigating to verification link: {verification_link}")
                await page.goto(verification_link)

                # Wait for page to load and check if verification was successful
                await page.wait_for_timeout(3000)

                # Check for success indicators
                new_content = await page.content()
                success_indicators = [
                    'verified successfully' in new_content.lower(),
                    'verification complete' in new_content.lower(),
                    'thank you' in new_content.lower(),
                    'application submitted' in new_content.lower()
                ]

                if any(success_indicators):
                    self.logger.info("Email verification successful")
                    return True
                else:
                    self.logger.warning("Email verification may have failed")
                    return False
            else:
                self.logger.error("Could not find verification email")
                return False

        except Exception as e:
            self.logger.error(
                f"Error handling Greenhouse verification: {str(e)}")
            return False
