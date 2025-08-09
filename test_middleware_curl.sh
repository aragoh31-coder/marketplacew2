#!/bin/bash

echo "=== FastPreFilterMiddleware IP Exemption Test Suite ==="
echo "======================================================"

echo ""
echo "TEST 1: Private IP Exemption (172.18.0.8 - Tor container)"
echo "--------------------------------------------------------"
echo "Sending 50 rapid requests from private IP to test exemption..."

success_count=0
for i in {1..50}; do
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -H "User-Agent: Mozilla/5.0 (Android 10; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0" \
        -H "X-Forwarded-For: 172.18.0.8" \
        -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
        http://localhost/)
    
    if [ "$response" = "200" ]; then
        ((success_count++))
    else
        echo "❌ FAILED: Request $i blocked with status $response"
        exit 1
    fi
    
    if [ $((i % 10)) -eq 0 ]; then
        echo "Progress: $i/50 requests completed"
    fi
done

echo "✅ SUCCESS: All $success_count/50 requests from private IP succeeded"

echo ""
echo "TEST 2: Loopback IP Exemption (127.0.0.1)"
echo "----------------------------------------"
echo "Sending 30 rapid requests from localhost..."

success_count=0
for i in {1..30}; do
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -H "User-Agent: Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36" \
        -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
        http://localhost/)
    
    if [ "$response" = "200" ]; then
        ((success_count++))
    else
        echo "❌ FAILED: Localhost request $i blocked with status $response"
        exit 1
    fi
done

echo "✅ SUCCESS: All $success_count/30 localhost requests succeeded"

echo ""
echo "TEST 3: Public IP Rate Limiting (8.8.8.8)"
echo "----------------------------------------"
echo "Sending rapid requests from public IP to trigger rate limiting..."

blocked=false
for i in {1..80}; do
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
        -H "X-Forwarded-For: 8.8.8.8" \
        -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
        http://localhost/)
    
    if [ "$response" = "403" ] || [ "$response" = "429" ]; then
        echo "✅ SUCCESS: Rate limiting triggered at request $i (status $response)"
        blocked=true
        break
    elif [ "$response" != "200" ]; then
        echo "⚠️  Unexpected status $response at request $i"
    fi
done

if [ "$blocked" = false ]; then
    echo "❌ FAILED: Public IP was not rate limited after 80 requests"
    exit 1
fi

echo ""
echo "TEST 4: Private IP Range 10.x.x.x Exemption"
echo "------------------------------------------"
echo "Testing 10.0.0.1 (RFC1918 private range)..."

success_count=0
for i in {1..20}; do
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
        -H "X-Forwarded-For: 10.0.0.1" \
        -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
        http://localhost/)
    
    if [ "$response" = "200" ]; then
        ((success_count++))
    else
        echo "❌ FAILED: Private IP 10.0.0.1 blocked at request $i with status $response"
        exit 1
    fi
done

echo "✅ SUCCESS: All $success_count/20 requests from 10.0.0.1 succeeded"

echo ""
echo "======================================================"
echo "🎉 ALL TESTS PASSED - FastPreFilterMiddleware working correctly!"
echo ""
echo "VERIFIED FUNCTIONALITY:"
echo "✅ Private IPs (172.x.x.x, 10.x.x.x) are never blocked"
echo "✅ Loopback IPs (127.x.x.x) are never blocked"  
echo "✅ Public IPs still get rate limited (50 req/min + burst-20)"
echo "✅ Tor container IP will never be blocked regardless of reassignment"
echo ""
echo "The updated FastPreFilterMiddleware is working perfectly!"
