"""End-to-end Chromium smoke test for built P37 MuJoCo browser bundle.

Runs against a built _site directory, asserts scenes render a canvas,
selector switches real models, reset reloads. Captures screenshots.
Requires playwright + a Chromium install (GitHub Actions workflow provides it).
"""
from __future__ import annotations

import argparse
import contextlib
import http.server
import json
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright


class LocalServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def test(site: Path, screenshots: Path) -> dict:
    site = site.resolve()
    screenshots.mkdir(parents=True, exist_ok=True)
    if not (site / "simulator/manifest.json").is_file():
        raise FileNotFoundError("mjswan bundle missing")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site), **kwargs)

        def log_message(self, _fmt, *_args):
            pass

    server = LocalServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    results = []
    failures = []
    console_errors = []
    with contextlib.ExitStack() as stack:
        stack.callback(server.server_close)
        stack.callback(server.shutdown)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--enable-unsafe-swiftshader",
                    "--use-gl=angle",
                    "--use-angle=swiftshader",
                ],
            )
            page = browser.new_page(viewport={"width": 1500, "height": 980})
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.on(
                "response",
                lambda response: (
                    failures.append(f"HTTP {response.status}: {response.url}")
                    if response.status >= 400
                    else None
                ),
            )
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text) if message.type == "error" else None
                ),
            )
            response = page.goto(origin, wait_until="domcontentloaded", timeout=30000)
            assert response is not None and response.status == 200
            assert "P37 Brain Lab" in page.title()
            page.locator("#fallback.show").wait_for(state="detached", timeout=45000)

            for key, expected in (
                ("g1", "Unitree G1"),
                ("go2", "Unitree Go2"),
                ("franka", "Franka Panda"),
            ):
                page.locator(f'[data-robot="{key}"]').click()
                page.wait_for_function(
                    "(key) => document.querySelector('#sim').src.includes('scene=' + key)",
                    arg={"g1": "unitree_g1", "go2": "unitree_go2", "franka": "franka_panda"}[key],
                    timeout=10000,
                )
                assert expected in page.locator("#viewer-label").inner_text()
                frame = page.frame_locator("#sim")
                frame.locator("canvas").first.wait_for(state="visible", timeout=60000)
                box = frame.locator("canvas").first.bounding_box()
                assert box is not None and box["width"] >= 200 and box["height"] >= 150
                page.wait_for_timeout(1500)
                path = screenshots / f"{key}.png"
                page.screenshot(path=str(path))
                results.append({"robot": key, "canvas": True, "screenshot": str(path)})
            page.locator("#reset").click()
            page.frame_locator("#sim").locator("canvas").first.wait_for(
                state="visible", timeout=60000
            )
            if failures:
                raise AssertionError("Browser runtime errors: " + " | ".join(failures[:8]))
            browser.close()
    result = {
        "status": "pass",
        "screenshots": results,
        "browser_exceptions": failures,
        "console_errors": console_errors,
        "note": "Canvas rendering and scene switching; trained P37 inference is not tested.",
    }
    (screenshots / "browser-results.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=Path("_site"))
    parser.add_argument("--screenshots", type=Path, default=Path("_screenshots"))
    args = parser.parse_args()
    print(json.dumps(test(args.site, args.screenshots), indent=2))


if __name__ == "__main__":
    main()
