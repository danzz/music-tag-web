#!/usr/bin/env bash
# ==============================================================================
# 本地测试环境一键启动脚本 (Local Test Environment Launcher)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

TEST_PORT=18002
CONTAINER_NAME="music-tag-web-test"

echo "=========================================================="
echo "🚀 正在启动 Music Tag Web 本地独立测试环境..."
echo "=========================================================="

# 1. 检查并生成测试数据
if [ ! -d "test_environment/media/01_精选专辑" ]; then
    echo "[*] 未检测到完整测试曲库，正在自动生成测试音频与数据..."
    python3 scripts/generate_test_library.py
else
    echo "[√] 测试曲库数据就绪 (test_environment/media)"
fi

mkdir -p test_environment/config

# 2. 检查是否需要重新编译前端
if [ ! -f "static/dist/index.prod.html" ]; then
    echo "[*] 正在编译前端资源..."
    cd web && NODE_OPTIONS=--openssl-legacy-provider npm run build && cd ..
fi

# 3. 构建/确认本地镜像
echo "[*] 检查/构建本地测试镜像 (music-tag-web:local)..."
docker build -t music-tag-web:local -t music-tag-web:latest .

# 4. 停止并移除已有测试容器
if [ "$(docker ps -aq -f name=^/${CONTAINER_NAME}$)" ]; then
    echo "[*] 清理旧的测试容器: ${CONTAINER_NAME}"
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

# 5. 启动测试容器
echo "[*] 启动测试容器 (绑定端口: ${TEST_PORT})..."
docker run -d --name "${CONTAINER_NAME}" \
  -p "${TEST_PORT}:8001" \
  -e DJANGO_SECRET_KEY="test-environment-secret-key-123456" \
  -e WORKER_NUM=1 \
  -v "${SCRIPT_DIR}/test_environment/media:/app/media:rw" \
  -v "${SCRIPT_DIR}/test_environment/config:/app/data:rw" \
  --restart=unless-stopped \
  music-tag-web:local

# 6. 等待就绪并健康检查
echo -n "[*] 等待服务初始化与数据库迁移"
for i in {1..15}; do
    if curl -s -f "http://127.0.0.1:${TEST_PORT}/" >/dev/null 2>&1; then
        echo -e "\n[√] 服务已成功就绪！"
        break
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "=========================================================="
echo "🎉 测试环境已启动！"
echo "🌐 访问地址: http://127.0.0.1:${TEST_PORT}/"
echo "🔑 初始账号: admin"
echo "🔑 初始密码: admin"
echo "📁 测试媒体库挂载: ${SCRIPT_DIR}/test_environment/media"
echo "💾 配置持久化挂载: ${SCRIPT_DIR}/test_environment/config"
echo "📋 查看容器日志: docker logs -f ${CONTAINER_NAME}"
echo "🛑 停止测试环境: ./stop_test_env.sh"
echo "=========================================================="

