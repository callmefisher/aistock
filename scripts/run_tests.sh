#!/bin/bash

set -e

echo "========================================="
echo "选股池自动化系统 - 测试运行脚本"
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

run_backend_tests() {
    log_info "运行后端测试..."
    cd backend

    if [ ! -d "venv" ]; then
        log_info "创建Python虚拟环境..."
        python3 -m venv venv
    fi

    source venv/bin/activate
    pip install -q -r requirements.txt

    log_info "运行单元测试..."
    pytest tests/test_auth.py tests/test_rule_engine_unit.py -v

    log_info "运行集成测试..."
    pytest tests/test_data_sources.py tests/test_rules.py tests/test_tasks.py -v

    log_info "运行回归测试..."
    pytest tests/test_regression.py -v

    deactivate
    cd ..

    log_success "后端测试完成"
}

run_frontend_tests() {
    log_info "运行前端测试..."
    cd frontend

    if [ ! -d "node_modules" ]; then
        log_info "安装Node依赖..."
        npm install
    fi

    log_info "运行单元测试..."
    npm run test:unit

    log_info "运行集成测试..."
    npm run test:integration

    cd ..

    log_success "前端测试完成"
}

show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项："
    echo "  backend    运行后端测试"
    echo "  frontend   运行前端测试"
    echo "  all        运行所有测试"
    echo "  help       显示帮助信息"
}

case "${1:-all}" in
    backend)
        run_backend_tests
        ;;
    frontend)
        run_frontend_tests
        ;;
    all)
        run_backend_tests
        echo ""
        run_frontend_tests
        ;;
    help)
        show_help
        ;;
    *)
        log_error "未知选项: $1"
        show_help
        exit 1
        ;;
esac

echo ""
log_success "测试执行完成!"
