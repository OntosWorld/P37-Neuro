"""Static invariants for the P37 public physics and research interface."""

import re
from pathlib import Path

from catalog import ROBOTS, check_catalog
from demo_specs import DEMOS

ROOT = Path(__file__).resolve().parent


def test_curated_catalog() -> None:
    check_catalog()
    assert len(ROBOTS) >= 10
    assert {robot.kind for robot in ROBOTS} >= {
        "Humanoids",
        "Quadrupeds",
        "Manipulators",
        "Mobile",
        "Aerial",
    }
    assert {"unitree_g1", "unitree_go2", "franka_panda"}.issubset({robot.id for robot in ROBOTS})


def test_browser_has_real_interaction_and_honest_policy_status() -> None:
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "studio.js").read_text(encoding="utf-8")
    css = (ROOT / "studio.css").read_text(encoding="utf-8")
    minimal_css = (ROOT / "studio-minimal.css").read_text(encoding="utf-8")
    for marker in (
        "P37 Brain Lab",
        "studio.css",
        "studio.js",
        "robot-library",
        "scene-canvas",
        "inspector-panel",
        "p37-evidence",
        "Trained P37 policy",
    ):
        assert marker in page or marker in js
    assert "simulator/manifest.json" in js
    assert "NOT ATTACHED" in page
    assert "not walking-qualified" in js.lower() or "not walking-qualified" in page.lower()
    assert len(css) > 4000
    assert len(minimal_css) > 4000
    for marker in ("toggle-library", "browse-models", "surface-scrim", "close-inspector"):
        assert marker in page
    assert "openDrawer" in js and "closeDrawers" in js
    assert "height:calc(100dvh - 64px)" in minimal_css
    assert "studio-minimal.css" in page


def test_demos_are_physical_tasks_and_not_fake_p37_policies() -> None:
    assert len(DEMOS) >= 3
    assert {demo.robot_id for demo in DEMOS} >= {
        "unitree_g1",
        "unitree_go2",
        "franka_panda",
    }
    assert all(demo.policy == "physics-only" for demo in DEMOS)
    script = (ROOT / "demo_specs.py").read_text(encoding="utf-8")
    assert "add_freejoint" in script
    assert "mjGEOM_BOX" in script
    assert "density=" in script
    web = (ROOT / "studio.js").read_text(encoding="utf-8")
    assert "loadCrossBodyResults" in web
    assert "performance_qualified !== false" in web
    assert "selectDemo" in web
    assert (ROOT / "demos.css").is_file()
    html_ids = set(re.findall(r'\\bid="([^"]+)"', (ROOT / "index.html").read_text()))
    js_ids = set(re.findall(r'\\bdom\\("([^"]+)"\\)', web))
    assert js_ids <= html_ids, f"missing JavaScript targets: {sorted(js_ids - html_ids)}"


def test_builder_keeps_real_mujoco_scenes() -> None:
    script = (ROOT / "build_mjswan.py").read_text(encoding="utf-8")
    assert "MjSpec.from_file" in script
    assert "project.add_scene" in script
    assert "scene.set_viewer" in script
    assert "_light_scene" in script
    assert "contype=0" in script
    assert "for robot in ROBOTS" in script
