#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, '/app')

def test_module_loading():
    print("Testing Python module loading...")
    
    try:
        import marketplace
        print("✓ marketplace package imported successfully")
        print(f"  marketplace.__file__: {marketplace.__file__}")
        print(f"  marketplace.__path__: {getattr(marketplace, '__path__', 'No __path__')}")
    except Exception as e:
        print(f"✗ Error importing marketplace package: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        import marketplace.settings
        print("✓ marketplace.settings module imported")
        print(f"  settings.__file__: {marketplace.settings.__file__}")
        
        attrs = [attr for attr in dir(marketplace.settings) if not attr.startswith('_')]
        print(f"  Available attributes: {len(attrs)}")
        if len(attrs) > 0:
            print(f"  First few attributes: {attrs[:10]}")
        else:
            print("  ✗ No attributes found in settings module!")
            
    except Exception as e:
        print(f"✗ Error importing marketplace.settings: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        print("\nTesting direct settings file execution...")
        settings_file = '/app/marketplace/settings.py'
        
        with open(settings_file, 'r') as f:
            content = f.read()
        
        print(f"  Settings file size: {len(content)} characters")
        print(f"  Contains ROOT_URLCONF: {'ROOT_URLCONF' in content}")
        
        namespace = {}
        exec(content, namespace)
        
        attrs = [attr for attr in namespace.keys() if not attr.startswith('_')]
        print(f"  Executed namespace attributes: {len(attrs)}")
        print(f"  ROOT_URLCONF in namespace: {'ROOT_URLCONF' in namespace}")
        
        if 'ROOT_URLCONF' in namespace:
            print(f"  ROOT_URLCONF value: {namespace['ROOT_URLCONF']}")
        
    except Exception as e:
        print(f"✗ Error executing settings file: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    test_module_loading()
