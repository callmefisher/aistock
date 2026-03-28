#!/bin/bash

echo "========================================="
echo "选股池自动化系统 - 智能启动脚本"
echo "========================================="
echo ""

if ! command -v docker &> /dev/null; then
    echo "错误: Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "错误: Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

if [ ! -f .env ]; then
    echo "创建.env文件..."
    cp .env.example .env
    echo "请编辑.env文件，配置必要的参数"
    echo ""
fi

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

echo "检测端口占用情况..."
echo ""

FRONTEND_PORT=80
BACKEND_PORT=8000
MYSQL_PORT=3306
REDIS_PORT=6379
SELENIUM_PORT=4444
SELENIUM_VNC_PORT=7900

if ! check_port $FRONTEND_PORT; then
    echo "⚠️  端口 $FRONTEND_PORT 已被占用"
    FRONTEND_PORT=$(find_available_port 8080)
    if [ -z "$FRONTEND_PORT" ]; then
        echo "错误: 无法找到可用的前端端口"
        exit 1
    fi
    echo "✓ 自动切换到端口: $FRONTEND_PORT"
fi

if ! check_port $BACKEND_PORT; then
    echo "⚠️  端口 $BACKEND_PORT 已被占用"
    BACKEND_PORT=$(find_available_port 8001)
    if [ -z "$BACKEND_PORT" ]; then
        echo "错误: 无法找到可用的后端端口"
        exit 1
    fi
    echo "✓ 自动切换到端口: $BACKEND_PORT"
fi

if ! check_port $MYSQL_PORT; then
    echo "⚠️  端口 $MYSQL_PORT 已被占用"
    MYSQL_PORT=$(find_available_port 3307)
    if [ -z "$MYSQL_PORT" ]; then
        echo "错误: 无法找到可用的MySQL端口"
        exit 1
    fi
    echo "✓ 自动切换到端口: $MYSQL_PORT"
fi

if ! check_port $REDIS_PORT; then
    echo "⚠️  端口 $REDIS_PORT 已被占用"
    REDIS_PORT=$(find_available_port 6380)
    if [ -z "$REDIS_PORT" ]; then
        echo "错误: 无法找到可用的Redis端口"
        exit 1
    fi
    echo "✓ 自动切换到端口: $REDIS_PORT"
fi

if ! check_port $SELENIUM_PORT; then
    echo "⚠️  端口 $SELENIUM_PORT 已被占用"
    SELENIUM_PORT=$(find_available_port 4445)
    if [ -z "$SELENIUM_PORT" ]; then
        echo "错误: 无法找到可用的Selenium端口"
        exit 1
    fi
    echo "✓ 自动切换到端口: $SELENIUM_PORT"
fi

if ! check_port $SELENIUM_VNC_PORT; then
    echo "⚠️  端口 $SELENIUM_VNC_PORT 已被占用"
    SELENIUM_VNC_PORT=$(find_available_port 7901)
    if [ -z "$SELENIUM_VNC_PORT" ]; then
        echo "错误: 无法找到可用的Selenium VNC端口"
        exit 1
    fi
    echo "✓ 自动切换到端口: $SELENIUM_VNC_PORT"
fi

echo ""
echo "端口配置完成："
echo "  前端: $FRONTEND_PORT"
echo "  后端: $BACKEND_PORT"
echo "  MySQL: $MYSQL_PORT"
echo "  Redis: $REDIS_PORT"
echo "  Selenium: $SELENIUM_PORT"
echo "  Selenium VNC: $SELENIUM_VNC_PORT"
echo ""

cat > docker-compose.override.yml <<EOF
version: '3.8'

services:
  mysql:
    ports:
      - "$MYSQL_PORT:3306"
  
  redis:
    ports:
      - "$REDIS_PORT:6379"
  
  selenium:
    ports:
      - "$SELENIUM_PORT:4444"
      - "$SELENIUM_VNC_PORT:7900"
  
  backend:
    ports:
      - "$BACKEND_PORT:8000"
    environment:
      - SELENIUM_URL=http://selenium:4444/wd/hub
  
  frontend:
    ports:
      - "$FRONTEND_PORT:80"
EOF

echo "停止现有容器..."
docker-compose down

echo ""
echo "构建Docker镜像..."
docker-compose build

echo ""
echo "启动服务..."
docker-compose up -d

echo ""
echo "等待服务启动..."
sleep 10

echo ""
echo "========================================="
echo "服务启动完成！"
echo "========================================="
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
echo "Selenium服务："
echo "  WebDriver: http://localhost:$SELENIUM_PORT"
echo "  VNC查看: http://localhost:$SELENIUM_VNC_PORT"
echo ""
echo "查看日志："
echo "  docker-compose logs -f backend"
echo ""
echo "停止服务："
echo "  docker-compose down"
echo ""
echo "========================================="

echo ""
echo "端口配置已保存到 docker-compose.override.yml"
echo "下次启动将使用相同端口配置"
