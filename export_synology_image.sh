#!/usr/bin/env bash
# ==============================================================================
# 群晖 NAS (linux/amd64) 离线镜像打包与导出脚本
# Music Tag Web Synology Image Export Script
# ==============================================================================
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

IMAGE_NAME="music-tag-web"
IMAGE_TAG="v2.0"
OUTPUT_TAR="music-tag-web-synology.tar"
BUILD_FRONTEND=true

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-frontend)
            BUILD_FRONTEND=false
            shift
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --output|-o)
            OUTPUT_TAR="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: ./export_synology_image.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --output, -o <路径>   指定导出的 tar 文件名 (默认: music-tag-web-synology.tar)"
            echo "  --tag <版本标签>      指定镜像版本标签 (默认: v2.0)"
            echo "  --skip-frontend       跳过前端 npm run build 编译步骤"
            echo "  -h, --help            显示帮助信息"
            exit 0
            ;;
        *)
            OUTPUT_TAR="$1"
            shift
            ;;
    esac
done

echo "=========================================================="
echo "📦 正在执行群晖专用镜像构建与导出流程..."
echo "🖥️  目标架构: linux/amd64 (群晖 x86_64 NAS)"
echo "🏷️  目标镜像: ${IMAGE_NAME}:${IMAGE_TAG} 与 ${IMAGE_NAME}:latest"
echo "📁 输出文件: ${OUTPUT_TAR}"
echo "=========================================================="

# 1. 编译前端生产静态资源
if [ "$BUILD_FRONTEND" = true ]; then
    echo "[1/3] 正在编译前端代码 (NODE_OPTIONS=--openssl-legacy-provider npm run build)..."
    cd web
    NODE_OPTIONS=--openssl-legacy-provider npm run build
    cd ..
    if [ ! -f "static/dist/index.prod.html" ]; then
        echo "❌ 错误: 前端编译未能生成 static/dist/index.prod.html"
        exit 1
    fi
    echo "[√] 前端打包完成。"
else
    echo "[1/3] 已跳过前端编译 (--skip-frontend)。"
fi

# 2. 构建 linux/amd64 架构 Docker 镜像
echo "[2/3] 正在使用 buildx 构建 linux/amd64 镜像..."
docker buildx build --platform linux/amd64 \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -t "${IMAGE_NAME}:latest" \
    --load \
    .
echo "[√] 镜像构建完成。"

# 3. 导出为群晖可直接导入的 tar 包
echo "[3/3] 正在导出镜像到 ${OUTPUT_TAR}..."
docker save "${IMAGE_NAME}:${IMAGE_TAG}" "${IMAGE_NAME}:latest" -o "${OUTPUT_TAR}"

TAR_SIZE=$(du -h "${OUTPUT_TAR}" | cut -f1)
echo "[√] 导出完成: $(pwd)/${OUTPUT_TAR} (大小: ${TAR_SIZE})"

echo "=========================================================="
echo "🎉 群晖离线镜像包已就绪！"
echo ""
echo "📥 群晖 Container Manager 导入与更新说明:"
echo " 1. 打开群晖 DSM -> Container Manager ->「映像」页面"
echo " 2. 点击「操作 / 添加」->「从文件添加」"
echo " 3. 选择并上传 ${OUTPUT_TAR}"
echo " 4. 在「容器」列表中重启 music-tag-web 容器即可生效"
echo "=========================================================="

