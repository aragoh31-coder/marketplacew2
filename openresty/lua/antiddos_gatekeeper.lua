
local function is_anti_ddos_path()
    local uri = ngx.var.uri
    return string.match(uri, "^/anti_ddos/") ~= nil
end

local function is_static_asset()
    local uri = ngx.var.uri
    return string.match(uri, "^/static/") or
           string.match(uri, "^/media/") or
           string.match(uri, "%.css$") or 
           string.match(uri, "%.js$") or 
           string.match(uri, "%.png$") or 
           string.match(uri, "%.jpg$") or 
           string.match(uri, "%.jpeg$") or 
           string.match(uri, "%.gif$") or 
           string.match(uri, "%.ico$") or 
           string.match(uri, "%.svg$") or 
           string.match(uri, "%.woff") or 
           string.match(uri, "%.ttf$") or
           string.match(uri, "%.map$")
end

local function is_health_check()
    local uri = ngx.var.uri
    return uri == "/health" or uri == "/openresty-status"
end

if is_anti_ddos_path() or is_static_asset() or is_health_check() then
    return
end

local token = ngx.var.cookie_hmac_token
if not token or token == "" then
    ngx.log(ngx.INFO, "HMAC gatekeeper: No token, uri=" .. (ngx.var.uri or ""))
    return ngx.redirect("/anti_ddos/spinner/")
end

ngx.log(ngx.INFO, "HMAC gatekeeper: Token present, uri=" .. (ngx.var.uri or ""))
