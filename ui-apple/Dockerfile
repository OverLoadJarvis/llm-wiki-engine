FROM node:20-alpine AS builder

WORKDIR /app

RUN npm config set registry https://registry.npmmirror.com && \
    npm config set fetch-timeout 600000 && \
    npm config set fetch-retry-maxtimeout 600000 && \
    npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retries 5

COPY package.json package-lock.json ./
RUN npm ci --prefer-offline --no-audit --no-fund

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
