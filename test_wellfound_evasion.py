#!/usr/bin/env python3
"""
Test Wellfound with enhanced evasion strategies
"""
from base_agent import SearchCriteria
from agents.wellfound_agent import WellfoundAgent
from config.config_loader import ConfigLoader
import asyncio
import sys
import random
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_wellfound_evasion():
    """Test Wellfound with enhanced evasion"""

    # Load config
    config_loader = ConfigLoader("config/config.yaml")
    config = config_loader.load_config()

    # Initialize Wellfound agent
    agent = WellfoundAgent(config)

    try:
        print("🔧 Initializing fresh browser session for Wellfound...")
        await agent.initialize_browser()

        # Add extra delay before starting
        print("⏳ Initial human-like delay...")
        await asyncio.sleep(random.uniform(3, 7))

        print("🔑 Attempting Wellfound login with enhanced evasion...")
        login_success = await agent.login()

        if login_success:
            print("✅ Wellfound login successful!")

            # Extra delay after login
            print("⏳ Post-login delay...")
            await asyncio.sleep(random.uniform(5, 10))

            print("🔍 Testing Wellfound job search...")

            # Create simple search criteria
            search_criteria = SearchCriteria(
                keywords=["Engineer"],
                locations=["San Francisco"],
                easy_apply_only=False
            )

            jobs = await agent.search_jobs(search_criteria)

            print(f"📊 Found {len(jobs)} jobs on Wellfound")

            if jobs:
                print("📝 Sample jobs found:")
                for i, job in enumerate(jobs[:3]):
                    print(f"  {i+1}. {job.title} at {job.company}")
                print("✅ Wellfound evasion successful!")
            else:
                print("⚠️ No jobs found - checking page state...")

                current_url = agent.page.url
                print(f"Current URL: {current_url}")

                page_content = await agent.page.content()
                if "rate" in page_content.lower() or "limit" in page_content.lower():
                    print("⚠️ Rate limiting detected on Wellfound")
                elif "login" in current_url:
                    print("⚠️ Redirected back to login")
                else:
                    print("ℹ️ Unknown state - may need different search approach")

            # Take screenshot
            await agent.page.screenshot(path="wellfound_evasion_test.png")
            print("📸 Screenshot saved as wellfound_evasion_test.png")

        else:
            print("❌ Wellfound login failed")

            # Debug login failure
            current_url = agent.page.url
            print(f"Current URL: {current_url}")

            page_content = await agent.page.content()
            if "error" in page_content.lower():
                print("⚠️ Login error detected")
            elif "verify" in page_content.lower():
                print("⚠️ Email verification required")
            else:
                print("ℹ️ Unknown login failure reason")

            await agent.page.screenshot(path="wellfound_login_failure.png")
            print("📸 Login failure screenshot saved")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    finally:
        print("🧹 Cleaning up...")
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(test_wellfound_evasion())
