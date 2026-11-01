# syntax=docker/dockerfile:1
FROM node:22-alpine AS deps
WORKDIR /srv/web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /srv/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /srv/web/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS prod
WORKDIR /srv/web
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Non-root. The standalone bundle needs nothing writable at runtime.
RUN addgroup -g 10001 -S tj && adduser -u 10001 -S tj -G tj

COPY --from=build --chown=tj:tj /srv/web/.next/standalone ./
COPY --from=build --chown=tj:tj /srv/web/.next/static ./.next/static
COPY --from=build --chown=tj:tj /srv/web/public ./public

USER tj
EXPOSE 3000
CMD ["node", "server.js"]
