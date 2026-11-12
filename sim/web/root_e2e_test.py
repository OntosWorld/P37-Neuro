"""Check the canonical P37-Neuro root build and its live workcell controls.

This GitHub Pages smoke test checks the publish layout even on CI machines
without hardware WebGPU. Dedicated Apple Metal GPU tests still qualify solver
behavior and contact separately.
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import threading
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


class LocalServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def test(site: Path, screenshots: Path, *, url_prefix: str = "/P37-Neuro/") -> dict:
    site = site.resolve()
    screenshots.mkdir(parents=True, exist_ok=True)
    assert (site / "index.html").is_file(), "single live root missing"
    assert (site / "robots/compact.urdf").is_file(), "reference physics robot absent"
    assert (site / "robots/extended.urdf").is_file(), "extended body absent"
    metadata = json.loads((site / "build-info.json").read_text(encoding="utf-8"))
    assert metadata["site_entry"] == "/P37-Neuro/"
    assert metadata["trained_p37_policy_attached"] is False
    for old_route in ("lab", "demos", "test"):
        assert not (site / old_route).exists(), f"obsolete public navigation directory: {old_route}"
    assert (site / "simulator/manifest.json").is_file(), "MuJoCo runtime bundle missing"
    catalog = json.loads((site / "catalog.json").read_text(encoding="utf-8"))
    assert len(catalog["robots"]) == 10, "ten manufacturer-derived bodies required"
    manifest = json.loads((site / "simulator/manifest.json").read_text(encoding="utf-8"))
    scenes = {item["id"] for p in manifest["projects"] for item in p["scenes"]}
    assert {robot["id"] for robot in catalog["robots"]} <= scenes
    assert not (site / "studio.js").exists(), "old landing page is still published"

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            requested = urlsplit(path).path
            if not requested.startswith(url_prefix):
                return str(site / "__not_found__")
            return super().translate_path("/" + requested[len(url_prefix):])

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site), **kwargs)

        def log_message(self, *_args):
            pass

    server = LocalServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    origin = f"http://127.0.0.1:{server.server_port}{url_prefix}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=[
                "--no-sandbox", "--disable-dev-shm-usage",
                "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
            ])
            page = browser.new_page(viewport={"width": 1512, "height": 982})
            response = page.goto(origin, wait_until="domcontentloaded", timeout=45000)
            assert response is not None and response.status == 200
            assert "P37-Neuro" in page.title()
            page.get_by_role("heading", name="Robots, interacting with the world.").wait_for(
                timeout=35000
            )
            assert page.locator(".canvas-wrap").count() == 1
            assert page.get_by_role("button", name="Pause robot task").is_visible()
            assert page.get_by_role("button", name="Close fingers").is_visible()
            assert page.get_by_role("button", name="Run gravity & contact test").is_visible()
            assert page.locator(".playground-scenes button").count() == 3
            assert page.locator(".playground-embodiment button").count() == 2
            page.locator(".catalog-choices button").first.wait_for(timeout=15000)
            assert page.locator(".catalog-choices button").count() == 10
            assert page.locator('a[href^="../"]').count() == 0, "old route still linked"
            stage = page.locator(".canvas-wrap").bounding_box()
            assert stage is not None and stage["height"] >= 450
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
            page.screenshot(path=str(screenshots / "root-desktop.png"), timeout=60000)
            # Selecting a real Panda stays on the same URL, uses actual native
            # MuJoCo physics and never changes the top-level navigation.
            page.get_by_role("button", name="Franka Panda").click()
            assert page.locator("iframe.menagerie-viewer").count() == 1
            src = page.locator("iframe.menagerie-viewer").get_attribute("src")
            assert src and "scene=franka_panda" in src
            assert page.url == origin, "robot selection must not create new public URL"
            assert page.request.get(origin + "simulator/manifest.json").status == 200
            page.get_by_role("combobox", name="Robot embodiment").select_option("unitree_g1")
            assert "scene=unitree_g1" in page.locator(
                "iframe.menagerie-viewer"
            ).get_attribute("src")
            page.get_by_role("combobox", name="Robot embodiment").select_option("compact")
            assert page.locator("iframe.menagerie-viewer").count() == 0
            page.get_by_role("button", name="Pause robot task").click()
            assert page.get_by_role("button", name="Run robot task").is_visible()
            page.get_by_role("button", name="Run robot task").click()
            assert page.get_by_role("button", name="Pause robot task").is_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(400)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
            assert page.locator(".canvas-wrap").bounding_box()["height"] >= 410
            page.screenshot(path=str(screenshots / "root-mobile.png"), timeout=60000)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    return {"single_root": True, "default_task_running": True,
            "controls_available": True, "mobile_checked": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url-prefix", default="/P37-Neuro/")
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(test(args.site, args.screenshots, url_prefix=args.url_prefix), indent=2))


if __name__ == "__main__":
    main()
