#!/bin/bash

set -e

echo "========================================="
echo "选股池自动化系统 - 智能部署脚本"
echo "========================================="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     echo "linux" ;;
        CYGWIN*)    echo "windows" ;;
        MINGW*)     echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64)   echo "amd64" ;;
        arm64|aarch64)  echo "arm64" ;;
        armv7l)         echo "armv7" ;;
        *)              echo "unknown" ;;
    esac
}

get_platform() {
    local os=$(detect_os)
    local arch=$(detect_arch)
    echo "${os}-${arch}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker未运行，请启动Docker"
        exit 1
    fi
    
    log_success "Docker环境检查通过"
}

check_docker_compose() {
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        log_error "Docker Compose未安装"
        exit 1
    fi
    
    log_success "Docker Compose环境检查通过"
}

image_exists() {
    local image_name=$1
    docker image inspect "$image_name" &> /dev/null
}

pull_image_if_needed() {
    local image_name=$1
    local image_alias=$2
    
    if image_exists "$image_name"; then
        log_info "镜像已存在: $image_alias"
        return 0
    fi
    
    log_info "拉取镜像: $image_alias"
    if docker pull "$image_name"; then
        log_success "镜像拉取成功: $image_alias"
    else
        log_error "镜像拉取失败: $image_alias"
        return 1
    fi
}

build_image_if_needed() {
    local image_name=$1
    local dockerfile=$2
    local context=$3
    local force=$4
    
    if [ "$force" = "true" ] || ! image_exists "$image_name"; then
        log_info "构建镜像: $image_name"
        
        $COMPOSE_CMD build --no-cache \
            --build-arg BUILDKIT_INLINE_CACHE=1 \
            "$image_name" 2>&1 | while IFS= read -r line; do
                if [[ $line == *"Successfully"* ]] || [[ $line == *"Successfully built"* ]] || [[ $line == *"Successfully tagged"* ]]; then
                    log_success "$line"
                else
                    echo "  $line"
                fi
            done
        
        log_success "镜像构建完成: $image_name"
    else
        log_info "镜像已存在，跳过构建: $image_name"
    fi
}

clean_docker_cache() {
    log_info "清理Docker构建缓存..."
    
    docker builder prune -f &> /dev/null || true
    
    local dangling_images=$(docker images -f "dangling=true" -q)
    if [ -n "$dangling_images" ]; then
        log_info "清理悬空镜像..."
        docker rmi $dangling_images &> /dev/null || true
    fi
    
    log_success "Docker缓存清理完成"
}

check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 1
    else
        return 0
    fi
}

find_available_port() {
    local start_port=$1
    local max_attempts=100
    local port=$start_port
    
    for i in $(seq 1 $max_attempts); do
        if check_port $port; then
            echo $port
            return 0
        fi
        port=$((port + 1))
    done
    
    echo ""
    return 1
}

detect_ports() {
    log_info "检测端口占用情况..."
    
    FRONTEND_PORT=80
    BACKEND_PORT=8000
    MYSQL_PORT=3306
    REDIS_PORT=6379
    SELENIUM_PORT=4444
    SELENIUM_VNC_PORT=7900
    
    if ! check_port $FRONTEND_PORT; then
        log_warning "端口 $FRONTEND_PORT 已被占用"
        FRONTEND_PORT=$(find_available_port 8080)
        [ -z "$FRONTEND_PORT" ] && { log_error "无法找到可用的前端端口"; exit 1; }
        log_success "自动切换到端口: $FRONTEND_PORT"
    fi
    
    if ! check_port $BACKEND_PORT; then
        log_warning "端口 $BACKEND_PORT 已被占用"
        BACKEND_PORT=$(find_available_port 8001)
        [ -z "$BACKEND_PORT" ] && { log_error "无法找到可用的后端端口"; exit 1; }
        log_success "自动切换到端口: $BACKEND_PORT"
    fi
    
    if ! check_port $MYSQL_PORT; then
        log_warning "端口 $MYSQL_PORT 已被占用"
        MYSQL_PORT=$(find_available_port 3307)
        [ -z "$MYSQL_PORT" ] && { log_error "无法找到可用的MySQL端口"; exit 1; }
        log_success "自动切换到端口: $MYSQL_PORT"
    fi
    
    if ! check_port $REDIS_PORT; then
        log_warning "端口 $REDIS_PORT 已被占用"
        REDIS_PORT=$(find_available_port 6380)
        [ -z "$REDIS_PORT" ] && { log_error "无法找到可用的Redis端口"; exit 1; }
        log_success "自动切换到端口: $REDIS_PORT"
    fi
    
    log_success "端口检测完成"
}

create_docker_compose_override() {
    log_info "生成docker-compose.override.yml..."
    
    cat > docker-compose.override.yml <<EOF
version: '3.8'

services:
  mysql:
    ports:
      - "$MYSQL_PORT:3306"
  
  redis:
    ports:
      - "$REDIS_PORT:6379"
  
  backend:
    ports:
      - "$BACKEND_PORT:8000"
  
  frontend:
    ports:
      - "$FRONTEND_PORT:80"
EOF
    
    log_success "端口配置文件生成完成"
}

create_env_file() {
    if [ ! -f .env ]; then
        log_info "创建.env文件..."
        cp .env.example .env
        log_warning "请编辑.env文件，配置必要的参数"
    fi
}

pull_base_images() {
    log_info "检查并拉取基础镜像..."
    
    pull_image_if_needed "mysql:8.0" "MySQL 8.0"
    pull_image_if_needed "redis:7-alpine" "Redis 7"
    pull_image_if_needed "nginx:alpine" "Nginx"
    
    local platform=$(get_platform)
    if [[ "$platform" == *"arm64" ]]; then
        log_info "检测到ARM64架构，使用seleniarm镜像"
        pull_image_if_needed "seleniarm/standalone-chromium:latest" "Selenium ARM64" || {
            log_warning "Selenium ARM64镜像拉取失败，将跳过Selenium服务"
            SKIP_SELENIUM=true
        }
    else
        pull_image_if_needed "selenium/standalone-chrome:latest" "Selenium" || {
            log_warning "Selenium镜像拉取失败，将跳过Selenium服务"
            SKIP_SELENIUM=true
        }
    fi
    
    log_success "基础镜像检查完成"
}

build_custom_images() {
    log_info "构建自定义镜像..."
    
    build_image_if_needed "aistock-backend:latest" "backend/Dockerfile" "backend" "$FORCE_BUILD"
    
    log_success "自定义镜像构建完成"
}

start_services() {
    log_info "启动服务..."
    
    if [ "$SKIP_SELENIUM" = true ]; then
        log_warning "Selenium服务将被跳过"
        $COMPOSE_CMD -f docker-compose.minimal.yml up -d
    else
        $COMPOSE_CMD up -d
    fi
    
    log_success "服务启动完成"
}

show_status() {
    echo ""
    echo "========================================="
    echo "部署完成！"
    echo "========================================="
    echo ""
    echo "平台信息："
    echo "  操作系统: $(detect_os)"
    echo "  架构: $(detect_arch)"
    echo ""
    echo "访问地址："
    echo "  前端界面: http://localhost:$FRONTEND_PORT"
    echo "  API文档:  http://localhost:$BACKEND_PORT/docs"
    echo "  API地址:  http://localhost:$BACKEND_PORT/api/v1"
    echo ""
    echo "数据库连接："
    echo "  MySQL: localhost:$MYSQL_PORT"
    echo "  Redis: localhost:$REDIS_PORT"
    echo ""
    echo "管理命令："
    echo "  查看状态: $COMPOSE_CMD ps"
    echo "  查看日志: $COMPOSE_CMD logs -f backend"
    echo "  停止服务: $COMPOSE_CMD down"
    echo "  重启服务: $COMPOSE_CMD restart"
    echo ""
    echo "========================================="
}

main() {
    local FORCE_BUILD=false
    local SKIP_SELENIUM=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force|-f)
                FORCE_BUILD=true
                shift
                ;;
            --no-cache)
                FORCE_BUILD=true
                shift
                ;;
            --help|-h)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项："
                echo "  --force, -f      强制重新构建镜像"
                echo "  --no-cache       不使用缓存构建镜像"
                echo "  --help, -h       显示帮助信息"
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                exit 1
                ;;
        esac
    done
    
    log_info "开始部署..."
    log_info "检测平台: $(get_platform)"
    
    check_docker
    check_docker_compose
    create_env_file
    detect_ports
    create_docker_compose_override
    
    if [ "$FORCE_BUILD" = true ]; then
        clean_docker_cache
    fi
    
    pull_base_images
    build_custom_images
    start_services
    show_status
}

main "$@"
