# Security Fixes Pull Request

## Description
This PR addresses several security vulnerabilities identified during a comprehensive code review of the Tor-based Django Marketplace application.

## Security Issues Fixed
- Fixed PGP implementation by removing `always_trust=True` parameter
- Enhanced subprocess calls to prevent command injection
- Implemented missing remote image deletion functionality
- Improved cryptocurrency address validation
- Added consistent CSRF protection across all views
- Strengthened Content Security Policy headers
- Updated vulnerable dependencies:
  - Django from 5.1.4 to 5.1.11
  - cryptography from 43.0.0 to 44.0.1
  - gunicorn from 22.0.0 to 23.0.0
  - Replaced ecdsa 0.19.0 with cryptography

## Testing Performed
- Verified PGP encryption works correctly without `always_trust=True`
- Tested subprocess calls for Tor descriptor refresh
- Verified remote image deletion functionality
- Tested cryptocurrency address validation with various address formats
- Verified CSRF protection on all form submissions
- Checked Content Security Policy headers in browser responses
- Verified application works with updated dependencies

## Documentation
- Added SECURITY_FIXES.md documenting all security issues and fixes
- Created update_dependencies.sh script to update vulnerable dependencies

## Checklist
- [x] Code follows the project's coding style
- [x] Documentation has been updated
- [x] Tests have been added/updated to cover the changes
- [x] All tests pass locally
- [x] Security vulnerabilities have been addressed