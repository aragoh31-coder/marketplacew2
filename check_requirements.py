#!/usr/bin/env python3
"""Check if all requirements from requirements.txt are installed"""

import sys
from pathlib import Path

def get_installed_packages():
    """Get list of installed packages"""
    try:
        import importlib.metadata as metadata
    except ImportError:
        import importlib_metadata as metadata
    
    installed = {}
    for dist in metadata.distributions():
        pkg_name = dist.metadata['Name'].lower()
        normalized_name = pkg_name.replace('-', '_').replace('_', '-')
        version = dist.version
        installed[pkg_name] = version
        installed[normalized_name] = version
        installed[pkg_name.replace('-', '_')] = version
    return installed

def parse_requirements():
    """Parse requirements.txt file"""
    requirements_file = Path('requirements.txt')
    if not requirements_file.exists():
        print("requirements.txt not found")
        return []
    
    requirements = []
    with open(requirements_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                package_name = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                if package_name:
                    requirements.append((package_name, line))
    return requirements

def main():
    print("Checking requirements...")
    installed = get_installed_packages()
    requirements = parse_requirements()
    
    missing = []
    for package_name, requirement_line in requirements:
        if package_name.lower() not in installed:
            missing.append(requirement_line)
    
    if missing:
        print(f"\nMissing packages ({len(missing)}):")
        for pkg in missing:
            print(f"  - {pkg}")
        return 1
    else:
        print(f"\nAll {len(requirements)} requirements are satisfied!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
