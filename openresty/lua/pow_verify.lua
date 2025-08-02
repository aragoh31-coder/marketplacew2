local redis = require "resty.redis"
local json = require "cjson.safe"

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

local function verify_sha256_solution(challenge, solution)
    local input = challenge.nonce .. solution
    local hash = ngx.sha1_bin(input)
    local hex_hash = ""
    
    for i = 1, #hash do
        hex_hash = hex_hash .. string.format("%02x", string.byte(hash, i))
    end
    
    local leading_zeros = 0
    for i = 1, #hex_hash do
        local char = string.sub(hex_hash, i, i)
        if char == "0" then
            leading_zeros = leading_zeros + 1
        else
            break
        end
    end
    
    return leading_zeros >= (challenge.difficulty or 4)
end

ngx.header.content_type = "application/json"
ngx.header["Cache-Control"] = "no-cache, no-store, must-revalidate"

ngx.req.read_body()
local body = ngx.req.get_body_data()
if not body then
    ngx.status = 400
    ngx.say(json.encode({error = "Missing request body"}))
    return
end

local data = json.decode(body)
if not data or not data.fingerprint or not data.solution then
    ngx.status = 400
    ngx.say(json.encode({error = "Invalid request format. Required: fingerprint, solution"}))
    return
end

local red = connect_redis()
if not red then
    ngx.status = 503
    ngx.say(json.encode({error = "Service unavailable"}))
    return
end

local challenge_key = "pow_challenge:" .. data.fingerprint
local challenge_data = red:get(challenge_key)

if challenge_data == ngx.null then
    ngx.status = 404
    ngx.say(json.encode({error = "Challenge not found or expired"}))
    return
end

local challenge = json.decode(challenge_data)

if ngx.time() - challenge.timestamp > 300 then
    red:del(challenge_key)
    ngx.status = 410
    ngx.say(json.encode({error = "Challenge expired"}))
    return
end

if verify_sha256_solution(challenge, data.solution) then
    local valid_key = "pow_valid:" .. data.fingerprint
    red:setex(valid_key, 3600, "true")
    red:del(challenge_key)
    
    ngx.say(json.encode({
        success = true, 
        message = "PoW verified successfully",
        valid_for = "1 hour"
    }))
else
    ngx.status = 403
    ngx.say(json.encode({
        success = false, 
        message = "Invalid PoW solution"
    }))
end

red:close()
