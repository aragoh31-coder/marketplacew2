local redis = require "resty.redis"
local json = require "cjson.safe"

local _M = {}

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

local function solve_sha256_challenge(challenge)
    local nonce = challenge.nonce
    local difficulty = challenge.difficulty or 4
    local target_zeros = string.rep("0", difficulty)
    
    for i = 1, 100000 do
        local solution = tostring(i)
        local input = nonce .. solution
        local hash = ngx.sha1_bin(input)
        local hex_hash = ""
        
        for j = 1, #hash do
            hex_hash = hex_hash .. string.format("%02x", string.byte(hash, j))
        end
        
        if string.sub(hex_hash, 1, difficulty) == target_zeros then
            return solution
        end
    end
    
    return nil
end

function _M.start_background_solver()
    ngx.timer.every(5, function()
        local red = connect_redis()
        if not red then
            return
        end
        
        local keys = red:keys("pow_challenge:*")
        if keys and type(keys) == "table" then
            for _, key in ipairs(keys) do
                local challenge_data = red:get(key)
                if challenge_data ~= ngx.null then
                    local challenge = json.decode(challenge_data)
                    
                    if challenge and ngx.time() - challenge.timestamp < 240 then
                        local solution = solve_sha256_challenge(challenge)
                        
                        if solution then
                            local fingerprint = string.match(key, "pow_challenge:(.+)")
                            if fingerprint then
                                local valid_key = "pow_valid:" .. fingerprint
                                red:setex(valid_key, 3600, "true")
                                red:del(key)
                                ngx.log(ngx.INFO, "Auto-solved PoW for fingerprint: ", fingerprint)
                            end
                        end
                    end
                end
            end
        end
        
        red:close()
    end)
end

return _M
