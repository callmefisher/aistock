# 前端构建阶段
FROM node:18-alpine as builder

WORKDIR /app

# npm 切换 npmmirror 国内源，避免直连 npmjs.org 依赖 VPN
RUN npm config set registry https://registry.npmmirror.com

# 复制package文件
COPY package*.json ./

# 安装依赖(包括开发依赖，用于构建)
# cache mount 缓存包下载: package 变更时仅增量联网，重复构建直接走本地缓存
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# 生产阶段 - 使用Nginx
FROM nginx:alpine

# 复制构建产物到Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制Nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动Nginx
CMD ["nginx", "-g", "daemon off;"]
