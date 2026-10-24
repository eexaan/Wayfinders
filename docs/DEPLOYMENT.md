# Deployment

**Pathways · static site · no backend**

Public URL: <https://wayfinders.shinorkon.com>

The app is a Vite/React bundle. It reads committed CSV and GeoJSON files at
runtime and makes no API calls, so deployment is copying one directory to a
static webroot and pointing nginx at it. There is no application server, no
database and no secret to configure.

---

## 1. What gets deployed

`web/dist/` contains everything:

| Path | Contents |
|---|---|
| `index.html` | The single entry point |
| `assets/` | Hashed JS, CSS and fonts (immutable) |
| `data/` | The frozen data contract, copied by `web/scripts/sync-data.mjs` |
| `sw.js` | Service worker: caches tiles and data, not the app bundle |
| `favicon.svg` | Favicon |

`web/vite.config.ts` sets `base: './'`, so the same build works at a domain
root or under a subpath.

---

## 2. Requirements

**To build:** Node 20 or newer. `npm ci` needs network access on the first run.

**To serve locally:** `python3` (for `http.server`).

**To deploy:** `rsync`, `ssh` access to the origin, and nginx on the origin.

The Python environment (`make setup`) is only needed for the data, figures and
GTFS pipeline — not for building or serving the dashboard.

---

## 3. Local

```bash
make serve
# open http://localhost:4444
```

`make serve` runs `make web` first, which is:

```bash
cd web && npm ci --silent && npm run build
```

then serves `web/dist` with `python3 -m http.server 4444`.

For repeat runs, skip the reinstall:

```bash
cd web && npm run build
cd dist && python3 -m http.server 4444
```

Live reload during UI work uses Vite directly, on its own port:

```bash
cd web && npm run dev     # http://localhost:5173
```

`make serve` is the production-shaped build; `npm run dev` is the fast loop.

### A note on a fixed bug

Until recently `make serve` failed on a fresh clone with
`cd: can't cd to web/dist`. The `web` target was not in `.PHONY`, and a real
`web/` directory exists, so make treated the prerequisite as an up-to-date file
and skipped the build. Both `web` and `serve` are now phony; `make serve` works
from a clean checkout.

---

## 4. Production

The origin runs nginx. It serves the static bundle from `/var/www/wayfinders`;
the app is **not** proxied to a running process.

```bash
make deploy HOST=root@<origin> DEST=/var/www/wayfinders
```

The target builds the bundle, creates the webroot, replaces its contents with
`rsync --delete`, then hands ownership to `www-data` (override with
`OWNER=user:group`) and sets 755/644 permissions.

The manual equivalent:

```bash
cd web && npm run build
rsync -a --delete web/dist/ root@<origin>:/var/www/wayfinders/
ssh root@<origin> \
  'chown -R www-data:www-data /var/www/wayfinders && \
   find /var/www/wayfinders -type d -exec chmod 755 {} + && \
   find /var/www/wayfinders -type f -exec chmod 644 {} +'
```

**Why `/var/www` and not the home directory?** The checkout lives under
`/root`, which is mode 700. nginx workers run as `www-data` and cannot traverse
it, so the built files are copied to a readable webroot.

**Why nginx and not Caddy?** Caddy is installed on the origin but not running;
nginx owns ports 80 and 443 for the other sites on the host. Adding a Caddy
site would have no effect, and stopping nginx to hand the ports over would take
those sites down.

---

## 5. nginx site

`/etc/nginx/sites-available/wayfinders`:

```nginx
server {
    listen 80;
    server_name wayfinders.shinorkon.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name wayfinders.shinorkon.com;

    ssl_certificate     /etc/nginx/ssl/celia.crt;
    ssl_certificate_key /etc/nginx/ssl/celia.key;

    root /var/www/wayfinders;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    }

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options "nosniff" always;
    }
}
```

Enable it once:

```bash
ln -s /etc/nginx/sites-available/wayfinders /etc/nginx/sites-enabled/wayfinders
nginx -t && systemctl reload nginx
```

An explicit `server_name` matters: requests for an unknown host on 443 fall
through to the first loaded vhost, which is how this domain once served another
site by mistake.

---

## 6. DNS and TLS

`wayfinders.shinorkon.com` is proxied by Cloudflare (responses carry `cf-ray`).
The origin certificate is self-signed and shared with the host's other vhosts.
That requires Cloudflare's SSL/TLS mode to be **Full**, not **Full (strict)**.

If the mode is ever changed to strict, issue a Cloudflare Origin Certificate
covering the hostname and point `ssl_certificate` at it; the self-signed cert
will otherwise fail validation.

Ports 80 and 443 must be open on the origin. Port 4444 is only for local
serving and is not part of production.

---

## 7. Verify a deployment

```bash
curl -s https://wayfinders.shinorkon.com | grep -o "<title>[^<]*</title>"
# <title>Pathways · Greater Malé bus supply tool</title>

curl -s https://wayfinders.shinorkon.com \
  | grep -o "assets/index-[^\"]*\.js" | head -1
# assets/index-<hash>.js

curl -s -o /dev/null -w "%{http_code}\n" \
  https://wayfinders.shinorkon.com/assets/index-<hash>.js
# 200

curl -s -o /dev/null -w "%{http_code}\n" \
  https://wayfinders.shinorkon.com/data/routes_master.csv
# 200
```

The asset hash must match the one in the build you just deployed. If it does
not, the webroot was not replaced, or Cloudflare is serving cached HTML.

From the origin, before Cloudflare is involved:

```bash
curl -k -s -H "Host: wayfinders.shinorkon.com" https://127.0.0.1 \
  | grep -o "<title>[^<]*</title>"
```

---

## 8. Rollback

The deployed artefact is whatever is in `web/dist`, so rolling back means
building an older commit and deploying it:

```bash
git switch --detach <good-commit>
make deploy HOST=root@<origin> DEST=/var/www/wayfinders
git switch main
```

To take the host offline without touching the webroot, remove the nginx
symlink and reload:

```bash
rm /etc/nginx/sites-enabled/wayfinders
nginx -t && systemctl reload nginx
```

---

## 9. Gotchas

- **`rsync --delete`** replaces the webroot contents. Anything placed there by
  hand will disappear on the next deploy.
- **Cloudflare** does not cache HTML by default, but it does cache hashed
  assets. A new index with new hashes is picked up immediately; purge the cache
  only if you have overridden the defaults.
- **Service worker**: `web/public/sw.js` caches tiles and data under versioned
  cache names (`wf-tiles-v3`, `wf-data-v3`). After a deploy, a hard reload is
  enough; the activate handler removes older caches.
- **`make deploy` rebuilds**: it depends on `web`, which runs `npm ci` every
  time. If dependencies are already installed, deploy with
  `cd web && npm run build && rsync …` to skip the reinstall.
- **No secrets live in the repo.** `HOST`, `DEST` and `OWNER` are passed on the
  command line, and the origin address is not committed.

---

## 10. File map

| File | Role |
|---|---|
| `Makefile` | `web` builds, `serve` runs locally on 4444, `deploy` ships the bundle |
| `web/vite.config.ts` | `base: './'` so the build is portable |
| `web/scripts/sync-data.mjs` | Copies `dashboard/data/` into the bundle before build |
| `web/public/sw.js` | Tile and data cache; never caches the app bundle |
| `docs/DASHBOARD_SPEC.md` | The data contract the bundle reads |
