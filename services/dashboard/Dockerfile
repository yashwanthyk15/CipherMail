# Stage 1: Build React app
FROM node:20-alpine as builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm install tailwindcss@3 postcss autoprefixer
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy nginx config
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Copy built app
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx master runs as root and drops to nginx user automatically

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
