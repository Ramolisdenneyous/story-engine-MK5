FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ARG VITE_API_BASE=http://localhost:8001
ARG VITE_TUTORIAL_VIDEO_URL=
ENV VITE_API_BASE=${VITE_API_BASE}
ENV VITE_TUTORIAL_VIDEO_URL=${VITE_TUTORIAL_VIDEO_URL}
RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY --from=build /app/dist ./dist
COPY --from=build /app/vite.config.ts ./vite.config.ts
EXPOSE 5173
CMD ["sh", "-c", "npm run preview -- --host 0.0.0.0 --port ${PORT:-5173}"]
