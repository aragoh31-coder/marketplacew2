local redis = require "resty.redis"
local json = require "cjson.safe"

local function connect_redis()
    local red = redis:new()
    red:set_timeout(1000)
    local ok, err = red:connect(os.getenv("REDIS_HOST") or "redis", 
                               tonumber(os.getenv("REDIS_PORT")) or 6379)
    if not ok then
        return nil
    end
    return red
end

local function get_cache_stats()
    local rl_cache = ngx.shared.rl_cache
    local pow_cache = ngx.shared.pow_cache
    local session_cache = ngx.shared.session_cache
    local blocked_ips = ngx.shared.blocked_ips
    
    return {
        rl_cache = {
            size = rl_cache:capacity(),
            free_space = rl_cache:free_space()
        },
        pow_cache = {
            size = pow_cache:capacity(),
            free_space = pow_cache:free_space()
        },
        session_cache = {
            size = session_cache:capacity(),
            free_space = session_cache:free_space()
        },
        blocked_ips = {
            size = blocked_ips:capacity(),
            free_space = blocked_ips:free_space()
        }
    }
end

local function get_redis_stats()
    local red = connect_redis()
    if not red then
        return {error = "Redis connection failed"}
    end
    
    local info = red:info("memory")
    local keyspace = red:info("keyspace")
    
    red:close()
    
    return {
        memory_info = info,
        keyspace_info = keyspace
    }
end

ngx.header.content_type = "application/json"

local status = {
    timestamp = ngx.time(),
    openresty_version = ngx.config.nginx_version,
    worker_pid = ngx.worker.pid(),
    cache_stats = get_cache_stats(),
    redis_stats = get_redis_stats(),
    system_info = {
        time = os.date("%Y-%m-%d %H:%M:%S"),
        uptime = ngx.time() - ngx.config.subsystem
    }
}

ngx.say(json.encode(status))
