#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1}"
HOST_HEADER="${HOST_HEADER:-localhost}"

get_headers() {
  local path="$1"
  curl -s -H "Host: ${HOST_HEADER}" -o /dev/null -D - "$BASE_URL$path"
}

status_code() {
  local path="$1"
  curl -s -H "Host: ${HOST_HEADER}" -o /dev/null -w "%{http_code}" "$BASE_URL$path"
}

must_contain_header() {
  local headers="$1"
  local name_lc="$2"
  echo "$headers" | awk -F': ' -v n="$name_lc" 'tolower($1)==n{found=1} END{exit found?0:1}'
}

check_css() {
  local path="$1"
  local hdrs
  hdrs="$(get_headers "$path")"
  local code
  code="$(status_code "$path")"
  echo "$path -> $code"
  test "$code" = "200"
  echo "$hdrs" | grep -i "^Content-Type:.*text/css" >/dev/null
  echo "$hdrs" | grep -i "^Cache-Control:.*immutable" >/dev/null
  echo "$hdrs" | grep -i "^Content-Encoding:.*gzip" >/dev/null
}

check_font() {
  local path="$1"
  local hdrs
  hdrs="$(get_headers "$path")"
  local code
  code="$(status_code "$path")"
  echo "$path -> $code"
  test "$code" = "200"
  echo "$hdrs" | grep -Ei "^Content-Type: *(font/woff2|application/font-woff2|application/font-woff)" >/dev/null
  echo "$hdrs" | grep -i "^Cache-Control:.*immutable" >/dev/null
  echo "$hdrs" | grep -i "^Content-Encoding:.*gzip" >/dev/null
}

check_root_redirect() {
  local hdrs
  hdrs="$(get_headers "/")"
  local code
  code="$(status_code "/")"
  echo "/ -> $code"
  [[ "$code" == "301" || "$code" == "302" ]]
  echo "$hdrs" | grep -i "^Location: */anti_ddos/challenge/" >/dev/null
}

check_css "/static/css/main.css"
check_css "/static/css/tailwind.min.css" || true
check_root_redirect

csp=$(get_headers "/" | awk -F': ' 'tolower($1)=="content-security-policy"{print $2}' | tr -d '\r')
echo "CSP: $csp"
echo "$csp" | grep -Fq "script-src 'none'"
echo "$csp" | grep -Fq "object-src 'none'"
echo "$csp" | grep -Fq "img-src 'self' data:"
