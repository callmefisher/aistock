#!/bin/bash

set -e

echo "========================================="
echo "智能构建脚本 - 仅在变更时重建"
echo "========================================="

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

export DOCKER_BUILDKIT=1

case "${1:-backend}" in
    backend)
        log_info "构建后端镜像..."
        docker compose -f docker-compose.minimal.yml build backend
        docker compose -f docker-compose.minimal.yml up -d backend
        log_success "后端构建完成"
        ;;
    frontend)
        log_info "构建前端镜像..."
        docker compose -f docker-compose.minimal.yml build frontend
        docker compose -f docker-compose.minimal.yml up -d frontend
        log_success "前端构建完成"
        ;;
    all)
        log_info "构建所有服务..."
        docker compose -f docker-compose.minimal.yml build
        docker compose -f docker-compose.minimal.yml up -d
        log_success "所有服务构建完成"
        ;;
    rebuild)
        log_info "强制全量重建..."
        docker compose -f docker-compose.minimal.yml build --no-cache
        docker compose -f docker-compose.minimal.yml up -d
        log_success "全量重建完成"
        ;;
    *)
        log_error "未知选项: $1"
        echo "用法: $0 [backend|frontend|all|rebuild]"
        exit 1
        ;;
esac
