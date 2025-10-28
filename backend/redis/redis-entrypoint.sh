#!/bin/sh
set -e

# Create config directory if it doesn't exist
mkdir -p /usr/local/etc/redis

# Generate redis.conf with environment variable
cat > /usr/local/etc/redis/redis.conf <<EOF
# Password authentication
requirepass ${REDIS_PASSWORD}

# Protected mode
protected-mode yes

# 持久化
dir /data
appendonly yes

# 阻止被外部 REPLICAOF 攻擊
# 不允許外部客戶端設置 replica
rename-command REPLICAOF ""
EOF

# Start Redis with the generated config
exec redis-server /usr/local/etc/redis/redis.conf