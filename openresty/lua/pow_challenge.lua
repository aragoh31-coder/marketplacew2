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

local function generate_challenge(difficulty)
    local challenge = {
        nonce = ngx.encode_base64(string.sub(tostring(math.random()), 3)),
        timestamp = ngx.time(),
        difficulty = difficulty or 4,
        type = "sha256"
    }
    
    return challenge
end

ngx.header.content_type = "application/json"
ngx.header["Cache-Control"] = "no-cache, no-store, must-revalidate"
ngx.header["Pragma"] = "no-cache"
ngx.header["Expires"] = "0"

local red = connect_redis()
if not red then
    ngx.status = 503
    ngx.say(json.encode({error = "Service unavailable"}))
    return
end

local fingerprint = ngx.var.arg_fp or "unknown"
if fingerprint == "unknown" then
    ngx.status = 400
    ngx.say(json.encode({error = "Missing fingerprint parameter"}))
    return
end

local challenge_key = "pow_challenge:" .. fingerprint
local existing_challenge = red:get(challenge_key)

local challenge
if existing_challenge ~= ngx.null then
    challenge = json.decode(existing_challenge)
else
    challenge = generate_challenge(4)
    red:setex(challenge_key, 300, json.encode(challenge))
end

ngx.say(json.encode({
    challenge = challenge,
    instructions = "Find a solution where SHA256(nonce + solution) has " .. challenge.difficulty .. " leading zeros",
    example = "Try different values until hash starts with " .. string.rep("0", challenge.difficulty)
}))

red:close()
