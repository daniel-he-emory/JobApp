#!/usr/bin/env python3
"""
Test with completely fresh browser session and enhanced evasion
"""
from base_agent import SearchCriteria
from agents.linkedin_agent import LinkedInAgent
from config.config_loader import ConfigLoader
import asyncio
import sys
import random
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_fresh_evasion():
    """Test LinkedIn with fresh session and maximum evasion"""

    # Load config
    config_loader = ConfigLoader("config/config.yaml")
    config = config_loader.load_config()

    # Create simple search criteria
    SearchCriteria(
        keywords=["Engineer"],
        locations=["Remote"],
        easy_apply_only=False,  # Don't filter by Easy Apply to get more results
        date_posted="Past month"  # Broader time range
    )

    # Initialize LinkedIn agent
    agent = LinkedInAgent(config)

    try:
        print("🔧 Initializing fresh browser session...")
        await agent.initialize_browser()

        # Add extra delay before starting
        print("⏳ Initial delay to mimic human behavior...")
        await asyncio.sleep(random.uniform(3, 7))

        print("🔑 Attempting login with enhanced evasion...")
        login_success = await agent.login()

        if login_success:
            print("✅ Login successful!")

            # Extra delay after login
            print("⏳ Post-login delay...")
            await asyncio.sleep(random.uniform(5, 10))

            print("🔍 Testing job search with broader criteria...")

            # Try direct navigation without complex filtering
            print("📍 Direct navigation to jobs page...")
            await agent.page.goto("https://www.linkedin.com/jobs/")
            await asyncio.sleep(random.uniform(3, 6))

            # Try simple search
            try:
                # Look for search box
                search_box = await agent.page.wait_for_selector('input[aria-label*="Search"], input[placeholder*="Search"]', timeout=10000)
                if search_box:
                    print("🔍 Found search box, entering keywords...")

                    # Type slowly like a human
                    await search_box.click()
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    await search_box.type("Software Engineer", delay=random.randint(100, 300))
                    await asyncio.sleep(random.uniform(1, 2))
                    await agent.page.keyboard.press('Enter')

                    print("⏳ Waiting for search results...")
                    await asyncio.sleep(random.uniform(5, 8))

                    # Check current URL and page content
                    current_url = agent.page.url
                    print(f"📍 Current URL: {current_url}")

                    # Look for any job-related content
                    page_content = await agent.page.content()

                    # Check for various indicators
                    if "no results" in page_content.lower():
                        print("❌ No results found")
                    elif "rate" in page_content.lower() or "limit" in page_content.lower():
                        print("⚠️ Rate limiting detected")
                    elif "challenge" in page_content.lower() or "verify" in page_content.lower():
                        print("⚠️ Security challenge detected")
                    elif "job" in page_content.lower():
                        print("✅ Job content found on page")

                        # Try to count job elements
                        job_links = await agent.page.query_selector_all('a[href*="/jobs/view/"]')
                        print(f"🔍 Found {len(job_links)} job links")

                        if job_links:
                            # Get details of first few jobs
                            for i, link in enumerate(job_links[:3]):
                                try:
                                    text = await link.inner_text()
                                    await link.get_attribute('href')
                                    print(f"  Job {i+1}: {text[:50]}...")
                                except:
                                    pass
                    else:
                        print("ℹ️ Unknown page state")

                    # Take screenshot for debugging
                    await agent.page.screenshot(path="fresh_session_test.png")
                    print("📸 Screenshot saved as fresh_session_test.png")

                else:
                    print("❌ Could not find search box")

            except Exception as e:
                print(f"❌ Search error: {str(e)}")

        else:
            print("❌ Login failed")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    finally:
        print("🧹 Cleaning up...")
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(test_fresh_evasion())
