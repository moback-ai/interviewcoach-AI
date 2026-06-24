FROM node:24-alpine AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps --no-audit

COPY frontend/ .
ARG VITE_API_BASE_URL=/api
ARG VITE_STORAGE_URL=/storage
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_STORAGE_URL=$VITE_STORAGE_URL
RUN npm run build

FROM nginx:1.27-alpine

COPY docker/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
