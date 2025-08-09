#!/usr/bin/env python3
"""Verify generate_cut_circle function is available after rebuild"""

try:
    from core.security.captcha_cutcircle import generate_cut_circle

    print("✓ generate_cut_circle function imported successfully")

    img_b64, missing_index = generate_cut_circle()
    print(f"✓ Function executed successfully")
    print(f"  - Image base64 length: {len(img_b64)}")
    print(f"  - Missing segment index: {missing_index}")
    print(f"  - Missing index range valid: {0 <= missing_index < 12}")

except ImportError as e:
    print(f"✗ ImportError: {e}")

    try:
        import core.security.captcha_cutcircle as module

        print(
            f"Available functions: {[name for name in dir(module) if not name.startswith('_')]}"
        )
    except Exception as e2:
        print(f"Error checking module: {e2}")

except Exception as e:
    print(f"✗ Other error: {e}")
