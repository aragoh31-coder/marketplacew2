#!/bin/bash

echo "Installing OpenResty Lua dependencies..."

apk update
apk add --no-cache luarocks

luarocks install lua-resty-redis
luarocks install lua-cjson

echo "OpenResty dependencies installed successfully"
