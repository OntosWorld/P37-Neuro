"""Static checks for the physical robot web entry point."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_browser_page_names_real_robots():
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    for name in ("Unitree G1", "Unitree Go2", "Franka Panda", "simulator/manifest.json"):
        assert name in page
    assert "Model-only physics" in page
    assert "not been qualified" in page


def test_builder_defines_real_menagerie_scenes():
    script = (ROOT / "build_mjswan.py").read_text(encoding="utf-8")
    for model in ("unitree_g1", "unitree_go2", "franka_emika_panda"):
        assert model in script
    assert "MjSpec.from_file" in script
    assert "scene.set_viewer" in script
