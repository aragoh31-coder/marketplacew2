#!/usr/bin/env python3
import ast
import sys

def check_syntax(filename):
    try:
        with open(filename, 'r') as f:
            content = f.read()
        
        ast.parse(content, filename=filename)
        print(f"✓ {filename} has valid Python syntax")
        return True
        
    except SyntaxError as e:
        print(f"✗ Syntax error in {filename}:")
        print(f"  Line {e.lineno}: {e.text}")
        print(f"  Error: {e.msg}")
        return False
    except Exception as e:
        print(f"✗ Error reading {filename}: {e}")
        return False

def check_imports(filename):
    try:
        with open(filename, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line.startswith('from') and 'import' in line:
                if 'settings.local' in line:
                    print(f"Line {i}: Found local settings import: {line}")
                elif '.settings' in line:
                    print(f"Line {i}: Found settings import: {line}")
        
        return True
    except Exception as e:
        print(f"✗ Error checking imports in {filename}: {e}")
        return False

if __name__ == "__main__":
    settings_file = "/app/marketplace/settings.py"
    
    print("Checking Django settings file...")
    syntax_ok = check_syntax(settings_file)
    imports_ok = check_imports(settings_file)
    
    if syntax_ok and imports_ok:
        print("✓ Settings file appears to be valid")
    else:
        print("✗ Issues found in settings file")
