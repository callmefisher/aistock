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

COMPOSE_FILE="docker-compose.minimal.yml"
PROJECT_NAME="aistock"

get_compose_cmd() {
    # 优先 docker compose v2: Dockerfile 使用 BuildKit cache mount，compose v1 不支持
    if docker compose version &> /dev/null 2>&1; then
        echo "docker compose"
    elif command -v docker-compose &> /dev/null; then
        log_warning "检测到 compose v1（docker-compose），cache mount 构建可能失败，建议升级到 Docker Compose v2"
        echo "docker-compose"
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
    log_info "构建镜像..."
    if [ -n "${1:-}" ]; then
        # 支持多服务转发: build backend frontend
        $COMPOSE_CMD -f "$COMPOSE_FILE" build "$@"
        log_success "$* 镜像构建完成"
    else
        $COMPOSE_CMD -f "$COMPOSE_FILE" build
        log_success "所有镜像构建完成"
    fi
}

# 指纹哈希工具（兼容 macOS/BSD 与 Linux）
MD5_CMD="md5sum"
command -v md5sum >/dev/null 2>&1 || MD5_CMD="md5 -q"

# 计算单侧构建指纹: 目录内"文件清单 + 每个文件内容哈希"
# 直接基于文件内容而非 git diff，未提交/未跟踪的新文件同样触发构建
# 排除清单与 .dockerignore 对齐：运行时产物与本地环境不参与指纹
_service_fingerprint() {
    local dir="$1" files
    files=$(find "$dir" \
        \( -name node_modules -o -name venv -o -name .venv \
        -o -name __pycache__ -o -name htmlcov -o -name .pytest_cache \
        -o -name dist -o -name dist-ssr -o -name coverage -o -name docs \
        -o -name data -o -name .git -o -name .DS_Store \) -prune \
        -o -type f ! -name '*.log' ! -name '*.sqlite' ! -name '*.db' \
        ! -name '.coverage' ! -name '*.pyc' ! -name '.env' \
        ! -name '*.bak' ! -name '*.tmp' ! -name '*.md' -print 2>/dev/null | sort)
    {
        printf '%s\n' "$files"
        [ -n "$files" ] && printf '%s\n' "$files" | tr '\n' '\0' | xargs -0 $MD5_CMD 2>/dev/null
    } | $MD5_CMD | awk '{print $1}'
}

# 轻量清理: 保留在用镜像 + 最近10GB构建缓存，砍掉悬空镜像和旧缓存
# 不使用 -a，避免删除正在使用的 tagged 镜像
auto_cleanup() {
    log_info "自动清理 Docker 缓存..."
    docker image prune -f >/dev/null 2>&1
    docker builder prune --keep-storage 10gb -f >/dev/null 2>&1
    local disk_info
    disk_info=$(docker system df --format "table {{.Type}}\t{{.Size}}\t{{.Reclaimable}}" 2>/dev/null | tail -n +2)
    log_success "清理完成，当前占用："
    echo "$disk_info" | sed 's/^/    /'
}

# 深度清理: 手动触发，删除所有未被服务使用的资源
deep_cleanup() {
    log_warning "深度清理：将删除所有未被服务使用的镜像、卷、缓存..."
    docker image prune -af >/dev/null 2>&1
    docker builder prune -af >/dev/null 2>&1
    docker volume prune -f >/dev/null 2>&1
    log_success "深度清理完成"
    docker system df
}

# 智能构建: 前后端指纹独立对比，仅重建变更侧镜像；构建后自动轻量清理
smart_build() {
    local fp_dir=".build-fingerprints"
    local compose_fp backend_fp frontend_fp
    compose_fp=$($MD5_CMD < "$COMPOSE_FILE" | awk '{print $1}')
    backend_fp="${compose_fp}:$(_service_fingerprint backend)"
    frontend_fp="${compose_fp}:$(_service_fingerprint frontend)"

    local changed=()
    [ "$backend_fp" != "$(cat "$fp_dir/backend" 2>/dev/null)" ] && changed+=(backend)
    [ "$frontend_fp" != "$(cat "$fp_dir/frontend" 2>/dev/null)" ] && changed+=(frontend)

    # 旧版单指纹文件迁移: 存在则触发一次全量构建后切换到新机制
    if [ -f .last-built-fingerprint ]; then
        rm -f .last-built-fingerprint
        changed=(backend frontend)
    fi

    if [ ${#changed[@]} -eq 0 ]; then
        log_success "无构建影响的变更，跳过 build"
        return 0
    fi

    log_info "检测到变更: ${changed[*]}，开始构建..."
    # set -e 下用 if 包装: 构建失败走显式失败分支，不更新指纹，下次 smart-build 自动重试
    if ! build "${changed[@]}"; then
        log_error "构建失败，指纹未更新"
        return 1
    fi
    mkdir -p "$fp_dir"
    echo "$backend_fp" > "$fp_dir/backend"
    echo "$frontend_fp" > "$fp_dir/frontend"
    log_success "构建指纹已更新"
    auto_cleanup
    log_info "构建成功，自动重启服务..."
    up
    return 0
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
    echo "  API文档:  http://localhost:8001/docs"
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

promote_admin() {
    local username="${1:-}"
    if [ -z "$username" ]; then
        log_error "用法: ./deploy.sh promote-admin <username>"
        return 1
    fi
    log_info "把用户 '$username' 提升为管理员..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T mysql mysql -uroot -proot_password stock_pool \
        -e "UPDATE users SET is_superuser=1 WHERE username='$username'; SELECT id, username, is_superuser FROM users WHERE username='$username';" 2>&1 \
        | grep -v "Warning.*password"
    log_success "完成（若 is_superuser=1 即提权成功）"
}

# CLI 备份数据库（不走 UI/权限），用于运维/灾难恢复场景
backup_db() {
    local output_file="${1:-aistock_backup_$(date +%Y-%m-%d_%H-%M-%S).sql}"
    log_info "备份 stock_pool 数据库到: $output_file"
    # --hex-blob: 二进制 BLOB 编码成十六进制，避免恢复时 mysql client 卡在二进制字节
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T mysql \
        mysqldump --hex-blob --single-transaction --routines --events --triggers \
        -uroot -proot_password stock_pool 2>/dev/null > "$output_file"
    local rc=$?
    if [ $rc -eq 0 ] && [ -s "$output_file" ]; then
        local size
        size=$(du -h "$output_file" | cut -f1)
        log_success "备份完成: $output_file ($size)"
    else
        log_error "备份失败（返回码 $rc）"
        rm -f "$output_file"
        return 1
    fi
}

# CLI 从 SQL 文件恢复数据库（绕过 UI，灾难恢复/登录不可用时使用）
restore_db() {
    local sql_file="${1:-}"
    local skip_confirm="${2:-}"
    if [ -z "$sql_file" ]; then
        log_error "用法: ./deploy.sh restore-db <sql文件路径> [--yes]"
        log_error "     加 --yes 跳过确认提示（谨慎使用）"
        return 1
    fi
    if [ ! -f "$sql_file" ]; then
        log_error "文件不存在: $sql_file"
        return 1
    fi

    local size
    size=$(du -h "$sql_file" | cut -f1)
    log_warning "============================================"
    log_warning "即将用 $sql_file ($size) 恢复到数据库 stock_pool"
    log_warning "当前数据库的全部数据将被覆盖，操作不可逆！"
    log_warning "============================================"

    if [ "$skip_confirm" != "--yes" ]; then
        printf "输入 YES 继续（其他任何输入都会取消）: "
        read -r confirm
        if [ "$confirm" != "YES" ]; then
            log_info "已取消"
            return 0
        fi
    fi

    log_info "开始恢复..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T mysql \
        mysql -uroot -proot_password stock_pool < "$sql_file"
    local rc=$?
    if [ $rc -eq 0 ]; then
        log_success "恢复完成"
    else
        log_error "恢复失败（返回码 $rc）"
        return 1
    fi
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
    echo "  build    构建所有镜像（总是执行）"
    echo "  build [服务]  构建指定服务镜像"
    echo "  smart-build  智能构建（前后端指纹独立判断，仅重建变更侧镜像）"
    echo "  cleanup      轻量清理：悬空镜像+超出10GB的旧构建缓存"
    echo "  deep-cleanup 深度清理：所有未被服务使用的镜像/卷/缓存"
    echo "  ps       查看服务状态"
    echo "  logs     查看后端日志"
    echo "  logs [服务]  查看指定服务日志"
    echo "  init-db  初始化数据库表"
    echo "  promote-admin <username>  把指定用户提升为管理员"
    echo "  backup-db [输出文件]      CLI 备份数据库（绕过 UI/权限）"
    echo "  restore-db <文件> [--yes] CLI 从 SQL 文件恢复（灾难恢复用，需确认）"
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
    smart-build)
        check_docker
        smart_build "$2"
        ;;
    cleanup)
        auto_cleanup
        ;;
    deep-cleanup)
        deep_cleanup
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
    promote-admin)
        promote_admin "$2"
        ;;
    backup-db)
        backup_db "$2"
        ;;
    restore-db)
        restore_db "$2" "$3"
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