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
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


class LocalServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def test(site: Path, screenshots: Path, *, url_prefix: str = "/") -> dict:
    if not url_prefix.startswith("/") or not url_prefix.endswith("/"):
        raise ValueError("url_prefix must start and end with a slash")
    site = site.resolve()
    screenshots.mkdir(parents=True, exist_ok=True)
    if not (site / "simulator/manifest.json").is_file():
        raise FileNotFoundError("mjswan bundle missing")
    catalog = json.loads((site / "catalog.json").read_text(encoding="utf-8"))
    assert len(catalog["robots"]) >= 10
    assert (site / "studio.css").is_file()
    assert (site / "studio-minimal.css").is_file()
    assert (site / "studio.js").is_file()
    assert (site / "p37-evidence.json").is_file()
    demos = json.loads((site / "demo-catalog.json").read_text(encoding="utf-8"))
    assert len(demos["scenes"]) >= 3
    assert (site / "demos.css").is_file()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            requested = urlsplit(path).path
            if url_prefix != "/":
                if not requested.startswith(url_prefix):
                    return str(site / "__not_found__")
                requested = "/" + requested[len(url_prefix) :]
            return super().translate_path(requested)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site), **kwargs)

        def log_message(self, _fmt, *_args):
            pass

    server = LocalServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}{url_prefix}"
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
            page.locator("#scene-loading").wait_for(state="hidden", timeout=120000)
            assert page.locator("#robot-count").inner_text().startswith("10")

            # Skild-style task scenes are truly separate MuJoCo models.
            # Their collision objects, not pre-recorded motion, create the action.
            page.locator("#toggle-demos").click()
            assert page.locator("#demo-panel").get_attribute("aria-hidden") == "false"
            assert page.locator(".demo-entry").count() >= 3
            assert "One checkpoint. Two bodies." in page.locator("#demo-panel").inner_text()
            disclaimer = page.locator(".compare-disclaimer").inner_text().lower()
            assert "without a trained controller" in disclaimer
            page.locator("#close-demos").click()
            for demo_id in ("g1_impact_lab", "go2_contact_field", "franka_gravity_stack"):
                page.locator(f'[data-demo="{demo_id}"]').click()
                page.wait_for_function(
                    "(key) => new URL(document.querySelector('#sim').src)"
                    ".searchParams.get('scene') === key",
                    arg=demo_id,
                    timeout=60000,
                )
                page.locator("#scene-loading").wait_for(state="hidden", timeout=120000)
                assert not page.locator("#scene-fallback").is_visible()
                page.frame_locator("#sim").locator("canvas").first.wait_for(
                    state="visible", timeout=90000
                )
                assert "physics" in page.locator("#scene-badge").inner_text().lower()

            # The 3D scene, rather than either library/inspector sidebar,
            # occupies the full viewport on desktop.
            stage = page.locator("#scene-canvas").bounding_box()
            assert stage and stage["width"] >= 1400, "scene is still crowded by permanent panels"
            assert stage["height"] >= 700, "MuJoCo viewport collapsed vertically"
            sim_box = page.locator("#sim").bounding_box()
            assert sim_box and sim_box["height"] >= 700, "simulator iframe is vertically collapsed"
            page.frame_locator("#sim").locator("canvas").first.wait_for(
                state="visible", timeout=90000
            )
            assert page.locator("#scene-title").is_visible()
            assert page.locator("#reset").is_visible()
            page.wait_for_timeout(2200)
            assert page.locator("#robot-library-panel").get_attribute("aria-hidden") == "true"
            assert page.locator("#inspector").get_attribute("aria-hidden") == "true"
            page.screenshot(path=str(screenshots / "ui-desktop.png"), timeout=90000)

            # P37 research is visible only when explicitly requested.
            page.locator("#toggle-inspector").click()
            assert page.locator("#toggle-inspector").get_attribute("aria-expanded") == "true"
            page.locator("#tab-p37").click()
            assert "EXPERIMENTAL" in page.locator("#panel-p37").inner_text()
            page.locator(".trial-row").first.wait_for(state="visible", timeout=15000)
            assert "SEED 1000" in page.locator("#evidence-trials").inner_text()
            page.locator("#inspector").screenshot(
                path=str(screenshots / "ui-research.png"), timeout=60000
            )
            page.locator("#close-inspector").click()
            assert page.locator("#inspector").get_attribute("aria-hidden") == "true"

            # On-demand library, category filtering, and dismiss actions.
            page.locator("#toggle-library").click()
            assert page.locator("#robot-library-panel").get_attribute("aria-hidden") == "false"
            page.locator('[data-category="Quadrupeds"]').click()
            assert page.locator('[data-robot="unitree_g1"]').count() == 0
            page.locator('[data-category="All"]').click()
            page.locator("#robot-library-panel").screenshot(
                path=str(screenshots / "ui-library.png"), timeout=60000
            )
            page.locator("#close-library").click()
            assert page.locator("#robot-library-panel").get_attribute("aria-hidden") == "true"

            for key, expected in (
                ("unitree_g1", "Unitree G1"),
                ("unitree_go2", "Unitree Go2"),
                ("franka_panda", "Franka Panda"),
                ("boston_dynamics_spot", "Boston Dynamics Spot"),
                ("crazyflie_2", "Crazyflie 2"),
            ):
                page.locator("#toggle-library").click()
                page.locator(f'[data-robot="{key}"]').click()
                assert page.locator("#robot-library-panel").get_attribute("aria-hidden") == "true"
                page.wait_for_function(
                    "(key) => new URL(document.querySelector('#sim').src)"
                    ".searchParams.get('scene') === key",
                    arg=key,
                    timeout=60000,
                )
                assert expected in page.locator("#scene-title").inner_text()
                page.locator("#scene-loading").wait_for(state="hidden", timeout=120000)
                assert not page.locator("#scene-fallback").is_visible()
                frame = page.frame_locator("#sim")
                frame.locator("canvas").first.wait_for(state="visible", timeout=90000)
                box = frame.locator("canvas").first.bounding_box()
                assert box is not None and box["width"] >= 200 and box["height"] >= 150
                page.wait_for_timeout(1500)
                path = (
                    screenshots / f"{key}.png"
                    if key in ("unitree_g1", "boston_dynamics_spot")
                    else None
                )
                if path:
                    page.screenshot(path=str(path), timeout=90000)
                results.append(
                    {
                        "robot": key,
                        "canvas": True,
                        "screenshot": str(path) if path else None,
                    }
                )
                if key == "unitree_g1":
                    # Exercise actual pointer routing to the mjswan physics canvas.
                    # The native force test is responsible for quantitative physics proof.
                    x = box["x"] + box["width"] * 0.5
                    y = box["y"] + box["height"] * 0.5
                    page.mouse.move(x, y)
                    page.mouse.down()
                    page.mouse.move(x + 55, y + 25, steps=12)
                    page.mouse.up()
                    page.wait_for_timeout(600)
                    page.screenshot(
                        path=str(screenshots / "g1-pointer-interaction.png"),
                        timeout=90000,
                    )
            page.locator("#reset").click()
            page.frame_locator("#sim").locator("canvas").first.wait_for(
                state="visible", timeout=90000
            )
            # Mobile bottom-sheet layout must fit viewport without horizontal overflow.
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(350)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            scene_mobile = page.locator("#scene-canvas").bounding_box()
            assert scene_mobile and scene_mobile["width"] >= 385
            assert scene_mobile["height"] >= 650
            page.screenshot(path=str(screenshots / "ui-mobile.png"), timeout=90000)
            page.locator("#toggle-library").click()
            assert page.locator("#robot-library-panel").get_attribute("aria-hidden") == "false"
            page.wait_for_function(
                "() => document.querySelector('#robot-library-panel')"
                ".getBoundingClientRect().top < 280",
                timeout=15000,
            )
            gallery = page.locator("#robot-library-panel").bounding_box()
            assert gallery and gallery["width"] <= 391
            assert gallery["y"] < 300
            page.locator("#robot-library-panel").screenshot(
                path=str(screenshots / "ui-mobile-library.png"), timeout=60000
            )
            page.locator("#surface-scrim").click(position={"x": 380, "y": 25}, force=True)
            assert page.locator("#robot-library-panel").get_attribute("aria-hidden") == "true"

            if failures:
                raise AssertionError("Browser runtime errors: " + " | ".join(failures[:8]))
            if console_errors:
                raise AssertionError("Browser console errors: " + " | ".join(console_errors[:8]))
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
    parser.add_argument("--url-prefix", default="/")
    args = parser.parse_args()
    print(json.dumps(test(args.site, args.screenshots, url_prefix=args.url_prefix), indent=2))


if __name__ == "__main__":
    main()
