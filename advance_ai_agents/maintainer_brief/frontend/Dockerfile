# Maintainer Brief — frontend (Next.js). For self-host; on Vercel this is unused.
FROM node:20-slim AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
# NEXT_PUBLIC_* are baked at build time — pass the backend URL as a build arg.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm build

FROM node:20-slim AS run
WORKDIR /app
RUN corepack enable
ENV NODE_ENV=production
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["pnpm", "start", "--port", "3000"]
