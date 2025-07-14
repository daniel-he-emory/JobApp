#!/usr/bin/env python3
"""
Simple test to check if LinkedIn shows rate limiting or other issues
"""
from base_agent import SearchCriteria
from agents.linkedin_agent import LinkedInAgent
from config.config_loader import ConfigLoader
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def quick_linkedin_test():
    """Quick test of LinkedIn functionality"""

    # Load config
    config_loader = ConfigLoader("config/config.yaml")
    config = config_loader.load_config()

    # Create search criteria
    search_criteria = SearchCriteria(
        keywords=["Software Engineer"],
        locations=["San Francisco"],
        easy_apply_only=True,
        date_posted="Past week"
    )

    # Initialize LinkedIn agent
    agent = LinkedInAgent(config)

    try:
        print("🔧 Initializing browser...")
        await agent.initialize_browser()

        print("🔑 Attempting login...")
        login_success = await agent.login()

        if login_success:
            print("✅ Login successful!")

            print("🔍 Testing job search...")
            jobs = await agent.search_jobs(search_criteria)

            print(f"📊 Found {len(jobs)} jobs")

            if jobs:
                print("📝 Sample jobs:")
                for i, job in enumerate(jobs[:3]):
                    print(f"  {i+1}. {job.title} at {job.company}")
            else:
                print("❌ No jobs found - checking page state...")

                # Debug info
                current_url = agent.page.url
                print(f"Current URL: {current_url}")

                # Check if rate limited
                page_content = await agent.page.content()
                if "rate" in page_content.lower() or "limit" in page_content.lower():
                    print("⚠️ Possible rate limiting detected")
                elif "sign" in page_content.lower() and "in" in page_content.lower():
                    print("⚠️ Appears to need re-authentication")
                else:
                    print("ℹ️ Page appears normal but no jobs found")

        else:
            print("❌ Login failed")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    finally:
        print("🧹 Cleaning up...")
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(quick_linkedin_test())
