# 在 8.120 机器上执行的脚本

# 1. 设置环境变量
export PREFECT_API_URL=http://192.168.8.127:4200/api

# 2. 验证连接
echo "Testing connection to Prefect server..."
curl $PREFECT_API_URL/health

# 3. 启动 worker
echo "Starting worker..."
uv run prefect worker start --pool default-agent-pool --api $PREFECT_API_URL