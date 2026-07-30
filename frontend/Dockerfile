# FitCheck AI — frontend (TanStack Start / Vite SSR).
# Multi-stage: build with the full toolchain, then run a slim node server.
# VITE_API_BASE_URL is baked at build time, so pass it as a build-arg.
FROM node:20-slim AS build
WORKDIR /app
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
# TanStack Start (nitro) emits a self-contained server under .output/
COPY --from=build /app/.output ./.output
EXPOSE 3000
ENV PORT=3000
# nitro server entrypoint; adjust if your build outputs a different path
CMD ["node", ".output/server/index.mjs"]
