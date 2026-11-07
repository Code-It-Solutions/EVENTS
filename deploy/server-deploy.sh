#!/usr/bin/env bash
# Runs ON the VPS as root after the source tarball is uploaded to /tmp/afrionex-events-src.tgz.
# Safe to re-run. Touches only /opt/afrionex-events, compose project "afrionex-events",
# /etc/nginx/conf.d/afrionex-events.conf, /var/www/afrionex-events-acme and that certificate.
set -euo pipefail
APP=/opt/afrionex-events
DOMAIN=events.afrionexsolutions.com
ACME=/var/www/afrionex-events-acme
CONF=/etc/nginx/conf.d/afrionex-events.conf

echo "== source"
mkdir -p "$APP"
find "$APP" -mindepth 1 -maxdepth 1 ! -name .env -exec rm -rf {} +
tar -xzf /tmp/afrionex-events-src.tgz -C "$APP"
rm -f /tmp/afrionex-events-src.tgz

echo "== secrets"
if [ ! -f "$APP/.env" ]; then
  ( umask 077; printf 'SECRET_KEY=%s\nOTP_REQUIRED_FOR_CHAIRS=false\n' "$(openssl rand -hex 32)" > "$APP/.env" )
fi
chmod 600 "$APP/.env"

echo "== build and start"
cd "$APP"
docker compose -p afrionex-events -f deploy/compose.prod.yaml up -d --build
code=000
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3130/login || true)
  [ "$code" = "200" ] && break; sleep 2
done
echo "app http: $code"; [ "$code" = "200" ] || { docker compose -p afrionex-events -f deploy/compose.prod.yaml logs --tail 40; exit 1; }

echo "== nginx + certificate"
install -d -m 755 "$ACME" && chmod -R a+rX "$ACME"
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
  cat > "$CONF" <<EOF
server {
    listen 178.162.240.53:80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ { root $ACME; }
    location / { return 503; }
}
EOF
  nginx -t && systemctl reload nginx
  certbot certonly --webroot -w "$ACME" -d "$DOMAIN" --non-interactive --agree-tos --keep-until-expiring
fi
cp deploy/nginx-afrionex-events.conf "$CONF"
if ! nginx -t; then
  echo "nginx test failed; removing new config so other sites are unaffected"
  rm -f "$CONF"; nginx -t && systemctl reload nginx; exit 1
fi
systemctl reload nginx

echo "== check"
curl -s -o /dev/null -w 'https: %{http_code}\n' "https://$DOMAIN/login"
