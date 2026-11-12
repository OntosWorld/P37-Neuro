"""Static invariants for the P37 public physics and research interface."""

from pathlib import Path

from catalog import ROBOTS, check_catalog

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


def test_builder_keeps_real_mujoco_scenes() -> None:
    script = (ROOT / "build_mjswan.py").read_text(encoding="utf-8")
    assert "MjSpec.from_file" in script
    assert "project.add_scene" in script
    assert "scene.set_viewer" in script
    assert "_light_scene" in script
    assert "contype=0" in script
    assert "for robot in ROBOTS" in script


def test_public_demos_keep_capability_claims_evidence_gated() -> None:
    html = (ROOT / "demos" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "demos" / "demos.js").read_text(encoding="utf-8")
    evidence = (ROOT / "build_demo_evidence.py").read_text(encoding="utf-8")
    assert "same trained checkpoint" in html
    assert "not yet verified" in html
    assert "controlled policy-transfer benchmark" in html
    assert "Live MuJoCo" in html
    assert 'controller !== "none"' in js
    assert "qualified_for_walking !== false" in js
    assert "same_checkpoint_task_transfer_qualified" in evidence
    assert "same_checkpoint_joint_actions_executed_on_two_bodies" in evidence
    assert "mujoco.MjModel.from_xml_path" in evidence
    assert "p37-cross-body-evidence.json" in evidence
    assert "p37_recovery_claimed" in evidence
    assert "demos.css" in html and "demos.js" in html


def test_manufacturer_models_are_embedded_on_single_public_root() -> None:
    """The canonical root embeds the real-robot viewer without extra public navigation."""
    assembler = (ROOT / "assemble_site.py").read_text(encoding="utf-8")
    root_app = (
        ROOT.parents[1] / "docs" / "interactive-lab" / "steel" / "src" / "App.tsx"
    ).read_text(encoding="utf-8")
    assert 'shutil.copytree(simulator, output / "simulator")' in assembler
    assert '"catalog.json"' in assembler
    assert "for robot in ROBOTS" in assembler
    assert "iframe" in root_app and "menagerie-viewer" in root_app
    assert "Select real robot body" in root_app
    assert "unitree_g1" in root_app
    assert "One brain. Different bodies." in root_app
    assert "P37 recurrent PPO" in root_app
    assert "Movement cycle" in root_app
    assert "Articulation" in root_app
    assert "Hold motion" in root_app
    assert "not a trained autonomous skill" in root_app.lower()
    assert "POWERED BY P37-NEURO" in root_app
    assert "model_derived" in (ROOT / "model_motion_library.py").read_text(encoding="utf-8")
    assert "compact arm" not in root_app.lower()
    assert "extended arm" not in root_app.lower()
    assert "attach_g1_policy" in (ROOT / "build_mjswan.py").read_text(encoding="utf-8")
    adapter = (ROOT / "p37_browser_policy.py").read_text(encoding="utf-8")
    assert "next_memory" in adapter and "adapt_hx" in adapter
    assert "p37_checkpoint_sha256" in assembler
