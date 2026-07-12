# Maintainer Brief — frontend (Next.js). For self-host / Fly; on Vercel this is unused.
FROM node:22-slim AS build
WORKDIR /app
# Pin pnpm to the version that generated pnpm-lock.yaml (corepack's latest, 11.x,
# breaks on this Node with ERR_UNKNOWN_BUILTIN_MODULE).
RUN corepack enable && corepack prepare pnpm@10.23.0 --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
# NEXT_PUBLIC_* are baked at build time — pass the backend URL as a build arg.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm build

FROM node:22-slim AS run
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.23.0 --activate
ENV NODE_ENV=production
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["pnpm", "start", "--port", "3000"]
