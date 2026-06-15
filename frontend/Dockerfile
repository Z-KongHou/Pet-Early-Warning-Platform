FROM node:20-alpine

WORKDIR /app

# Build-time arg for Next.js rewrites (server-side proxy to AI service)
ARG AI_SERVICE_URL=http://ai:8000
ENV AI_SERVICE_URL=${AI_SERVICE_URL}

# Dependencies layer (cached)
COPY package.json package-lock.json* ./
RUN npm ci --only=production 2>/dev/null || npm install

# App code
COPY . .

# Build Next.js
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
