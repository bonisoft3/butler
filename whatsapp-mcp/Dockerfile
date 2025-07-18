FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# for arm64 support we need to install chromium provided by debian
# npm ERR! The chromium binary is not available for arm64.
# https://github.com/puppeteer/puppeteer/issues/7740

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

RUN apt-get update && \
    apt-get install -y wget gnupg curl && \
    apt-get install -y fonts-ipafont-gothic fonts-wqy-zenhei fonts-thai-tlwg fonts-kacst fonts-freefont-ttf libxss1 \
    libgtk2.0-0 libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2 && \
    apt-get install -y chromium && \
    apt-get clean

WORKDIR /project

COPY package*.json tsconfig.json ./
COPY src/ ./src/

RUN npm install
RUN npm run build

ENV DOCKER_CONTAINER=true

RUN mkdir -p /session-data

COPY ./scripts/webhook.production.json /project/session-data/webhook.production.json

RUN chown -R node:node /project/session-data

EXPOSE 3001

ENTRYPOINT ["node", "dist/main.js"]

# docker run -it --entr
