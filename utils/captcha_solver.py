"""
CAPTCHA Solver Utility

This module provides integration with CAPTCHA solving services like 2Captcha
for automated challenge resolution in job application workflows.
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any
from enum import Enum


class CaptchaService(Enum):
    """Supported CAPTCHA solving services"""
    TWOCAPTCHA = "2captcha"
    ANTICAPTCHA = "anticaptcha"


class CaptchaError(Exception):
    """Custom exception for CAPTCHA solving errors"""
    pass


class CaptchaSolver:
    """
    CAPTCHA solver integration for automated challenge resolution
    Supports multiple CAPTCHA services with async operations
    """

    def __init__(self, service_name: str, api_key: str):
        """
        Initialize CAPTCHA solver

        Args:
            service_name: Name of the CAPTCHA service ('2captcha', 'anticaptcha')
            api_key: API key for the service
        """
        self.service_name = service_name.lower()
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

        # Service endpoints
        self.endpoints = {
            "2captcha": {
                "submit": "https://2captcha.com/in.php",
                "result": "https://2captcha.com/res.php"
            },
            "anticaptcha": {
                "submit": "https://api.anti-captcha.com/createTask",
                "result": "https://api.anti-captcha.com/getTaskResult"
            }
        }

        if self.service_name not in self.endpoints:
            raise ValueError(f"Unsupported CAPTCHA service: {service_name}")

        self.logger.info(f"Initialized CAPTCHA solver for {service_name}")

    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> str:
        """
        Solve reCAPTCHA v2 challenge

        Args:
            site_key: The site key from the reCAPTCHA challenge
            page_url: The URL where the CAPTCHA appears

        Returns:
            The solved CAPTCHA token string

        Raises:
            CaptchaError: If solving fails or times out
        """
        if self.service_name == "2captcha":
            return await self._solve_2captcha_recaptcha_v2(site_key, page_url)
        elif self.service_name == "anticaptcha":
            return await self._solve_anticaptcha_recaptcha_v2(site_key, page_url)
        else:
            raise CaptchaError(
                f"reCAPTCHA v2 not supported for {self.service_name}")

    async def _solve_2captcha_recaptcha_v2(self, site_key: str, page_url: str) -> str:
        """
        Solve reCAPTCHA v2 using 2Captcha service

        Args:
            site_key: The site key from the reCAPTCHA challenge
            page_url: The URL where the CAPTCHA appears

        Returns:
            The solved CAPTCHA token string
        """
        self.logger.info(
            f"Starting 2Captcha reCAPTCHA v2 solve for {page_url}")

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            # Step 1: Submit CAPTCHA for solving
            submit_data = {
                "key": self.api_key,
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": page_url,
                "json": "1"
            }

            try:
                async with session.post(self.endpoints["2captcha"]["submit"], data=submit_data) as response:
                    if response.status != 200:
                        raise CaptchaError(
                            f"Failed to submit CAPTCHA: HTTP {response.status}")

                    result = await response.json()

                    if result.get("status") != 1:
                        error_msg = result.get("error_text", "Unknown error")
                        raise CaptchaError(
                            f"2Captcha submission failed: {error_msg}")

                    captcha_id = result.get("request")
                    if not captcha_id:
                        raise CaptchaError(
                            "No CAPTCHA ID returned from 2Captcha")

                    self.logger.info(
                        f"CAPTCHA submitted successfully. ID: {captcha_id}")

            except aiohttp.ClientError as e:
                raise CaptchaError(
                    f"Network error during CAPTCHA submission: {str(e)}")
            except Exception as e:
                raise CaptchaError(
                    f"Unexpected error during CAPTCHA submission: {str(e)}")

            # Step 2: Poll for result
            return await self._poll_2captcha_result(session, captcha_id)

    async def _poll_2captcha_result(self, session: aiohttp.ClientSession, captcha_id: str) -> str:
        """
        Poll 2Captcha for CAPTCHA solution result

        Args:
            session: Active HTTP session
            captcha_id: ID of the submitted CAPTCHA

        Returns:
            The solved CAPTCHA token string
        """
        max_attempts = 60  # 5 minutes maximum (5 second intervals)
        attempt = 0

        self.logger.info(f"Polling for CAPTCHA solution. ID: {captcha_id}")

        while attempt < max_attempts:
            attempt += 1

            # Wait before polling (2Captcha recommends 5 second intervals)
            await asyncio.sleep(5)

            result_data = {
                "key": self.api_key,
                "action": "get",
                "id": captcha_id,
                "json": "1"
            }

            try:
                async with session.get(self.endpoints["2captcha"]["result"], params=result_data) as response:
                    if response.status != 200:
                        self.logger.warning(
                            f"Poll attempt {attempt}: HTTP {response.status}")
                        continue

                    result = await response.json()

                    if result.get("status") == 1:
                        # CAPTCHA solved successfully
                        token = result.get("request")
                        if token:
                            self.logger.info(
                                f"CAPTCHA solved successfully after {attempt} attempts")
                            return token
                        else:
                            raise CaptchaError(
                                "CAPTCHA marked as solved but no token returned")

                    elif result.get("request") == "CAPCHA_NOT_READY":
                        # Still processing, continue polling
                        self.logger.debug(
                            f"Poll attempt {attempt}: CAPTCHA not ready yet")
                        continue

                    else:
                        # Error occurred
                        error_msg = result.get(
                            "error_text", result.get("request", "Unknown error"))
                        raise CaptchaError(
                            f"2Captcha solving failed: {error_msg}")

            except aiohttp.ClientError as e:
                self.logger.warning(
                    f"Poll attempt {attempt}: Network error - {str(e)}")
                continue
            except Exception as e:
                if "CAPTCHA" in str(e):
                    raise  # Re-raise CAPTCHA-specific errors
                self.logger.warning(
                    f"Poll attempt {attempt}: Unexpected error - {str(e)}")
                continue

        raise CaptchaError(
            f"CAPTCHA solving timeout after {max_attempts} attempts (5 minutes)")

    async def _solve_anticaptcha_recaptcha_v2(self, site_key: str, page_url: str) -> str:
        """
        Solve reCAPTCHA v2 using Anti-Captcha service

        Args:
            site_key: The site key from the reCAPTCHA challenge
            page_url: The URL where the CAPTCHA appears

        Returns:
            The solved CAPTCHA token string
        """
        self.logger.info(
            f"Starting Anti-Captcha reCAPTCHA v2 solve for {page_url}")

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            # Step 1: Submit CAPTCHA for solving
            submit_data = {
                "clientKey": self.api_key,
                "task": {
                    "type": "NoCaptchaTaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": site_key
                }
            }

            try:
                async with session.post(self.endpoints["anticaptcha"]["submit"], json=submit_data) as response:
                    if response.status != 200:
                        raise CaptchaError(
                            f"Failed to submit CAPTCHA: HTTP {response.status}")

                    result = await response.json()

                    if result.get("errorId") != 0:
                        error_msg = result.get(
                            "errorDescription", "Unknown error")
                        raise CaptchaError(
                            f"Anti-Captcha submission failed: {error_msg}")

                    task_id = result.get("taskId")
                    if not task_id:
                        raise CaptchaError(
                            "No task ID returned from Anti-Captcha")

                    self.logger.info(
                        f"CAPTCHA submitted successfully. Task ID: {task_id}")

            except aiohttp.ClientError as e:
                raise CaptchaError(
                    f"Network error during CAPTCHA submission: {str(e)}")
            except Exception as e:
                raise CaptchaError(
                    f"Unexpected error during CAPTCHA submission: {str(e)}")

            # Step 2: Poll for result
            return await self._poll_anticaptcha_result(session, task_id)

    async def _poll_anticaptcha_result(self, session: aiohttp.ClientSession, task_id: int) -> str:
        """
        Poll Anti-Captcha for CAPTCHA solution result

        Args:
            session: Active HTTP session
            task_id: ID of the submitted task

        Returns:
            The solved CAPTCHA token string
        """
        max_attempts = 60  # 5 minutes maximum
        attempt = 0

        self.logger.info(f"Polling for CAPTCHA solution. Task ID: {task_id}")

        while attempt < max_attempts:
            attempt += 1

            # Wait before polling
            await asyncio.sleep(5)

            result_data = {
                "clientKey": self.api_key,
                "taskId": task_id
            }

            try:
                async with session.post(self.endpoints["anticaptcha"]["result"], json=result_data) as response:
                    if response.status != 200:
                        self.logger.warning(
                            f"Poll attempt {attempt}: HTTP {response.status}")
                        continue

                    result = await response.json()

                    if result.get("errorId") != 0:
                        error_msg = result.get(
                            "errorDescription", "Unknown error")
                        raise CaptchaError(
                            f"Anti-Captcha polling failed: {error_msg}")

                    status = result.get("status")
                    if status == "ready":
                        # CAPTCHA solved successfully
                        solution = result.get("solution", {})
                        token = solution.get("gRecaptchaResponse")
                        if token:
                            self.logger.info(
                                f"CAPTCHA solved successfully after {attempt} attempts")
                            return token
                        else:
                            raise CaptchaError(
                                "CAPTCHA marked as ready but no token returned")

                    elif status == "processing":
                        # Still processing, continue polling
                        self.logger.debug(
                            f"Poll attempt {attempt}: CAPTCHA still processing")
                        continue

                    else:
                        raise CaptchaError(
                            f"Unexpected status from Anti-Captcha: {status}")

            except aiohttp.ClientError as e:
                self.logger.warning(
                    f"Poll attempt {attempt}: Network error - {str(e)}")
                continue
            except Exception as e:
                if "CAPTCHA" in str(e):
                    raise  # Re-raise CAPTCHA-specific errors
                self.logger.warning(
                    f"Poll attempt {attempt}: Unexpected error - {str(e)}")
                continue

        raise CaptchaError(
            f"CAPTCHA solving timeout after {max_attempts} attempts (5 minutes)")

    async def get_balance(self) -> float:
        """
        Get account balance from the CAPTCHA service

        Returns:
            Account balance as float
        """
        if self.service_name == "2captcha":
            return await self._get_2captcha_balance()
        elif self.service_name == "anticaptcha":
            return await self._get_anticaptcha_balance()
        else:
            raise CaptchaError(
                f"Balance check not supported for {self.service_name}")

    async def _get_2captcha_balance(self) -> float:
        """Get 2Captcha account balance"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            params = {
                "key": self.api_key,
                "action": "getbalance",
                "json": "1"
            }

            try:
                async with session.get(self.endpoints["2captcha"]["result"], params=params) as response:
                    if response.status != 200:
                        raise CaptchaError(
                            f"Failed to get balance: HTTP {response.status}")

                    result = await response.json()

                    if result.get("status") == 1:
                        return float(result.get("request", 0))
                    else:
                        error_msg = result.get("error_text", "Unknown error")
                        raise CaptchaError(
                            f"Balance check failed: {error_msg}")

            except aiohttp.ClientError as e:
                raise CaptchaError(
                    f"Network error during balance check: {str(e)}")

    async def _get_anticaptcha_balance(self) -> float:
        """Get Anti-Captcha account balance"""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            data = {"clientKey": self.api_key}

            try:
                async with session.post("https://api.anti-captcha.com/getBalance", json=data) as response:
                    if response.status != 200:
                        raise CaptchaError(
                            f"Failed to get balance: HTTP {response.status}")

                    result = await response.json()

                    if result.get("errorId") == 0:
                        return float(result.get("balance", 0))
                    else:
                        error_msg = result.get(
                            "errorDescription", "Unknown error")
                        raise CaptchaError(
                            f"Balance check failed: {error_msg}")

            except aiohttp.ClientError as e:
                raise CaptchaError(
                    f"Network error during balance check: {str(e)}")


def create_captcha_solver_from_config(config: Dict[str, Any]) -> Optional[CaptchaSolver]:
    """
    Create a CAPTCHA solver instance from configuration

    Args:
        config: Configuration dictionary

    Returns:
        CaptchaSolver instance or None if not configured
    """
    captcha_config = config.get('captcha_solver', {})

    if not captcha_config.get('enabled', False):
        return None

    service_name = captcha_config.get('service', '2captcha')
    api_key = captcha_config.get('api_key', '')

    if not api_key or api_key == 'your_2captcha_api_key_here':
        logging.getLogger(__name__).warning(
            "CAPTCHA solving enabled but no valid API key configured")
        return None

    try:
        return CaptchaSolver(service_name, api_key)
    except Exception as e:
        logging.getLogger(__name__).error(
            f"Failed to create CAPTCHA solver: {str(e)}")
        return None
