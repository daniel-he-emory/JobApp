#!/usr/bin/env python3
"""
Simple LinkedIn debugging script to test job extraction
"""
from agents.linkedin_agent import LinkedInAgent
from config.config_loader import ConfigLoader
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_linkedin_simple():
    """Test LinkedIn job search without full automation"""

    # Load config
    config_loader = ConfigLoader("config/config.yaml")
    config = config_loader.load_config()

    # Initialize LinkedIn agent
    agent = LinkedInAgent(config)

    try:
        # Initialize browser
        await agent.initialize_browser()
        print("✅ Browser initialized")

        # Login
        login_success = await agent.login()
        if not login_success:
            print("❌ Login failed")
            return
        print("✅ Login successful")

        # Try direct navigation to jobs with simple search
        print("🔍 Navigating to jobs page...")
        await agent.page.goto("https://www.linkedin.com/jobs/search/?keywords=Engineer&location=San%20Francisco", timeout=60000)
        await agent.page.wait_for_load_state('domcontentloaded', timeout=30000)

        # Wait and take screenshot for debugging
        await agent.page.wait_for_timeout(5000)
        await agent.page.screenshot(path="linkedin_debug.png")
        print("📸 Screenshot saved as linkedin_debug.png")

        # Try to find any job-related elements
        print("🔍 Looking for job elements...")

        # Check page content
        page_content = await agent.page.content()
        if "job" in page_content.lower():
            print("✅ Page contains job-related content")
        else:
            print("❌ No job content found")

        # Try various job selectors
        job_selectors = [
            'li[data-occludable-job-id]',
            '[data-job-id]',
            '.job-search-card',
            '.jobs-search-results__list-item',
            '.entity-result',
            'a[href*="/jobs/view/"]'
        ]

        for selector in job_selectors:
            try:
                elements = await agent.page.query_selector_all(selector)
                print(f"Selector '{selector}': {len(elements)} elements found")
                if elements:
                    # Get first element details
                    first_element = elements[0]
                    text_content = await first_element.inner_text()
                    print(f"  First element text: {text_content[:100]}...")
                    break
            except Exception as e:
                print(f"Selector '{selector}': Error - {str(e)}")

        # Check current URL
        current_url = agent.page.url
        print(f"📍 Current URL: {current_url}")

        # Check if we're blocked or redirected
        if "challenge" in current_url or "security" in current_url:
            print("⚠️ Appears to be blocked by security challenge")
        elif "login" in current_url:
            print("⚠️ Redirected back to login page")
        else:
            print("✅ On jobs page")

    except Exception as e:
        print(f"❌ Error during test: {str(e)}")

    finally:
        await agent.cleanup()
        print("🧹 Cleanup completed")

if __name__ == "__main__":
    asyncio.run(test_linkedin_simple())
