#!/usr/bin/env bash
# ==============================================================================
# 发布镜像构建脚本 (Music Tag Web Release Builder)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

DEFAULT_IMAGE="music-tag-web"
DEFAULT_TAG="v2.0"
TARGET_IMAGE="${1:-${DEFAULT_IMAGE}:${DEFAULT_TAG}}"
LATEST_IMAGE="${TARGET_IMAGE%%:*}:latest"

MULTIARCH=false
EXPORT_TAR=false

for arg in "$@"; do
    case "$arg" in
        --multiarch)
            MULTIARCH=true
            ;;
        --export)
            EXPORT_TAR=true
            ;;
    esac
done

echo "=========================================================="
echo "📦 正在执行 Music Tag Web 镜像打包与发布流程..."
echo "🏷️  目标镜像名称: ${TARGET_IMAGE}"
echo "🏷️  附加标签:     ${LATEST_IMAGE}"
echo "=========================================================="

# 1. 编译前端生产静态资源
echo "[1/4] 正在编译前端生产代码 (npm run build)..."
cd web
NODE_OPTIONS=--openssl-legacy-provider npm run build
cd ..

if [ ! -f "static/dist/index.prod.html" ]; then
    echo "❌ 错误: 前端编译未能生成 static/dist/index.prod.html"
    exit 1
fi
echo "[√] 前端打包完成。"

# 2. 构建 Docker 镜像
if [ "$MULTIARCH" = true ]; then
    echo "[2/4] 使用 buildx 进行多架构构建 (linux/amd64, linux/arm64)..."
    docker buildx build --platform linux/amd64,linux/arm64 \
        -t "${TARGET_IMAGE}" \
        -t "${LATEST_IMAGE}" \
        .
else
    echo "[2/4] 构建本地平台 Docker 镜像..."
    docker build \
        -t "${TARGET_IMAGE}" \
        -t "${LATEST_IMAGE}" \
        .
fi
echo "[√] Docker 镜像构建完成。"

# 3. 校验镜像
echo "[3/4] 校验镜像信息..."
docker images | grep "${TARGET_IMAGE%%:*}" | head -n 5

# 4. 可选：导出离线安装包
if [ "$EXPORT_TAR" = true ]; then
    TAR_NAME="music-tag-web-$(date +%Y%m%d).tar.gz"
    echo "[4/4] 正在导出离线镜像包: ${TAR_NAME}..."
    docker save "${TARGET_IMAGE}" | gzip > "${TAR_NAME}"
    echo "[√] 离线镜像已导出: $(pwd)/${TAR_NAME} ($(du -h "${TAR_NAME}" | cut -f1))"
else
    echo "[4/4] 如需导出离线 tar 镜像，可执行: ./build_release.sh ${TARGET_IMAGE} --export"
fi

echo "=========================================================="
echo "🎉 打包完成！"
echo "👉 本地快速运行验证:"
echo "   docker run -d -p 8001:8001 -e DJANGO_SECRET_KEY=\"your-secret\" -v /path/to/music:/app/media ${TARGET_IMAGE}"
echo "👉 推送至 Docker Hub / 私有仓库:"
echo "   docker tag ${TARGET_IMAGE} your-username/${TARGET_IMAGE}"
echo "   docker push your-username/${TARGET_IMAGE}"
echo "=========================================================="

