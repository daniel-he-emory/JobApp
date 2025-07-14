#!/usr/bin/env python3
"""
Test proxy rotation functionality
"""
from agents.linkedin_agent import LinkedInAgent
from utils.proxy_manager import create_proxy_manager_from_config
from config.config_loader import ConfigLoader
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_proxy_rotation():
    """Test proxy rotation and IP changing"""

    # Load config
    config_loader = ConfigLoader("config/config.yaml")
    config = config_loader.load_config()

    print("🔧 Testing proxy rotation system...")

    # Create proxy manager
    proxy_manager = create_proxy_manager_from_config(config)

    if not proxy_manager:
        print("❌ Proxy manager not created - check configuration")
        return

    print(
        f"✅ Proxy manager created with {len(proxy_manager.proxy_configs)} proxies")

    # Validate proxies
    print("🔍 Validating proxy servers...")
    working_proxies = proxy_manager.validate_all_proxies()

    if not working_proxies:
        print("❌ No working proxies found")
        return

    print(f"✅ Found {len(working_proxies)} working proxies")

    # Test with LinkedIn agent
    agent = LinkedInAgent(config, proxy_config=config.get('proxy', {}))

    try:
        print("🔧 Testing browser with proxy rotation...")

        # Test multiple sessions with different proxies
        for i in range(3):
            print(f"\n--- Session {i+1} ---")

            # Get current proxy
            current_proxy = proxy_manager.get_current_proxy()
            if current_proxy:
                print(
                    f"🌐 Using proxy: {current_proxy.host}:{current_proxy.port}")
            else:
                print("⚠️ No proxy available")
                continue

            # Initialize browser with current proxy
            await agent.initialize_browser()

            # Test IP by visiting a simple page
            try:
                print("🔍 Checking IP address...")
                await agent.page.goto("http://httpbin.org/ip", timeout=30000)
                await agent.page.wait_for_load_state('domcontentloaded')

                # Get IP info
                content = await agent.page.content()
                print(f"📍 Response: {content[:200]}...")

                if "origin" in content:
                    print("✅ Successfully connected through proxy")
                else:
                    print("⚠️ Unclear proxy status")

            except Exception as e:
                print(f"❌ Proxy test failed: {str(e)}")
                proxy_manager.mark_proxy_failed(current_proxy)

            # Cleanup
            await agent.cleanup()

            # Rotate to next proxy
            if i < 2:  # Don't rotate on last iteration
                print("🔄 Rotating to next proxy...")
                proxy_manager.rotate_proxy()
                await asyncio.sleep(2)

    except Exception as e:
        print(f"❌ Error during proxy testing: {str(e)}")

    finally:
        # Show final stats
        stats = proxy_manager.get_proxy_stats()
        print(f"\n📊 Final proxy stats:")
        print(f"   Total proxies: {stats['total_proxies']}")
        print(f"   Working proxies: {stats['working_proxies']}")
        print(f"   Failed proxies: {stats['failed_proxies']}")

if __name__ == "__main__":
    asyncio.run(test_proxy_rotation())
