# Adagio

Private FIFA 2026 World Cup prediction game built with FastHTML and SQLite.

## Local Development

```bash
uv run python app.py
uv run pytest -q -s
```

The app runs on `http://localhost:5001` locally. Admin uses `ADMIN_PASSWORD`; if unset, the development default is `admin`.

## Railway Deployment

Railway can deploy this app directly from the repository. The app reads Railway's `PORT` variable and binds to `0.0.0.0`.

Required production variables:

```text
ADMIN_PASSWORD=<long private password>
APP_BASE_URL=https://<your Railway public domain>
```

Recommended persistent storage:

1. Add a Railway volume to the app service.
2. Mount it at `/data`.
3. Leave `DATABASE_URL` unset. The app will store SQLite at `/data/adagio.sqlite3`.

If you prefer an explicit path, set:

```text
DATABASE_URL=sqlite:////data/adagio.sqlite3
```

Deploy with:

```bash
railway up --detach -m "Deploy Adagio prediction game"
```

After deploy, set `APP_BASE_URL` to the public Railway domain so participant invite links are absolute.
