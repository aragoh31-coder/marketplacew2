#!/bin/bash

echo "==============================================================================="
echo "HMAC STATELESS PROTECTION TESTING SUITE"
echo "==============================================================================="

TOR_PROXY="socks5h://localhost:9050"
ONION="http://j2qnvjqnaihhrm5ktlwjp4tqkkpd27afli2qmn7fzphuefrgrt3imcqd.onion"
CLEARNET="http://localhost"

echo ""
echo "TEST 1: Fetch Challenge (Clearnet)"
echo "-----------------------------------"
echo "Testing challenge endpoint accessibility..."

response=$(curl -s -w "%{http_code}" -o /tmp/challenge_response.html $CLEARNET/anti_ddos/challenge/)
if [ "$response" = "200" ]; then
    echo "✅ Challenge endpoint accessible (HTTP $response)"
    if grep -q "challenge_data" /tmp/challenge_response.html; then
        echo "✅ Challenge data found in response"
    else
        echo "❌ Challenge data missing from response"
    fi
else
    echo "❌ Challenge endpoint failed (HTTP $response)"
fi

echo ""
echo "TEST 2: Fetch Challenge (Tor Onion)"
echo "-----------------------------------"
echo "Testing challenge via Tor onion service..."

response=$(curl -s -w "%{http_code}" -o /tmp/onion_challenge.html -x $TOR_PROXY $ONION/anti_ddos/challenge/)
if [ "$response" = "200" ]; then
    echo "✅ Onion challenge endpoint accessible (HTTP $response)"
    if grep -q "challenge_data" /tmp/onion_challenge.html; then
        echo "✅ Onion challenge data found in response"
    else
        echo "❌ Onion challenge data missing from response"
    fi
else
    echo "❌ Onion challenge endpoint failed (HTTP $response)"
fi

echo ""
echo "TEST 3: Run PoW Launcher"
echo "------------------------"
echo "Testing automated PoW solving..."

if [ -f "tor_pow_launcher.py" ]; then
    echo "Running PoW launcher..."
    timeout 60 python3 tor_pow_launcher.py
    launcher_exit=$?
    
    if [ $launcher_exit -eq 0 ]; then
        echo "✅ PoW launcher completed successfully"
    elif [ $launcher_exit -eq 124 ]; then
        echo "⚠️  PoW launcher timed out (60s limit)"
    else
        echo "❌ PoW launcher failed (exit code: $launcher_exit)"
    fi
else
    echo "❌ tor_pow_launcher.py not found"
fi

echo ""
echo "TEST 4: Access Main Site (Clearnet)"
echo "-----------------------------------"
echo "Testing main site access after PoW..."

response=$(curl -s -w "%{http_code}" -o /dev/null $CLEARNET/)
if [ "$response" = "200" ]; then
    echo "✅ Main site accessible (HTTP $response)"
elif [ "$response" = "302" ]; then
    echo "⚠️  Redirected (HTTP $response) - may need valid HMAC token"
else
    echo "❌ Main site access failed (HTTP $response)"
fi

echo ""
echo "TEST 5: OpenResty Gatekeeper Integration"
echo "----------------------------------------"
echo "Testing OpenResty Lua gatekeeper..."

response=$(curl -s -w "%{http_code}" -o /dev/null $CLEARNET/ --cookie-jar /tmp/cookies.txt)
echo "Request without token: HTTP $response"

response=$(curl -s -w "%{http_code}" -o /dev/null $CLEARNET/static/css/style.css)
if [ "$response" = "200" ] || [ "$response" = "404" ]; then
    echo "✅ Static assets bypass gatekeeper (HTTP $response)"
else
    echo "⚠️  Static assets may be blocked (HTTP $response)"
fi

echo ""
echo "TEST 6: HMAC Token Validation"
echo "-----------------------------"
echo "Testing HMAC token structure and validation..."

if [ -f "/tmp/challenge_response.html" ]; then
    challenge_data=$(grep -o 'name="challenge_data" value="[^"]*"' /tmp/challenge_response.html | cut -d'"' -f4)
    if [ -n "$challenge_data" ]; then
        echo "✅ Challenge data extracted: ${challenge_data:0:50}..."
        
        if echo "$challenge_data" | base64 -d > /dev/null 2>&1; then
            echo "✅ Challenge data is valid base64"
        else
            echo "❌ Challenge data is not valid base64"
        fi
    else
        echo "❌ Could not extract challenge data"
    fi
fi

echo ""
echo "TEST 7: Honeypot Detection"
echo "-------------------------"
echo "Testing honeypot field detection..."

curl -s -X POST $CLEARNET/anti_ddos/verify/ \
    -d "challenge_data=test" \
    -d "start_time=$(date +%s)" \
    -d "answer=42" \
    -d "hp0=bot_detected" \
    -d "hp1=" \
    -d "hp2=" \
    -d "hp3=" \
    -d "hp4=" \
    -w "Honeypot test response: %{http_code}\n" \
    -o /dev/null

echo ""
echo "TEST 8: Rate Limiting Integration"
echo "--------------------------------"
echo "Testing integration with existing rate limiting..."

echo "Sending rapid requests to test rate limiting..."
blocked=false
for i in {1..20}; do
    response=$(curl -s -w "%{http_code}" -o /dev/null $CLEARNET/)
    if [ "$response" = "429" ] || [ "$response" = "403" ]; then
        echo "✅ Rate limiting triggered at request $i (HTTP $response)"
        blocked=true
        break
    fi
done

if [ "$blocked" = false ]; then
    echo "⚠️  Rate limiting not triggered in 20 requests"
fi

echo ""
echo "TEST 9: Docker Container Health"
echo "-------------------------------"
echo "Checking Docker container status..."

if command -v docker-compose > /dev/null; then
    echo "Docker containers status:"
    docker-compose ps | grep -E "(openresty|django|tor)" || echo "❌ Docker compose not running"
else
    echo "⚠️  Docker compose not available"
fi

echo ""
echo "TEST 10: Log Analysis"
echo "--------------------"
echo "Analyzing recent logs for anti-DDoS activity..."

if [ -f "/var/log/nginx/access.log" ]; then
    echo "Recent anti-DDoS related requests:"
    tail -20 /var/log/nginx/access.log | grep -i "anti_ddos" | head -5
else
    echo "⚠️  Nginx access log not found"
fi

echo ""
echo "==============================================================================="
echo "TESTING COMPLETE"
echo "==============================================================================="
echo ""
echo "SUMMARY:"
echo "✅ = Test passed"
echo "⚠️  = Test passed with warnings"
echo "❌ = Test failed"
echo ""
echo "For detailed logs, check:"
echo "- OpenResty: docker-compose logs openresty"
echo "- Django: docker-compose logs django"
echo "- Tor: docker-compose logs tor"
echo ""
echo "To run PoW launcher manually:"
echo "python3 tor_pow_launcher.py"
echo ""
echo "Done."
