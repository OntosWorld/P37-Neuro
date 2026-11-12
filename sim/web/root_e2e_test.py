"""Canonical P37 homepage end-to-end test: real models and ONNX scenes only."""
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
    assert (site / "index.html").is_file()
    assert not (site / "robots").exists(), "procedural reference meshes leaked to public site"
    assert not (site / "vendor").exists(), "obsolete Steel Panda importer leaked to site"
    meta = json.loads((site / "build-info.json").read_text(encoding="utf-8"))
    assert meta["site_entry"] == "/P37-Neuro/"
    assert meta["trained_p37_policy_attached"] is True
    assert meta["qualified_cross_body_transfer"] is False
    assert set(meta["active_policy_robots"]) == {"unitree_g1", "unitree_go2"}
    assert len(meta["onnx_sha256"]) == 64
    catalog = json.loads((site / "catalog.json").read_text(encoding="utf-8"))
    assert len(catalog["robots"]) == 10
    manifest = json.loads((site / "simulator/manifest.json").read_text(encoding="utf-8"))
    scenes = {scene["id"]: scene for project in manifest["projects"] for scene in project["scenes"]}
    assert {item["id"] for item in catalog["robots"]} <= set(scenes)
    for body in meta["active_policy_robots"]:
        entry = scenes[body + "_p37_experimental"]
        assert any(
            policy["id"] == "p37_experimental_recurrent_ppo"
            for policy in entry["policies"]
        )
    assert not (site / "lab").exists()
    assert not (site / "demos").exists()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            requested = urlsplit(path).path
            if not requested.startswith(url_prefix):
                return str(site / "__not_found__")
            return super().translate_path("/" + requested[len(url_prefix) :])

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
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--enable-unsafe-swiftshader",
                    "--use-angle=swiftshader",
                ],
            )
            page = browser.new_page(viewport={"width": 1512, "height": 982})
            policy_network_responses = []
            page.on(
                "response",
                lambda response: policy_network_responses.append(
                    {"url": response.url, "status": response.status}
                )
                if "/policy/" in response.url or response.url.endswith(".onnx")
                else None,
            )
            response = page.goto(origin, wait_until="domcontentloaded", timeout=60000)
            assert response is not None and response.status == 200
            page.get_by_role(
                "heading", name="One intelligence. Different robot bodies."
            ).wait_for(timeout=30000)
            page.locator(".robot-options .robot-option").first.wait_for(timeout=20000)
            assert page.locator(".robot-options .robot-option").count() == 10
            assert page.locator("iframe.real-robot-frame").count() == 1
            assert "scene=unitree_g1_p37_experimental" in page.locator(
                "iframe.real-robot-frame"
            ).get_attribute("src")
            assert "policy=p37_experimental_recurrent_ppo" in page.locator(
                "iframe.real-robot-frame"
            ).get_attribute("src")
            page.wait_for_function(
                "() => document.querySelector('iframe.real-robot-frame')"
                "?.contentWindow?.__mjswanReady === true",
                timeout=150000,
            )
            # Actual rendering + policy resource load: not a decorative mesh.
            page.frame_locator("iframe.real-robot-frame").locator("canvas").first.wait_for(
                state="visible", timeout=20000
            )
            page.screenshot(path=str(screenshots / "g1-live-p37-desktop.png"), timeout=90000)
            assert page.get_by_role("button", name="Run P37 experimental").get_attribute(
                "aria-pressed"
            ) == "true"
            page.get_by_role("button", name="Model only").click()
            assert "scene=unitree_g1&" in page.locator(
                "iframe.real-robot-frame"
            ).get_attribute("src")
            page.get_by_role("button", name="Unitree Go2").click()
            assert "scene=unitree_go2_p37_experimental" in page.locator(
                "iframe.real-robot-frame"
            ).get_attribute("src")
            page.get_by_role("button", name="Franka Panda").click()
            assert "scene=franka_panda&" in page.locator(
                "iframe.real-robot-frame"
            ).get_attribute("src")
            assert page.get_by_role("button", name="Run P37 experimental").is_disabled()
            assert page.url == origin, "robot choice changed the public URL"
            page.screenshot(path=str(screenshots / "panda-real-geometry.png"), timeout=90000)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(400)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
            page.screenshot(path=str(screenshots / "p37-real-robots-mobile.png"), timeout=90000)
            assert page.locator(".real-robot-frame").count() == 1
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    return {
        "root": True,
        "real_bodies": len(catalog["robots"]),
        "live_policy_bodies": meta["active_policy_robots"],
        "no_procedural_meshes": True,
        "mobile": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--url-prefix", default="/P37-Neuro/")
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(test(args.site, args.screenshots, url_prefix=args.url_prefix), indent=2))


if __name__ == "__main__":
    main()
