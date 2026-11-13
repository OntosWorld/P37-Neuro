"""Capture real MuJoCo WebAssembly robot scene previews with browser WebGL.

These frames are taken from the actual public simulator viewer, using the
manufacturer meshes and task contact geometry. This avoids inventing robot
illustrations or using a different visual engine than the public experience.
The featured Panda frame must show the actual simulated cube lifted by its
motor replay; CI fails if browser physics does not produce that state.
"""

from __future__ import annotations

import argparse
import http.server
import io
import json
import socketserver
import threading
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

from catalog import ROBOTS

WIDTH = 1080
HEIGHT = 700
VIEWER_PREFIX = "/P37-Neuro/simulator/"


class LocalServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def capture(simulator: Path, destination: Path) -> dict:
    simulator = simulator.resolve()
    if not (simulator / "manifest.json").is_file():
        raise FileNotFoundError("Native MuJoCo browser scenes must be built before previews")
    destination.mkdir(parents=True, exist_ok=True)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            name = urlsplit(path).path
            if not name.startswith(VIEWER_PREFIX):
                return str(simulator / "__not_found__")
            return super().translate_path("/" + name[len(VIEWER_PREFIX) :])

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(simulator), **kwargs)

        def log_message(self, *_args):
            pass

    server = LocalServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    root = f"http://127.0.0.1:{server.server_port}{VIEWER_PREFIX}"
    provenance = {
        "format": "p37-mujoco-browser-task-posters",
        "generated_from": "google-deepmind/mujoco_menagerie",
        "renderer": "MuJoCo WebAssembly / Chromium WebGL",
        "robot_count": len(ROBOTS),
        "posters": [],
    }
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
            context = browser.new_context(
                viewport={"width": WIDTH, "height": HEIGHT},
                device_scale_factor=1,
            )
            for robot in ROBOTS:
                page = context.new_page()
                try:
                    policy = (
                        "panda_physical_cube_stack_scripted"
                        if robot.id == "franka_panda"
                        else "movement_cycle"
                    )
                    url = root + "?project=p37_robot_models&scene=" + robot.id + "&policy=" + policy
                    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    if response is None or response.status != 200:
                        raise RuntimeError(f"Robot browser scene HTTP failure: {robot.id}")
                    page.wait_for_function(
                        "() => window.__mjswanReady === true && "
                        "window.__p37Engine?.runtime?.mjData && "
                        "document.querySelector('canvas')",
                        timeout=120000,
                    )
                    canvas = page.locator("canvas").first
                    canvas.wait_for(state="visible", timeout=30000)
                    if robot.id == "franka_panda":
                        # Check the real source cube freejoint position while the
                        # validated motor table runs, before taking its poster.
                        page.wait_for_function(
                            """() => {
                              const runtime = window.__p37Engine?.runtime;
                              const model = runtime?.mjModel;
                              const data = runtime?.mjData;
                              if (!model || !data || data.time < 8.0) return false;
                              for (let j = 0; j < model.njnt; j++) {
                                if (model.jnt_type[j] === 0) {
                                  const address = model.jnt_qposadr[j];
                                  return Number(data.qpos[address+2]) > 0.66;
                                }
                              }
                              return false;
                            }""",
                            timeout=120000,
                        )
                    else:
                        page.wait_for_timeout(650)
                    pixels = canvas.screenshot(type="png", timeout=30000)
                    image = Image.open(io.BytesIO(pixels)).convert("RGB")
                    if image.width < 450 or image.height < 300:
                        raise RuntimeError(f"Invalid robot frame dimensions: {robot.id}")
                    # Crop the real camera render (not procedural re-rendering).
                    ratio = WIDTH / HEIGHT
                    if image.width / image.height > ratio:
                        crop_width = int(image.height * ratio)
                        offset = (image.width - crop_width) // 2
                        image = image.crop((offset, 0, offset + crop_width, image.height))
                    else:
                        crop_height = int(image.width / ratio)
                        offset = (image.height - crop_height) // 2
                        image = image.crop((0, offset, image.width, offset + crop_height))
                    image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
                    if max(ImageStat.Stat(image).stddev) < 3.0:
                        raise RuntimeError(f"Blank browser render: {robot.id}")
                    outfile = destination / f"{robot.id}.webp"
                    image.save(outfile, "WEBP", quality=86, method=4)
                    if outfile.stat().st_size < 7000:
                        raise RuntimeError(f"Robot image suspiciously small: {robot.id}")
                    provenance["posters"].append(
                        {
                            "robot_id": robot.id,
                            "filename": outfile.name,
                            "model": robot.model + "/scene.xml",
                            "width": WIDTH,
                            "height": HEIGHT,
                            "pixels_from_mujoco_browser_renderer": True,
                            "panda_lift_frame_from_actual_motors": robot.id == "franka_panda",
                        }
                    )
                    print(f"POSTER {robot.id}: {outfile.stat().st_size:,} bytes", flush=True)
                finally:
                    page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (destination / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    return provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulator", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(capture(args.simulator, args.output), indent=2))


if __name__ == "__main__":
    main()
