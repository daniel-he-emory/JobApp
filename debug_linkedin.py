#!/usr/bin/env python3
"""
Debug script to see LinkedIn page structure
"""
from playwright.async_api import async_playwright
from config.config_loader import ConfigLoader
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


async def debug_linkedin():
    config_loader = ConfigLoader('config/config.yaml')
    config = config_loader.load_config()

    credentials = config.get('credentials', {}).get('linkedin', {})

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # Login
            print("🔐 Logging into LinkedIn...")
            await page.goto("https://www.linkedin.com/login", timeout=30000)
            await page.fill('input[name="session_key"]', credentials['email'])
            await page.fill('input[name="session_password"]', credentials['password'])
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(3000)

            # Navigate to jobs
            print("🔍 Navigating to jobs page...")
            await page.goto("https://www.linkedin.com/jobs/search/?keywords=Solutions%20Engineer&location=San%20Francisco", timeout=60000)
            await page.wait_for_timeout(5000)

            # Debug: Save page content and screenshot
            print("📄 Saving page content for debugging...")
            content = await page.content()
            with open('/tmp/linkedin_debug.html', 'w') as f:
                f.write(content)

            # Try to find any job-related elements
            print("🔍 Looking for job elements...")

            # Check for various job selectors
            selectors_to_check = [
                'li[data-occludable-job-id]',  # Common LinkedIn pattern
                '[data-job-id]',
                '.base-search-card',
                '.job-search-card',
                '.jobs-search-results__list-item',
                '.job-result-card',
                '[data-test*="job"]',
                'article[data-entity-urn]',
                '.base-card',
                '.entity-result'
            ]

            for selector in selectors_to_check:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(
                            f"✅ Found {len(elements)} elements with selector: {selector}")

                        # Get first element's text content for debugging
                        first_element = elements[0]
                        text_content = await first_element.text_content()
                        print(
                            f"   First element text: {text_content[:100]}...")
                    else:
                        print(f"❌ No elements found with: {selector}")
                except Exception as e:
                    print(f"❌ Error with selector {selector}: {str(e)}")

            # Check page URL and title
            print(f"📍 Current URL: {page.url}")
            print(f"📋 Page title: {await page.title()}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_linkedin())
