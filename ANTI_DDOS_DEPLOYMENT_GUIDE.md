# Anti-DDoS Integration Deployment Guide

## Overview
This guide covers the deployment of the comprehensive 7-section anti-DDoS integration package into the existing Tor marketplace's 7-layer security system.

## Architecture Integration

### Current 7-Layer Security System
```
Layer 0: OpenResty (Lua anti-DDoS, rate limiting, PoW)
Layer 1: OpenResty Integration (header validation)
Layer 2: Resource Protection (CPU/memory monitoring)
Layer 3: Circuit-Aware Defense (threat scoring)
Layer 4: Fast Pre-Filter (50 req/min + burst-20)
Layer 5: Circuit Limiter (Tor circuit tracking)
Layer 6: Optimized Security (adaptive thresholds)
Layer 7: Django Security (CSRF, XSS, etc.)
```

### New Anti-DDoS Integration
```
Layer -1: HMAC Gatekeeper (OpenResty Lua)
Layer 0: AntiDDoSMiddleware (Django, top of stack)
Layer 0.5: Hybrid PoW System (Tor core patches)
```

## Components Deployed

### 1. Django anti_ddos App
- **Location**: `apps/anti_ddos/`
- **Middleware**: `AntiDDoSMiddleware` (top of middleware stack)
- **Views**: Challenge and verification endpoints
- **Templates**: No-JS templates with inline Tailwind CSS
- **URLs**: `/anti_ddos/challenge/` and `/anti_ddos/verify/`

### 2. HMAC Stateless Protection
- **Implementation**: Pure Python in `apps/anti_ddos/utils.py`
- **Features**: 
  - Daily key rotation
  - Honeypot detection (5 hidden fields)
  - Token lifetime: 2 hours (7200s)
  - 500 uses per token
  - Constant-time verification

### 3. Tor Hybrid PoW System
- **Files**: 
  - `src/feature/dos/dos_hybrid_pow.c`
  - `src/feature/dos/dos_hmac_stateless.c/.h`
- **Algorithms**: Equi-X + Argon2 adaptive switching
- **Configuration**: Added to `torrc`

### 4. OpenResty Lua Gatekeeper
- **File**: `openresty/lua/antiddos_gatekeeper.lua`
- **Integration**: Added to nginx.conf location blocks
- **Function**: HMAC token verification before existing anti-DDoS

### 5. Python Tor PoW Launcher
- **File**: `tor_pow_launcher.py`
- **Features**:
  - Automatic challenge solving
  - Tor circuit management
  - HMAC token acquisition
  - Retry logic with exponential backoff

### 6. Testing Suite
- **File**: `test_hmac_protection.sh`
- **Tests**: 10 comprehensive test scenarios
- **Coverage**: All integration points and failure modes

## Deployment Steps

### 1. Verify Prerequisites
```bash
cd /home/ubuntu/marketplace
docker-compose ps  # All containers should be running
```

### 2. Check Django Integration
```bash
docker-compose exec django python manage.py check
docker-compose exec django python manage.py collectstatic --noinput
```

### 3. Restart Services
```bash
docker-compose restart openresty django
docker-compose logs -f openresty django
```

### 4. Test Integration
```bash
chmod +x test_hmac_protection.sh
./test_hmac_protection.sh
```

### 5. Run PoW Launcher
```bash
python3 tor_pow_launcher.py
```

## Configuration Details

### Django Settings Updates
- Added `apps.anti_ddos` to `INSTALLED_APPS`
- Added `AntiDDoSMiddleware` at top of `MIDDLEWARE`
- Added URL pattern for `/anti_ddos/`

### Tor Configuration (torrc)
```
DoSChallengesPerSecMax 100
DoSArgon2LowRamThreshold 131072
DoSConnectionEnabled 1
DoSCircuitCreationEnabled 1
ControlPort 9051
HashedControlPassword 16:872860B76453A77D60CA2BB8C1A7042072093276A3D701AD684053EC4C
```

### OpenResty Integration
- Added `antiddos_gatekeeper.lua` to request processing
- Gatekeeper runs before existing `antiddos.lua`
- Bypasses static assets and anti_ddos paths

## Security Features

### HMAC Token System
- **Magic Number**: 0x544F5248 ("TORH")
- **Signature**: HMAC-SHA256 with daily rotated key
- **Validation**: Constant-time comparison
- **Honeypots**: 5 hidden fields detect automated submissions

### Hybrid PoW Challenges
- **Equi-X**: Fast general DoS protection
- **Argon2**: Memory-hard botnet resistance
- **Adaptive**: Switches based on system resources and entropy
- **Emergency**: Escalates difficulty under attack

### Progressive Enforcement
1. **Warning**: Soft rate limiting with headers
2. **Challenge**: Math problem + honeypot detection
3. **PoW**: Hybrid Equi-X/Argon2 challenges
4. **Block**: Hard IP blocking for persistent attackers

## Monitoring and Diagnostics

### Log Locations
- **OpenResty**: `docker-compose logs openresty`
- **Django**: `docker-compose logs django`
- **Tor**: `docker-compose logs tor`

### Key Metrics
- Challenge generation rate
- Token validation success/failure
- Honeypot detection triggers
- PoW algorithm selection (Equi-X vs Argon2)
- System resource utilization

### Health Checks
```bash
# Test challenge endpoint
curl -s http://localhost/anti_ddos/challenge/ | grep challenge_data

# Test onion service (replace with your actual .onion address)
curl -s --socks5-hostname localhost:9050 \
  http://YOUR_ONION_ADDRESS.onion/anti_ddos/challenge/

# Check HMAC gatekeeper
curl -s -I http://localhost/ | grep -i location
```

## Troubleshooting

### Common Issues

1. **403 Forbidden on legitimate requests**
   - Check HMAC token validity
   - Verify gatekeeper configuration
   - Restart Django to clear blocked IPs

2. **Challenge page not loading**
   - Check Django anti_ddos app installation
   - Verify URL patterns in urls.py
   - Check template directory structure

3. **PoW launcher fails**
   - Verify Tor control port (9051) accessibility
   - Check onion service connectivity
   - Validate challenge data extraction

4. **OpenResty errors**
   - Check Lua module dependencies
   - Verify nginx.conf syntax
   - Test gatekeeper logic independently

### Debug Commands
```bash
# Test middleware stack
docker-compose exec django python manage.py shell -c "
from django.conf import settings
print('Middleware order:')
for i, mw in enumerate(settings.MIDDLEWARE):
    print(f'{i+1}. {mw}')
"

# Test HMAC utilities
docker-compose exec django python manage.py shell -c "
from apps.anti_ddos.utils import create_challenge, issue_token
c = create_challenge(0)
print(f'Challenge: {c.a} + {c.b} = {c.expected}')
t = issue_token()
print(f'Token expires: {t.expires}')
"

# Test OpenResty Lua
docker-compose exec openresty nginx -t
```

## Performance Considerations

### Resource Usage
- **HMAC Operations**: ~0.1ms per token verification
- **Challenge Generation**: ~1ms per math problem
- **Honeypot Detection**: Negligible overhead
- **Memory**: ~10MB additional for token cache

### Scalability
- **Stateless Design**: No shared state between requests
- **Daily Key Rotation**: Automatic cleanup
- **Token Expiry**: 2-hour lifetime prevents accumulation
- **Queue Limits**: Prevents memory exhaustion

## Security Considerations

### Production Deployment
1. **Change Default Secrets**: Update HMAC secret key
2. **Enable HTTPS**: Use TLS termination
3. **Configure Firewall**: Restrict control port access
4. **Monitor Logs**: Set up log aggregation
5. **Regular Updates**: Keep dependencies current

### Attack Mitigation
- **DDoS**: Multi-layer rate limiting + PoW challenges
- **Bot Traffic**: Honeypot detection + behavioral analysis
- **Circuit Attacks**: Tor fingerprinting + memory tracking
- **Evasion**: Progressive enforcement + adaptive thresholds

## Integration Verification

### Success Criteria
- ✅ All Docker containers start successfully
- ✅ Onion service remains accessible
- ✅ Anti-DDoS challenges work correctly
- ✅ HMAC token system functions
- ✅ OpenResty Lua gatekeeper integration
- ✅ Testing suite passes all scenarios
- ✅ No disruption to existing functionality

### Final Validation
```bash
# Run complete test suite
./test_hmac_protection.sh

# Test PoW launcher
python3 tor_pow_launcher.py

# Verify onion accessibility (replace with your actual .onion address)
curl --socks5-hostname localhost:9050 \
  http://YOUR_ONION_ADDRESS.onion/
```

## Support and Maintenance

### Regular Tasks
- Monitor challenge success rates
- Review honeypot detection logs
- Update HMAC secret keys
- Analyze attack patterns
- Performance optimization

### Backup and Recovery
- Configuration files in version control
- Database migrations for Django app
- OpenResty configuration backup
- Tor key material protection

This deployment integrates seamlessly with the existing 7-layer security system while adding sophisticated anti-evasion capabilities targeting 95%+ attack blocking with minimal false positives.
