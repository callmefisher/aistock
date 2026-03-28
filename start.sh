#!/bin/bash

echo "========================================="
echo "选股池自动化系统 - 启动脚本"
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
echo "  前端界面: http://localhost"
echo "  API文档:  http://localhost/docs"
echo "  API地址:  http://localhost/api/v1"
echo ""
echo "查看日志："
echo "  docker-compose logs -f backend"
echo ""
echo "停止服务："
echo "  docker-compose down"
echo ""
echo "========================================="
