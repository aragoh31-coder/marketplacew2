#!/usr/bin/env lua

local redis = require "resty.redis"
local json = require "cjson.safe"

local function connect_redis()
    local red = redis:new()
    red:set_timeout(1000)
    local ok, err = red:connect(os.getenv("REDIS_HOST") or "redis", 
                               tonumber(os.getenv("REDIS_PORT")) or 6379)
    if not ok then
        print("Failed to connect to Redis: " .. (err or "unknown error"))
        return nil
    end
    return red
end

local function solve_sha256_challenge(challenge)
    local nonce = challenge.nonce
    local difficulty = challenge.difficulty or 4
    local target_zeros = string.rep("0", difficulty)
    
    for i = 1, 1000000 do
        local solution = tostring(i)
        local input = nonce .. solution
        
        local handle = io.popen("echo -n '" .. input .. "' | sha256sum")
        local result = handle:read("*a")
        handle:close()
        
        local hash = string.match(result, "^(%w+)")
        
        if hash and string.sub(hash, 1, difficulty) == target_zeros then
            return solution
        end
    end
    
    return nil
end

print("Starting standalone PoW solver...")

while true do
    local red = connect_redis()
    if red then
        local keys = red:keys("pow_challenge:*")
        if keys and type(keys) == "table" then
            for _, key in ipairs(keys) do
                local challenge_data = red:get(key)
                if challenge_data ~= ngx.null then
                    local challenge = json.decode(challenge_data)
                    
                    if challenge and os.time() - challenge.timestamp < 240 then
                        local solution = solve_sha256_challenge(challenge)
                        
                        if solution then
                            local fingerprint = string.match(key, "pow_challenge:(.+)")
                            if fingerprint then
                                local valid_key = "pow_valid:" .. fingerprint
                                red:setex(valid_key, 3600, "true")
                                red:del(key)
                                print("Auto-solved PoW for fingerprint: " .. fingerprint)
                            end
                        end
                    end
                end
            end
        end
        red:close()
    end
    
    os.execute("sleep 5")
end
