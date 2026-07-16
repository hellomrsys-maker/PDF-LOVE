# Unprivileged nginx: runs as a non-root user and listens on 8080,
# so the container needs no capabilities at all.
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY index.html /usr/share/nginx/html/index.html
COPY manifest.json /usr/share/nginx/html/manifest.json
COPY sw.js /usr/share/nginx/html/sw.js
COPY vendor/ /usr/share/nginx/html/vendor/
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
