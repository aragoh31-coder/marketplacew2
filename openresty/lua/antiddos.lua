local redis = require "resty.redis"
local json = require "cjson.safe"
local ngx_re = require "ngx.re"

local MAX_REQ_MINUTE = 300        -- 5 req/sec total (was 30)
local MAX_REQ_HOUR = 1800          -- 30 req/min average (was 300)
local MAX_REQ_BURST = 100          -- 100 requests in burst (was 10)
local WINDOW_MINUTE = 60
local WINDOW_HOUR = 3600
local WINDOW_BURST = 10
local HMAC_KEY = "openresty-antiddos-key-change-in-production"
local POW_THRESHOLD_MINUTE = 50    -- Higher threshold for PoW (was 10)
local POW_THRESHOLD_HOUR = 500     -- Higher threshold for PoW (was 100)

local SOFT_LIMIT_MINUTE = 200      -- Warning only
local HARD_LIMIT_MINUTE = 400      -- Show challenge
local BLOCK_LIMIT_MINUTE = 800     -- Hard block

local STATIC_RATE_MULTIPLIER = 0.1 -- Static assets count as 0.1 requests

local function connect_redis()
    local red = redis:new()
    red:set_timeout(1000)
    local ok, err = red:connect(os.getenv("REDIS_HOST") or "redis", 
                               tonumber(os.getenv("REDIS_PORT")) or 6379)
    if not ok then
        ngx.log(ngx.ERR, "Failed to connect to Redis: ", err)
        return nil
    end
    return red
end

local function get_client_fingerprint()
    local remote_ip = ngx.var.remote_addr or "unknown"
    local ua = ngx.var.http_user_agent or ""
    local accept = ngx.var.http_accept or ""
    local accept_lang = ngx.var.http_accept_language or ""
    local accept_encoding = ngx.var.http_accept_encoding or ""
    
    local fingerprint_data = remote_ip .. "|" .. ua .. "|" .. accept .. "|" .. accept_lang .. "|" .. accept_encoding
    return ngx.encode_base64(ngx.md5(fingerprint_data))
end

local function is_blocked_ip(ip)
    local blocked = ngx.shared.blocked_ips:get(ip)
    return blocked ~= nil
end

local function block_ip(ip, duration)
    ngx.shared.blocked_ips:set(ip, true, duration or 3600)
    ngx.log(ngx.WARN, "Blocked IP: ", ip, " for ", duration or 3600, " seconds")
end

local function is_static_asset()
    local path = string.lower(ngx.var.uri or "")
    
    local static_extensions = {
        "%.css$", "%.js$", "%.png$", "%.jpg$", "%.jpeg$", "%.gif$", 
        "%.ico$", "%.woff$", "%.woff2$", "%.svg$", "%.webp$", 
        "%.ttf$", "%.eot$", "%.webm$", "%.mp4$", "%.pdf$"
    }
    
    for _, pattern in ipairs(static_extensions) do
        if string.find(path, pattern) then
            return true
        end
    end
    
    return false
end

local function is_obvious_bot()
    local ua = string.lower(ngx.var.http_user_agent or "")
    
    if ua == "" then
        return false
    end
    
    local bot_patterns = {
        "python%-requests", "curl/", "wget/", "httpx/", "scrapy/",
        "selenium", "phantomjs", "headless", "automation"
    }
    
    for _, pattern in ipairs(bot_patterns) do
        if string.find(ua, pattern) then
            local legit_patterns = {"googlebot", "bingbot", "duckduckbot", "slurp", "yandex"}
            for _, legit in ipairs(legit_patterns) do
                if string.find(ua, legit) then
                    return false
                end
            end
            return true
        end
    end
    
    if string.find(ua, "scanner") or string.find(ua, "exploit") or string.find(ua, "hack") then
        return true
    end
    
    return false
end

local function is_suspicious_path()
    local path = string.lower(ngx.var.uri or "")
    
    local suspicious_patterns = {
        "/admin", "/wp%-admin", "%.php$", "%.asp$", "/config",
        "/backup", "%.sql$", "%.env$", "/%.git", "/%.svn", "/%.htaccess",
        "/xmlrpc%.php", "/wp%-login%.php", "/phpmyadmin"
    }
    
    for _, pattern in ipairs(suspicious_patterns) do
        if string.find(path, pattern) then
            return true
        end
    end
    
    local query_string = ngx.var.args or ""
    local xss_patterns = {"<script", "javascript:", "onload=", "onerror=", "eval%("}
    local sql_patterns = {"union", "select", "drop", "insert", "delete", "update", "exec"}
    
    for _, pattern in ipairs(xss_patterns) do
        if string.find(string.lower(query_string), pattern) then
            return true
        end
    end
    
    for _, pattern in ipairs(sql_patterns) do
        if string.find(string.lower(query_string), pattern) then
            return true
        end
    end
    
    return false
end

local function check_rate_limits(red, fingerprint)
    local current_time = ngx.time()
    local minute_key = "openresty_rl_min:" .. fingerprint .. ":" .. math.floor(current_time / 60)
    local hour_key = "openresty_rl_hour:" .. fingerprint .. ":" .. math.floor(current_time / 3600)
    local burst_key = "openresty_rl_burst:" .. fingerprint .. ":" .. math.floor(current_time / 10)
    
    local minute_count = tonumber(red:get(minute_key)) or 0
    local hour_count = tonumber(red:get(hour_key)) or 0
    local burst_count = tonumber(red:get(burst_key)) or 0
    
    local request_weight = 1.0
    if is_static_asset() then
        request_weight = STATIC_RATE_MULTIPLIER
    end
    
    local effective_minute = minute_count * request_weight
    local effective_hour = hour_count * request_weight
    local effective_burst = burst_count * request_weight
    
    if effective_burst >= MAX_REQ_BURST then
        return false, "burst", minute_count, hour_count
    end
    
    if effective_minute >= BLOCK_LIMIT_MINUTE then
        return false, "block", minute_count, hour_count
    end
    
    if effective_minute >= HARD_LIMIT_MINUTE then
        return false, "challenge", minute_count, hour_count
    end
    
    if effective_minute >= SOFT_LIMIT_MINUTE then
        ngx.log(ngx.WARN, "Soft limit warning for ", fingerprint, ": ", effective_minute, " req/min")
    end
    
    if effective_hour >= MAX_REQ_HOUR then
        return false, "hour", minute_count, hour_count
    end
    
    red:incr(burst_key)
    red:expire(burst_key, WINDOW_BURST)
    red:incr(minute_key)
    red:expire(minute_key, WINDOW_MINUTE)
    red:incr(hour_key)
    red:expire(hour_key, WINDOW_HOUR)
    
    return true, minute_count, hour_count
end

local function requires_pow(minute_count, hour_count)
    return minute_count >= POW_THRESHOLD_MINUTE or hour_count >= POW_THRESHOLD_HOUR
end

local function check_pow_verification(red, fingerprint)
    local valid_key = "pow_valid:" .. fingerprint
    local valid = red:get(valid_key)
    return valid ~= ngx.null
end

local remote_ip = ngx.var.remote_addr or "unknown"

if string.match(remote_ip, "^172%.18%.") or string.match(remote_ip, "^127%.") or remote_ip == "localhost" then
    local red = connect_redis()
    if red then
        local fingerprint = get_client_fingerprint()
        ngx.req.set_header("X-Client-Fingerprint", fingerprint)
        red:close()
    end
    return
end

if is_blocked_ip(remote_ip) then
    ngx.status = 403
    ngx.header.content_type = "text/plain"
    ngx.say("IP blocked due to suspicious activity")
    return ngx.exit(403)
end

if is_obvious_bot() then
    block_ip(remote_ip, 1800)
    ngx.status = 403
    ngx.header.content_type = "text/plain"
    ngx.say("Bot detected")
    return ngx.exit(403)
end

if is_suspicious_path() then
    block_ip(remote_ip, 3600)
    ngx.status = 403
    ngx.header.content_type = "text/plain"
    ngx.say("Suspicious request blocked")
    return ngx.exit(403)
end

if not string.match(remote_ip, "^172%.18%.") then
    local red = connect_redis()
    if not red then
        ngx.status = 503
        ngx.header.content_type = "text/plain"
        ngx.say("Service temporarily unavailable")
        return ngx.exit(503)
    end

    local fingerprint = get_client_fingerprint()
    ngx.req.set_header("X-Client-Fingerprint", fingerprint)

    local rate_ok, rate_type, minute_count, hour_count = check_rate_limits(red, fingerprint)

    if not rate_ok then
        if rate_type == "block" then
            block_ip(remote_ip, 600)  -- 10 minutes (reduced from 30)
            ngx.status = 403
            ngx.header.content_type = "text/plain"
            ngx.say("Blocked due to excessive requests")
            return ngx.exit(403)
        elseif rate_type == "challenge" then
            ngx.status = 429
            ngx.header.content_type = "application/json"
            ngx.header["Retry-After"] = "30"
            ngx.say('{"error":"Rate limit exceeded","action":"challenge","message":"Please solve challenge to continue"}')
            return ngx.exit(429)
        elseif rate_type == "burst" then
            ngx.status = 429
            ngx.header.content_type = "text/plain"
            ngx.header["Retry-After"] = "10"
            ngx.say("Too many requests - please slow down")
            return ngx.exit(429)
        else
            block_ip(remote_ip, 300)  -- 5 minutes
            ngx.status = 429
            ngx.header.content_type = "text/plain"
            ngx.header["Retry-After"] = "300"
            ngx.say("Rate limit exceeded")
            return ngx.exit(429)
        end
    end
    
    if requires_pow(minute_count or 0, hour_count or 0) then
        if not check_pow_verification(red, fingerprint) then
        local challenge_key = "pow_challenge:" .. fingerprint
        local challenge_exists = red:get(challenge_key)
        
        if challenge_exists == ngx.null then
            local challenge = {
                nonce = ngx.encode_base64(string.sub(tostring(math.random()), 3)),
                timestamp = ngx.time(),
                difficulty = 3,  -- Reduced difficulty for better UX
                type = "sha256"
            }
            red:setex(challenge_key, 600, json.encode(challenge))  -- Longer expiry
        end
        
        ngx.status = 429
        ngx.header.content_type = "application/json"
        ngx.header["Retry-After"] = "60"
        ngx.say(json.encode({
            error = "High traffic detected - PoW required",
            message = "Please complete proof-of-work challenge",
            challenge_url = "/pow-challenge?fp=" .. ngx.escape_uri(fingerprint),
            verify_url = "/pow-verify"
        }))
            return ngx.exit(429)
        else
            ngx.req.set_header("X-PoW-Verified", "true")
        end
    end
    
    red:close()
end
