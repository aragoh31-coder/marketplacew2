#!/usr/bin/env python3
"""Test if generate_cut_circle function is available"""

try:
    from core.security.captcha_cutcircle import generate_cut_circle
    print("✓ generate_cut_circle function imported successfully")
    
    img_b64, missing_index = generate_cut_circle()
    print(f"✓ Function executed successfully, returned image length: {len(img_b64)}, missing index: {missing_index}")
    
except ImportError as e:
    print(f"✗ ImportError: {e}")
    
    try:
        import core.security.captcha_cutcircle as module
        print(f"Module contents: {dir(module)}")
        
        import inspect
        print(f"Module file: {inspect.getfile(module)}")
        
    except Exception as e2:
        print(f"Error checking module: {e2}")

except Exception as e:
    print(f"✗ Other error: {e}")
