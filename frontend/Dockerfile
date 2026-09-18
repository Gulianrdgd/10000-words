FROM denoland/deno:2.9.6 AS build

WORKDIR /srv

# dependencies first, so source edits don't invalidate the layer
COPY package.json deno.lock ./
RUN deno install --allow-scripts

COPY . .
RUN deno task build

FROM nginx:1.27-alpine
COPY --from=build /srv/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
