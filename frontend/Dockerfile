# v0.2 Phase F — frontend Docker image (multi-stage). Node 20 build →
# nginx serve. FastAPI 백엔드 동결 정책 상 백엔드 컨테이너는 정적 파일을
# 서빙하지 않는다. 본 이미지가 dist/ 를 nginx 로 노출하고 /api 를 backend
# 컨테이너로 proxy 한다.

# ---------- build stage ----------
FROM node:20-alpine AS build
WORKDIR /app

# 의존성 캐시 레이어 분리
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# 소스 복사 후 정적 빌드
COPY . .
RUN npm run build

# ---------- runtime stage ----------
FROM nginx:1.27-alpine AS run
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
