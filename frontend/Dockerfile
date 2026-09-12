# frontend/Dockerfile
# Multi-stage build. docker-compose.yml uses the `dev` target for local
# development (hot reload via bind mount); use the default final stage
# (`runner`) for production deployments.

FROM node:20-alpine AS base
WORKDIR /app
COPY package.json package-lock.json* ./

# ─── Dev target (used by docker-compose.yml) ───────────────────────────────
FROM base AS dev
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ─── Production build ───────────────────────────────────────────────────────
FROM base AS deps
RUN npm ci

FROM deps AS builder
WORKDIR /app
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
