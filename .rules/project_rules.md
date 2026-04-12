# 项目规则

## 部署规则

### 重要：必须使用 deploy.sh 统一部署

- **所有代码更改后，必须使用** **`./deploy.sh build [backend|frontend]`** **构建镜像**
- **不要使用** **`docker-compose up -d --no-deps`** **来启动容器，这只会启动旧容器，不会重新构建**
- **正确流程**：
  1. 修改代码
  2. 运行 `./deploy.sh build backend` 或 `./deploy.sh build frontend`
  3. 运行 `docker-compose up -d` 启动新容器

### Docker容器状态检查

- 使用 `docker ps -a` 检查所有容器状态
- 使用 `docker-compose up -d` 启动所有服务

## 测试规则

### 端到端测试

- 使用 Playwright 进行真实浏览器测试
- 测试脚本放在 `frontend/tests/e2e/` 目录
- 运行命令：`cd frontend && node tests/e2e/xxx.cjs`

### API测试

- 后端API测试脚本放在 `backend/test_xxx.py`
- 可以通过 `docker exec stock_backend python /app/test_xxx.py` 运行

### 日志排查

- 后端日志：`docker exec stock_backend tail -f /app/logs/app.log`
- 前端日志：浏览器开发者工具 Console

