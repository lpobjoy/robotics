# Builds the operator console (Vite + React). Vite env vars are baked
# in at build time, not read at container start -- VITE_EAM_URL and
# VITE_HTTP_API_URL are build args here, not runtime env vars, and have
# to be set to wherever eam/mcp_server are actually reachable from the
# browser (not from inside this container) at build time.
FROM node:20-slim AS build

WORKDIR /app
COPY console/package.json console/package-lock.json* ./
RUN npm install

COPY console/ ./

ARG VITE_EAM_URL=http://localhost:8000
ARG VITE_HTTP_API_URL=http://localhost:8001
ENV VITE_EAM_URL=${VITE_EAM_URL}
ENV VITE_HTTP_API_URL=${VITE_HTTP_API_URL}

RUN npm run build

FROM node:20-slim
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist

ENV PORT=5173
EXPOSE 5173

CMD ["sh", "-c", "serve -s dist -l ${PORT}"]
