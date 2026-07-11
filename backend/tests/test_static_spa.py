import httpx
from fastapi import FastAPI

from app.main import mount_frontend


def _app_with_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>botardo</html>")
    (dist / "assets" / "app.js").write_text("console.log('x')")
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    mount_frontend(app, dist)
    return app


async def test_spa_fallback_serves_index(tmp_path):
    app = _app_with_dist(tmp_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        # raíz y ruta de SPA sin extensión → index.html
        r = await c.get("/")
        assert r.status_code == 200 and "botardo" in r.text
        r = await c.get("/movimientos")
        assert r.status_code == 200 and "botardo" in r.text
        # asset real → contenido del archivo
        r = await c.get("/assets/app.js")
        assert r.status_code == 200 and "console" in r.text
        # rutas API registradas antes siguen ganando
        r = await c.get("/health")
        assert r.json() == {"status": "ok"}
        # path traversal no escapa de dist: cae al index
        r = await c.get("/..%2f..%2fetc%2fpasswd")
        assert r.status_code == 200 and "botardo" in r.text


async def test_mount_skips_missing_dist(tmp_path):
    app = FastAPI()
    mount_frontend(app, tmp_path / "no-existe")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        assert (await c.get("/")).status_code == 404  # solo API
