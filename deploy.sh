#!/bin/bash

set -e

echo "========================================="
echo "选股池自动化系统 - Docker Compose 部署"
echo "========================================="
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

cd "$(dirname "$0")"

COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="aistock"

get_compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif docker compose version &> /dev/null 2>&1; then
        echo "docker compose"
    else
        log_error "Docker Compose 未安装"
        exit 1
    fi
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    if ! docker info &> /dev/null; then
        log_error "Docker 未运行"
        exit 1
    fi
    log_success "Docker 环境检查通过"
}

build() {
    local service="${1:-}"
    log_info "构建镜像..."
    if [ -n "$service" ]; then
        $COMPOSE_CMD -f "$COMPOSE_FILE" build "$service"
        log_success "$service 镜像构建完成"
    else
        $COMPOSE_CMD -f "$COMPOSE_FILE" build
        log_success "所有镜像构建完成"
    fi
}

up() {
    log_info "启动服务..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d
    log_success "服务启动完成"
}

down() {
    log_info "停止服务..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" down
    log_success "服务已停止"
}

restart() {
    down
    up
}

start() {
    log_info "启动服务..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" start
    log_success "服务启动完成"
}

stop() {
    log_info "停止服务..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" stop
    log_success "服务已停止"
}

ps_status() {
    echo ""
    echo "========================================="
    echo "服务状态 [${PROJECT_NAME}]"
    echo "========================================="
    echo ""
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps
    echo ""
    echo "访问地址："
    echo "  前端界面: http://localhost:7654"
    echo "  API文档:  http://localhost:8000/docs"
    echo "  数据库:   localhost:3306"
}

logs() {
    local service="${1:-backend}"
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f "$service"
}

exec_cmd() {
    local service="$1"
    shift
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec "$service" "$@"
}

init_db() {
    log_info "初始化数据库表..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T mysql mysql -uroot -proot_password stock_pool < fix_tables.sql 2>/dev/null || true
    log_success "数据库初始化完成"
}

usage() {
    echo ""
    echo "用法: ./deploy.sh [命令] [服务]"
    echo ""
    echo "命令："
    echo "  up       启动所有服务（创建并启动）"
    echo "  down     停止并移除所有服务"
    echo "  start    启动已存在的服务"
    echo "  stop     停止服务"
    echo "  restart  重启所有服务"
    echo "  build    构建所有镜像"
    echo "  build [服务]  构建指定服务镜像"
    echo "  ps       查看服务状态"
    echo "  logs     查看后端日志"
    echo "  logs [服务]  查看指定服务日志"
    echo "  init-db  初始化数据库表"
    echo "  exec [服务] [命令]  在服务容器中执行命令"
    echo ""
    echo "示例："
    echo "  ./deploy.sh up           启动所有服务"
    echo "  ./deploy.sh build        构建所有镜像"
    echo "  ./deploy.sh build backend  仅构建后端镜像"
    echo "  ./deploy.sh logs         查看后端日志"
    echo "  ./deploy.sh logs mysql   查看MySQL日志"
    echo "  ./deploy.sh exec mysql mysql -uroot -proot_password"
    echo ""
}

COMPOSE_CMD=$(get_compose_cmd)

case "${1:-}" in
    up)
        check_docker
        build
        up
        ps_status
        ;;
    down)
        down
        ;;
    start)
        check_docker
        start
        ps_status
        ;;
    stop)
        stop
        ;;
    restart)
        check_docker
        restart
        ps_status
        ;;
    build)
        check_docker
        build "$2"
        ;;
    ps|status)
        ps_status
        ;;
    logs)
        logs "${2:-backend}"
        ;;
    init-db)
        init_db
        ;;
    exec)
        if [ -z "$2" ]; then
            log_error "请指定服务名"
            exit 1
        fi
        exec_cmd "$@"
        ;;
    *)
        usage
        ;;
esac