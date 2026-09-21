# ==========================================
# Stage 1: Build Frontend Assets
# ==========================================
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies with caching
COPY package*.json ./
RUN npm install

# Build production SPA bundle
COPY . .
RUN npm run build

# ==========================================
# Stage 2: Serve with Production Nginx
# ==========================================
FROM nginx:alpine

# Remove default configuration
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy compiled static assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
