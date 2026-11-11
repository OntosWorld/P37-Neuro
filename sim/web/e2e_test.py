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
    assert (site / "steel-playground.css").is_file()
    assert (site / "steel-site-shell.css").is_file()
    assert (site / "studio.js").is_file()
    assert (site / "p37-evidence.json").is_file()
    assert (site / "demos/index.html").is_file()
    assert (site / "demos/evidence.json").is_file()
    assert (site / "lab/index.html").is_file()
    assert (site / "lab/steel/index.html").is_file()
    assert (site / "lab/compare/samples/mimicgen-square-source.json").is_file()

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
            assert "playground-brain" in page.locator("body").get_attribute("class")
            assert page.locator("#toggle-library").is_visible()
            bg = page.locator(".app-header").evaluate(
                "(node) => getComputedStyle(node).backgroundColor"
            )
            assert bg == "rgb(255, 255, 255)", f"unexpected Skild-style header: {bg}"
            page.locator("#scene-loading").wait_for(state="hidden", timeout=120000)
            assert page.locator("#robot-count").inner_text().startswith("10")

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

            # P37 demos are separate from the physics viewer. Verify their
            # actual MuJoCo canvas, measured native evidence and UI controls.
            demo = page.goto(origin + "demos/", wait_until="domcontentloaded", timeout=30000)
            assert demo is not None and demo.status == 200
            assert "Robotics Demos" in page.title()
            assert "playground-demos" in page.locator("body").get_attribute("class")
            assert page.locator(".scene-menu").is_visible()
            page.locator("#stage-loading").wait_for(state="hidden", timeout=120000)
            page.frame_locator("#stage-frame").locator("canvas").first.wait_for(
                state="visible", timeout=120000
            )
            assert page.locator(".force-row").count() == 2
            assert page.locator(".p37-trial-row").count() == 3
            assert page.locator("#cross-g1-actions").inner_text() == "29"
            assert page.locator("#cross-go2-actions").inner_text() == "12"
            assert page.locator("#cross-retraining").inner_text() == "None"
            assert "Unitree G1" in page.locator("#stage-title").inner_text()
            assert page.frame_locator("#stage-frame").locator("canvas").first.is_visible()
            assert (
                page.frame_locator("#stage-frame")
                .locator("body")
                .evaluate("(node) => node.ownerDocument.defaultView.__mjswanReady === true")
            ), "main demo was captured before native MuJoCo reported a stable frame"
            assert "not yet verified" in page.locator(".cross-claim").inner_text().lower()
            page.set_viewport_size({"width": 1440, "height": 900})
            page.screenshot(path=str(screenshots / "demos-desktop.png"), timeout=90000)
            page.locator(".sim-layout").screenshot(
                path=str(screenshots / "demos-live-robot.png"), timeout=90000
            )
            page.locator('[data-scene="unitree_go2"]').click()
            page.wait_for_function(
                "() => new URL(document.querySelector('#stage-frame').src)"
                ".searchParams.get('scene') === 'unitree_go2'",
                timeout=30000,
            )
            page.locator("#stage-loading").wait_for(state="hidden", timeout=120000)
            page.frame_locator("#stage-frame").locator("canvas").first.wait_for(
                state="visible", timeout=120000
            )
            assert "Unitree Go2" in page.locator("#stage-title").inner_text()
            page.locator("#compare-run").click()
            assert not page.locator("#compare-stop").is_disabled()
            assert page.locator("#compare-frame-a").get_attribute("src").startswith("../simulator/")
            assert page.locator("#compare-frame-b").get_attribute("src").startswith("../simulator/")
            assert "ACTUATORS" in page.locator("#body-stats-a").inner_text()
            assert "ACTUATORS" in page.locator("#body-stats-b").inner_text()
            page.frame_locator("#compare-frame-a").locator("canvas").first.wait_for(
                state="visible", timeout=120000
            )
            page.frame_locator("#compare-frame-b").locator("canvas").first.wait_for(
                state="visible", timeout=120000
            )
            page.locator("#compare-idle-a").wait_for(state="hidden", timeout=120000)
            page.locator("#compare-idle-b").wait_for(state="hidden", timeout=120000)
            for key in ("a", "b"):
                assert (
                    page.frame_locator(f"#compare-frame-{key}")
                    .locator("body")
                    .evaluate("(node) => node.ownerDocument.defaultView.__mjswanReady === true")
                ), f"body {key} is not physically loaded"
            page.locator(".compare-grid").screenshot(
                path=str(screenshots / "demos-two-bodies.png"), timeout=90000
            )
            page.locator("#compare-stop").click()
            assert page.locator("#compare-stop").is_disabled()
            page.set_viewport_size({"width": 390, "height": 844})
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(300)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            page.screenshot(path=str(screenshots / "demos-mobile.png"), timeout=90000)

            # Release GPU-heavy MuJoCo iframes before checking standalone HTML demos.
            # The five manufacturer scenes + two comparison canvases can exhaust
            # Chromium's SwiftShader budget and stall unrelated navigation.
            page.close()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
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

            # The new evidence pages are additive and must work at the same Pages prefix.
            assert page.request.get(origin + "lab/steel/").status == 200
            original = page.request.get(origin + "lab/compare/samples/mimicgen-square-source.json")
            assert original.status == 200
            source = original.json()
            assert source["publication"]["source"] == "amandlek/mimicgen_datasets"
            assert source["publication"]["learned_policy_attached"] is False
            assert len(source["traces"]) == 2
            response = page.goto(
                origin + "lab/compare/?sample=mimicgen",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            assert response is not None and response.status == 200
            page.locator(".card").first.wait_for(state="visible", timeout=30000)
            assert page.locator(".card").count() == 2
            assert (
                "Original data: amandlek/mimicgen_datasets"
                in page.locator("#sourceCredit").inner_text()
            )
            page.screenshot(path=str(screenshots / "mimicgen-real-data.png"), timeout=30000)

            assert "playground-evidence" in page.locator("body").get_attribute("class")
            assert page.locator("#mimicgen").is_visible()
            replay_bg = page.locator("body").evaluate(
                "(node) => getComputedStyle(node).backgroundColor"
            )
            assert replay_bg == "rgb(255, 255, 255)"
            # Explore both lightweight research interfaces in fresh pages.
            for route, expected_class, expected_control in (
                ("lab/", "playground-architecture", "[data-task='reach']"),
                ("lab/sim/", "playground-kinematics", "[data-robot='compact']"),
            ):
                response = page.goto(
                    origin + route, wait_until="domcontentloaded", timeout=30000
                )
                assert response is not None and response.status == 200
                assert expected_class in page.locator("body").get_attribute("class")
                assert page.locator(expected_control).first.is_visible()
                assert page.locator("header").first.is_visible()
                page.screenshot(
                    path=str(screenshots / ("lab-" + route.replace("/", "-") + ".png")),
                    timeout=30000,
                )

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
