#!/usr/bin/env python3
"""
Fetch working proxy servers from a free proxy API
"""
import requests
from pathlib import Path


def get_free_proxies():
    """Get working free proxy servers"""

    print("🔍 Fetching free proxy servers...")

    try:
        # Try multiple free proxy APIs
        apis = [
            "https://www.proxy-list.download/api/v1/get?type=http",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",
        ]

        working_proxies = []

        for api_url in apis:
            try:
                print(f"📡 Trying API: {api_url}")
                response = requests.get(api_url, timeout=10)

                if response.status_code == 200:
                    proxies_text = response.text.strip()
                    proxy_lines = [line.strip() for line in proxies_text.split(
                        '\n') if line.strip()]

                    print(f"Found {len(proxy_lines)} potential proxies")

                    # Test first few proxies
                    for proxy_line in proxy_lines[:5]:
                        if ':' in proxy_line:
                            try:
                                host, port = proxy_line.split(':')
                                port = int(port)

                                # Test proxy
                                proxy_dict = {
                                    'http': f'http://{host}:{port}',
                                    'https': f'http://{host}:{port}'
                                }

                                test_response = requests.get('http://httpbin.org/ip',
                                                             proxies=proxy_dict,
                                                             timeout=5)

                                if test_response.status_code == 200:
                                    ip_data = test_response.json()
                                    print(
                                        f"✅ Working proxy: {host}:{port} -> IP: {ip_data.get('origin')}")
                                    working_proxies.append({
                                        'host': host,
                                        'port': port,
                                        'protocol': 'http'
                                    })

                                    if len(working_proxies) >= 3:
                                        break

                            except Exception as e:
                                print(f"❌ Proxy {proxy_line} failed: {str(e)}")
                                continue

                    if working_proxies:
                        break

            except Exception as e:
                print(f"❌ API {api_url} failed: {str(e)}")
                continue

        if working_proxies:
            print(f"\n✅ Found {len(working_proxies)} working proxies!")
            return working_proxies
        else:
            print("❌ No working proxies found")
            return []

    except Exception as e:
        print(f"❌ Error fetching proxies: {str(e)}")
        return []


def update_config_with_proxies(working_proxies):
    """Update config.yaml with working proxies"""

    if not working_proxies:
        print("No proxies to update")
        return

    config_path = Path(__file__).parent / "config" / "config.yaml"

    print(f"📝 Updating {config_path} with working proxies...")

    # Read current config
    with open(config_path, 'r') as f:
        f.read()

    # Generate proxy YAML
    proxy_yaml = "  proxies:\n"
    for proxy in working_proxies:
        proxy_yaml += f"    - host: \"{proxy['host']}\"\n"
        proxy_yaml += f"      port: {proxy['port']}\n"
        proxy_yaml += f"      protocol: \"{proxy['protocol']}\"\n"

    print("Generated proxy configuration:")
    print(proxy_yaml)

    # Note: For now, just print the config instead of modifying the file
    # to avoid overwriting the existing config
    print("✅ Copy the above proxy configuration to your config.yaml manually")


if __name__ == "__main__":
    working_proxies = get_free_proxies()
    if working_proxies:
        update_config_with_proxies(working_proxies)
    else:
        print("\n💡 Recommendation: Use a paid residential proxy service like:")
        print("   - Bright Data: https://brightdata.com")
        print("   - Oxylabs: https://oxylabs.io")
        print("   - SmartProxy: https://smartproxy.com")
        print("   Free proxies are often unreliable and blocked by major sites.")
