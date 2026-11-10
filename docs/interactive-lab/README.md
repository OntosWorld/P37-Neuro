# P37 Cross-Embodiment Interactive Lab

This is an experimental, dependency-free web interface for explaining the P37 task-to-embodiment architecture alongside its actual evidence status.

## Open

Serve this directory with any static HTTP server and navigate to `index.html`:

```bash
python -m http.server 8000 --directory docs/interactive-lab
```

Then open http://localhost:8000/ . The page is intentionally independent of React, Python, MuJoCo installation, and any hosted inference backend. It is safe to deploy as an **architecture explorer** before a trained browser policy is available.

## Important distinction

- The interactive SVG depicts the **architectural contract**, not simulated dynamics.
- The existing [P37 Brain Lab](https://ontosrobotics.github.io/P37-Neuro/) provides the robot-model MuJoCo browser experience, currently marked **model-only**.
- The repository's [roadmap](../roadmap.md) tracks trained capability qualification separately from platform implementation.
- The [testing protocol](../testing.md) specifies T0–T6 evidence levels and held-out-body rules.

Do not label the diagram as live simulation, model inference, adaptation, recovery, or cross-embodiment transfer. A rendered robot arm moving toward a target would not, on its own, establish those claims.

## Controls

- Select a task objective: reach, transfer, or recover.
- Select a representative arm morphology or mobile manipulator.
- Share a URL with the selected task and embodiment.
- Open the existing physics viewer and source qualification protocol.

## Integration into the existing site

The published Brain Lab deployment source was not located through the default-branch source paths inspected when this interface was added. This is a **separate additive page**; its presence in the repository does not automatically make it available at the GitHub Pages URL. Once the site build/deployment directory is confirmed, copy or serve this page at `/P37-Neuro/experiments/` and add a navigation link to the current site. Keep the existing physics viewer and its warning about model-only runs intact.

## Next phase: real evidence-backed simulation comparison

Before enabling a trained P37 policy on the public site:

1. Export canonical episode traces for at least two distinct robot embodiments with the **same frozen model checkpoint**, or clearly declare differences.
2. Record task ID and pre-registered success criteria, robot description checksums, model hash, adapter versions, simulator/version, code SHA, seeds, observations, commands, measured outcomes, and held-out/train membership.
3. Run qualification against the repository's testing protocol. Publish negative outcomes and failure counts, not only selected successful runs.
4. Build a comparison viewer with synchronized recorded episodes, timestamp scrubbing, calibrated camera, task progress, command histories, failure markers, and per-episode metrics.
5. Gate any live browser policy integration on closed-loop qualification, inference parity, safety controls, and appropriate isolation. Do not expose unrestricted actuator or model execution endpoints.
6. Only after a qualified benchmark exists, show numerical cross-embodiment comparisons or competitive claims with explicit matched conditions.

## Acceptance criteria for this first increment

- Page loads without third-party dependencies.
- Task and robot controls update the schematic and link state.
- No fabricated policy performance, measured success rates, or robot physics are shown.
- Current source/protocol and actual physics viewer remain directly accessible.
- Works on desktop and narrow mobile layouts.
- Keyboard controls and reduced-motion settings are respected.

## Recorded evidence comparison (implemented)

Open [compare/index.html](compare/index.html) after serving this directory with the same static HTTP server. The viewer accepts local JSON only and synchronizes time across two or more recorded episodes. The **joint-state rails are recorded numerical values, not robot geometry or an animated physics simulation**. There are no hard-coded examples or invented success rates.

The Python adapter `p37_neuro.data.trace_export` serializes canonical `Episode` objects, including joint-position/velocity observations, commands, reward, failure and intervention markers, and explicit source/provenance metadata. The comparison schema is `p37-trace-v1`.

Example for existing in-memory canonical episodes:

```python
from p37_neuro.data.trace_export import TraceProvenance, export_comparison, write_comparison

# Supply actual recorded Episode objects from your real P37 run.
episodes = [recorded_arm_a, recorded_arm_b]
provenances = [
    TraceProvenance(
        checkpoint_sha256=checkpoint_sha256_a,
        code_commit=code_commit,
        simulator="MuJoCo",
        simulator_version=simulator_version,
        robot_description_sha256=robot_description_sha_a,
        adapter_version=adapter_a,
        seed=seed_a,
        training_membership="held-out",
        evidence_level="T2",
        policy_attached=True,
        evaluation_protocol="docs/testing.md",
        outcome="unverified",
    ),
    TraceProvenance(
        checkpoint_sha256=checkpoint_sha256_b,
        code_commit=code_commit,
        simulator="MuJoCo",
        simulator_version=simulator_version,
        robot_description_sha256=robot_description_sha_b,
        adapter_version=adapter_b,
        seed=seed_b,
        training_membership="held-out",
        evidence_level="T2",
        policy_attached=True,
        evaluation_protocol="docs/testing.md",
        outcome="unverified",
    ),
]
artifact = export_comparison(episodes, provenances, title="Recorded reach task")
write_comparison("comparison.json", artifact)
```

The example intentionally uses undefined placeholders for **real run artifacts**; it cannot be executed until you supply actual episodes and provenance. Do not replace them with fabricated claims. The exporter does not calculate success or claim evidence quality: the caller must derive those fields from qualified external evaluation.

- Import `comparison.json` via the file control in the browser.
- The synchronized view uses each episode's recorded timestamps. If traces have different durations, the shorter trace holds its final recorded sample.
- Frames are sampled with zero-order hold; no intervening physical state is inferred.
- The browser cannot verify hashes or confirm that the imported content is genuine. External provenance checks and acceptance gates remain mandatory.
- This is an offline, dependency-free viewer. Live simulation rendering and deploy-site routing are separate workstreams.

Tests are in `tests/test_trace_export.py`. Run `uv run pytest tests/test_trace_export.py` in the repository environment.
