# TJ web

The Next.js front end. See the [repository README](../../README.md) for setup
and [docs/MANUAL.md](../../docs/MANUAL.md) for using the app.

```bash
npm install
npm run dev     # expects the API on http://localhost:8000
npm run build
npm run lint
```

`/api/*` is rewritten to the API container (see `next.config.ts`), which keeps
the session cookie same-origin and mirrors the Caddy setup in production.

Before writing any UI, read [docs/DESIGN.md](../../docs/DESIGN.md). It is the
design system and it wins over anything that contradicts it. Every number on
screen goes through `lib/format.ts`.
