"""Validate the canonical real-robot showroom and experimental learned controller.

This checks the actual manufacturer-derived MuJoCo models and attached P37
policy assets, not procedural stand-ins or a screenshot of robot animation.
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
    assert (site / "index.html").is_file()
    catalog = json.loads((site / "catalog.json").read_text(encoding="utf-8"))
    robots = catalog["robots"]
    assert len(robots) == 10
    assert {r["id"] for r in robots} >= {"unitree_g1", "unitree_go2", "franka_panda"}
    metadata = json.loads((site / "build-info.json").read_text(encoding="utf-8"))
    assert metadata["site_entry"] == "/P37-Neuro/"
    assert metadata["trained_p37_policy_attached"] is True
    assert metadata["experimental_policy_robot"] == "unitree_g1"
    assert metadata["qualified_cross_body_transfer"] is False
    assert metadata["physical_task_scene_version"] == 2
    panda_task = metadata["panda_physical_cube_stack"]
    assert panda_task["qualified_native_contact_and_replay"] is True
    assert panda_task["learned_p37_policy"] is False
    assert panda_task["frames"] > 500
    assert panda_task["control_hz"] == 50
    assert set(metadata["task_experiences"]) == {
        "live_assisted_physics",
        "source_recorded_replay",
        "experimental_p37_policy",
    }
    assert (site / "recorded/index.html").is_file()
    assert (site / "recorded/samples/mimicgen-square-source.json").is_file()
    previews = json.loads((site / "task-previews/manifest.json").read_text(encoding="utf-8"))
    assert previews["renderer"] == "MuJoCo Python offscreen"
    assert len(previews["scenes"]) == 6
    assert all(item["actual_mujoco_scene"] is True for item in previews["scenes"])
    for item in previews["scenes"]:
        image = site / "task-previews" / item["file"]
        assert image.is_file() and image.stat().st_size > 12000
        assert image.read_bytes().startswith(bytes((255, 216, 255)))
    cross = json.loads((site / "p37-cross-body-evidence.json").read_text(encoding="utf-8"))
    assert metadata["p37_checkpoint_sha256"] == cross["checkpoint_sha256"]
    assert cross["qualified_for_walking"] is False
    assert cross["qualified_for_cross_body_task_transfer"] is False
    manifest = json.loads((site / "simulator" / "manifest.json").read_text(encoding="utf-8"))
    scenes = {s["id"]: s for p in manifest["projects"] for s in p["scenes"]}
    assert {r["id"] for r in robots} <= scenes.keys()
    assert scenes["unitree_g1"].get("policies"), "Missing browser ONNX controller"
    assert any(
        p["id"] == "panda_physical_cube_stack_scripted" for p in scenes["franka_panda"]["policies"]
    ), "Validated physical Panda stack replay is not attached"
    motions = json.loads((site / "simulator/motion_data/index.json").read_text(encoding="utf-8"))
    assert set(motions["motions"]) == {r["id"] for r in robots}
    for robot in robots:
        available = {p["id"] for p in scenes[robot["id"]]["policies"]}
        assert {"motor_articulation", "movement_cycle", "hold_position"} <= available
        clips = motions["motions"][robot["id"]]
        assert {clip["id"] for clip in clips} == {"articulation", "motion_cycle", "hold"}
        for clip in clips:
            assert clip["is_learned_p37_policy"] is False
            assert clip["is_qualified_locomotion"] is False
            assert (site / "simulator/motion_data" / clip["dataset_file"]).is_file()
    assert any("p37" in p["id"] for p in scenes["unitree_g1"]["policies"]), (
        "Experimental G1 P37 policy missing"
    )
    assert all(
        not any("p37" in p["id"] for p in scene["policies"])
        for key, scene in scenes.items()
        if key != "unitree_g1"
    ), "Learned policy falsely attached to another body"
    bridge = site / "simulator/steering_bridge.js"
    assert bridge.is_file(), "Steering bridge missing from real MuJoCo scene"
    js = bridge.read_text(encoding="utf-8")
    assert "xfrc_applied" in js and "event.origin !== window.location.origin" in js
    assert "p37:steering" in js and "p37:telemetry" in js
    assert "steering_bridge.js" in (site / "simulator/index.html").read_text(encoding="utf-8")
    for old_route in ("lab", "demos", "test"):
        assert not (site / old_route).exists()
    assert not (site / "studio.js").exists(), "Old procedural showroom is still published"

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
            response = page.goto(origin, wait_until="domcontentloaded", timeout=45000)
            assert response is not None and response.status == 200
            page.get_by_role("heading", name="Watch the robots do the work.").wait_for(
                timeout=35000
            )
            assert page.locator(".task-gallery-card").count() == 6
            assert page.locator(".task-gallery-card img").count() == 6
            page.wait_for_function(
                "() => Array.from(document.querySelectorAll('.task-gallery-card img'))"
                ".slice(0,3).every(img => img.complete && img.naturalWidth > 300)",
                timeout=35000,
            )
            assert page.locator(".robot-catalog button").count() == 10
            assert "reference arm" not in page.locator("main").inner_text().lower()
            assert "compact arm" not in page.locator("main").inner_text().lower()
            assert "Validated scripted Panda reference" in page.locator(
                ".p37-real-panel"
            ).inner_text()
            assert "walking" in page.locator(".policy-evidence").inner_text().lower()
            assert page.locator(".menagerie-viewer").count() == 1
            assert "scene=franka_panda" in page.locator("iframe.menagerie-viewer").get_attribute(
                "src"
            )
            assert "policy=panda_physical_cube_stack_scripted" in page.locator(
                "iframe.menagerie-viewer"
            ).get_attribute("src")
            page.screenshot(path=str(screenshots / "task-gallery-desktop.png"), timeout=90000)
            page.get_by_role("button", name="Navigation", exact=True).click()
            assert page.locator(".task-gallery-card").count() == 2
            page.get_by_role("button", name="All experiments").click()
            assert page.locator(".task-gallery-card").count() == 6
            page.get_by_role(
                "button", name="Inspect P37 experiment — Test a learned G1 controller."
            ).click()
            assert "scene=unitree_g1" in page.locator("iframe.menagerie-viewer").get_attribute(
                "src"
            )
            assert "policy=movement_cycle" in page.locator("iframe.menagerie-viewer").get_attribute(
                "src"
            )
            assert page.get_by_role("button", name="Hold motion").is_visible()
            assert page.get_by_role("button", name="Forward").is_visible()
            assert page.get_by_role("button", name="Live physical tasks").is_visible()
            assert page.get_by_role("button", name="Recorded execution").is_visible()
            assert page.get_by_role("button", name="P37 model experiment").is_visible()
            assert page.get_by_role("region", name="Measured robot task experiment").is_visible()
            assert page.get_by_text("Move to the inspection point").is_visible()
            assert page.get_by_role("progressbar", name="Measured task progress").is_visible()
            assert page.get_by_role("button", name="Turn left").is_visible()
            assert "Download this robot" not in page.locator("main").inner_text()
            page.get_by_role("button", name="Motor articulation").click()
            assert "policy=motor_articulation" in page.locator(
                "iframe.menagerie-viewer"
            ).get_attribute("src")
            page.get_by_role("button", name="Hold motion").click()
            assert "policy=hold_position" in page.locator("iframe.menagerie-viewer").get_attribute(
                "src"
            )
            page.get_by_role("button", name="Play motion").click()
            assert "policy=motor_articulation" in page.locator(
                "iframe.menagerie-viewer"
            ).get_attribute("src")
            page.get_by_role("button", name="Experimental P37 G1").click()
            assert "policy=p37_g1_experimental_recurrent_ppo" in page.locator(
                "iframe.menagerie-viewer"
            ).get_attribute("src")
            assert page.url == origin
            page.frame_locator("iframe.menagerie-viewer").locator("canvas").first.wait_for(
                state="visible", timeout=120000
            )
            page.wait_for_function(
                "() => document.querySelector('iframe.menagerie-viewer')"
                "?.contentWindow?.__mjswanReady === true",
                timeout=120000,
            )
            page.screenshot(path=str(screenshots / "g1-p37-live-inference.png"), timeout=90000)
            page.get_by_role("combobox", name="Select a robot").select_option("franka_panda")
            assert "Fixed-base robot" in page.locator(".p37-steer-panel").inner_text()
            assert page.get_by_text("Stack two physical cubes").is_visible()
            assert page.locator(".p37-task-primary").is_visible()
            assert "policy=panda_physical_cube_stack_scripted" in page.locator(
                "iframe.menagerie-viewer"
            ).get_attribute("src")
            assert page.get_by_role("button", name="Forward").count() == 0
            assert "scene=franka_panda" in page.locator("iframe.menagerie-viewer").get_attribute(
                "src"
            )
            page.frame_locator("iframe.menagerie-viewer").locator("canvas").first.wait_for(
                state="visible", timeout=120000
            )
            page.wait_for_function(
                "() => document.querySelector('.p37-task-progress strong')"
                "?.textContent?.includes('cube alignment')",
                timeout=120000,
            )
            assert (
                "stack not confirmed" in page.locator(".p37-task-experiment").inner_text().lower()
            )
            page.screenshot(path=str(screenshots / "panda-real-model.png"), timeout=90000)
            # Actual native physics trial and independent replay are enforced
            # by build_mjswan before the browser artifact can be published.
            page.locator(".p37-real-panel .info-row").filter(has_text="Controller").locator(
                "strong"
            ).filter(has_text="Validated scripted Panda reference").wait_for(timeout=15000)
            page.get_by_role("combobox", name="Select a robot").select_option("unitree_go2")
            assert "scene=unitree_go2" in page.locator("iframe.menagerie-viewer").get_attribute(
                "src"
            )
            assert page.get_by_text("Traverse the physical obstacle course").is_visible()
            assert page.get_by_role("button", name="Run assisted terrain attempt").is_visible()
            page.frame_locator("iframe.menagerie-viewer").locator("canvas").first.wait_for(
                state="visible", timeout=120000
            )
            page.get_by_text("Ready for input").wait_for(state="visible", timeout=120000)
            page.keyboard.down("w")
            try:
                page.wait_for_function(
                    "() => Number.parseFloat(document.querySelector("
                    "'.p37-steering-telemetry strong')?.textContent || '') > 0.02",
                    timeout=15000,
                )
            finally:
                page.keyboard.up("w")
            measured = page.locator(".p37-steering-telemetry strong").inner_text()
            assert measured.endswith(" m traveled"), measured
            displacement = float(measured.split(" ")[0])
            assert displacement > 0.02, f"Steering did not move real Go2: {measured}"
            page.screenshot(path=str(screenshots / "go2-user-steering.png"), timeout=90000)
            page.get_by_role("button", name="Run assisted terrain attempt").click()
            page.get_by_role("button", name="Stop scripted attempt").wait_for(timeout=15000)
            page.screenshot(path=str(screenshots / "go2-scripted-task.png"), timeout=90000)
            page.get_by_role("button", name="Stop scripted attempt").click()
            page.get_by_role("button", name="Run assisted terrain attempt").wait_for(timeout=15000)
            page.locator(".p37-real-panel .info-row").filter(has_text="Controller").locator(
                "strong"
            ).filter(has_text="Dataset motor replay").wait_for(timeout=15000)
            # G1 and policy selection were verified before Go2. Keep this
            # physically moving Go2 scene for the mobile check instead of
            # forcing another expensive GPU scene reload after steering.
            assert page.url == origin
            assert "Dataset motor replay" in page.locator(".p37-real-panel").inner_text()
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(400)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
            page.screenshot(path=str(screenshots / "real-robot-mobile.png"), timeout=90000)
            page.get_by_role("button", name="Recorded execution").click()
            assert page.locator("iframe.p37-recorded-viewer").count() == 1
            assert page.locator("iframe.menagerie-viewer").count() == 0
            page.frame_locator("iframe.p37-recorded-viewer").get_by_text(
                "2 recorded episodes imported"
            ).wait_for(timeout=30000)
            page.get_by_role("button", name="Live physical tasks").click()
            assert page.locator("iframe.p37-recorded-viewer").count() == 0
            assert "scene=unitree_go2" in page.locator("iframe.menagerie-viewer").get_attribute(
                "src"
            )
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    return {
        "single_root": True,
        "native_robot_models": 10,
        "experimental_g1_policy": True,
        "all_robot_motion_datasets": True,
        "physical_user_steering": True,
        "download_ui_removed": True,
        "task_objectives_and_metrics": True,
        "physical_task_scenes_and_source_recording": True,
        "task_first_gallery_and_native_scenes": True,
        "desktop_mobile": True,
        "panda_model_loaded": True,
        "unqualified_models_not_mislabeled": True,
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
