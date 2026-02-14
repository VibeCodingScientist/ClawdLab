# ===========================================
# ClawdLab Frontend — Dockerfile
# Multi-stage: build with Node, serve with nginx
# ===========================================

# === BUILD ===
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build-time env: API calls go to /api (nginx proxies to backend)
ENV VITE_API_URL=/api
ENV VITE_MOCK_MODE=false

RUN npm run build

# === PRODUCTION ===
FROM nginx:1.27-alpine AS production

# Remove default nginx config
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy our nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
