FROM nginx:stable-alpine

# 更换为阿里云国内源 (Alpine)
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 配置 nginx 支持 .mjs 文件
RUN echo "types { application/javascript js mjs; }" > /etc/nginx/conf.d/mjs.conf \
    && rm -rf /etc/nginx/conf.d/default.conf

# 复制 nginx 配置
COPY scripts/deploy/nginx.conf /etc/nginx/nginx.conf

# 构建产物通过 volumes 外挂，镜像内不包含
# docker-compose.yml 中已配置: ./web/apps/web-ele/dist:/usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]