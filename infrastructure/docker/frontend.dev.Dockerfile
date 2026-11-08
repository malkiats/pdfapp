# syntax=docker/dockerfile:1.10
#
# Local-development image for the optional `frontend` compose profile only.
# Production frontend is built and served by Vercel (infrastructure/deployment).
# Source is bind-mounted at runtime; this image only prepares writable, node-owned
# mount points so named volumes for node_modules/.next inherit the right owner.
FROM node:26.12.1-alpine@sha256:40cd011b55415bc894e45b02fdd5a5dfde056921b7d23a64c74f80497af48797

ENV NEXT_TELEMETRY_DISABLED=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false

RUN mkdir -p /srv/frontend/node_modules /srv/frontend/.next /srv/shared \
 && chown -R node:node /srv/frontend

WORKDIR /srv/frontend
USER 1000:1000
EXPOSE 3000
CMD ["sh", "-c", "npm ci --no-audit --no-fund && exec npm run dev -- --hostname 0.0.0.0 --port 3000"]
