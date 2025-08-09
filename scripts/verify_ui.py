import sys

import requests
from bs4 import BeautifulSoup

URL = "http://localhost/"

try:
    session = requests.Session()
    r = session.get(URL, allow_redirects=True)

    print(f"Final URL: {r.url}")
    print(f"Status code: {r.status_code}")

    if r.status_code != 200:
        sys.exit(f"❌ Homepage returned {r.status_code}")

    soup = BeautifulSoup(r.text, "html.parser")

    if "challenge_data" in r.text:
        print("✅ Anti-DDoS challenge page loaded correctly")

        # Check for Tailwind CSS in challenge page
        css = soup.select_one("link[href*='tailwind.css']")
        assert css, "❌ tailwind.css <link> not found in challenge page"
        print(f"✅ Found Tailwind CSS link: {css.get('href')}")

        # Check for challenge form
        challenge_form = soup.select_one("form")
        assert challenge_form, "❌ Challenge form missing"
        print("✅ Challenge form found")

    else:
        print("✅ Main homepage loaded")

        # Check for Tailwind stylesheet link
        css = soup.select_one("link[href*='tailwind.css']")
        assert css, "❌ tailwind.css <link> not found"
        print(f"✅ Found Tailwind CSS link: {css.get('href')}")

        # Check for sidebar toggle input
        toggle = soup.select_one("input#sidebar-toggle")
        assert toggle, "❌ #sidebar-toggle missing"
        print(f"✅ Found sidebar toggle: {toggle.get('id')}")

        # Check for at least one nav link
        nav = soup.select_one("aside.sidebar nav a")
        assert nav, "❌ No <a> found in sidebar"
        print(
            f"✅ Found navigation links: {len(soup.select('aside.sidebar nav a'))} links"
        )

    print("✅ UI template verification completed!")

except Exception as e:
    print(f"❌ Verification failed: {e}")
    sys.exit(1)
