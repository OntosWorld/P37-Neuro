/* P37 Brain Lab public demos.
   Source-of-truth physics: compiled MuJoCo Menagerie scenes.
   Source-of-truth experiments: generated native MuJoCo and P37 records.
   No fabricated neural transfer, recovery, or benchmarking claims.
*/
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = {
    catalog: [],
    available: new Set(),
    evidence: null,
    selected: "unitree_g1",
    comparisonActive: false,
    stageTimer: null,
    stageLoadVersion: 0
  };

  function model(id) {
    return state.catalog.find((robot) => robot.id === id);
  }

  function simUrl(id) {
    return "../simulator/?" + new URLSearchParams({
      project: "p37_robot_models",
      scene: id,
      panel: "0"
    }).toString();
  }

  function setStageStatus(message) {
    $("stage-state").textContent = message;
  }

  function stageError(message) {
    $("stage-loading").hidden = true;
    $("stage-error").hidden = false;
    $("stage-error").querySelector("span").textContent = message;
    setStageStatus("SIMULATION UNAVAILABLE");
  }

  function startStage(id) {
    const robot = model(id);
    if (!robot) return;
    state.selected = id;
    const version = ++state.stageLoadVersion;
    for (const button of document.querySelectorAll(".scene-choice")) {
      const active = button.dataset.scene === id;
      button.classList.toggle("selected", active);
      button.setAttribute("aria-pressed", String(active));
    }
    $("stage-robot").textContent = robot.name.toUpperCase();
    $("stage-title").textContent = robot.name;
    $("stage-caption").textContent = "Live MuJoCo · Model-only physics";
    $("stage-standalone").href = "../?robot=" + encodeURIComponent(id);
    if (state.stageTimer) clearTimeout(state.stageTimer);
    const frame = $("stage-frame");
    $("stage-loading").hidden = false;
    $("stage-error").hidden = true;
    setStageStatus("LOADING PHYSICS");
    if (!state.available.has(id)) {
      frame.src = "about:blank";
      stageError("This robot scene is missing from the compiled simulation bundle.");
      return;
    }
    frame.onload = () => {
      if (version !== state.stageLoadVersion || state.comparisonActive) return;
      $("stage-loading").hidden = true;
      setStageStatus("PHYSICS RUNNING");
      if (state.stageTimer) clearTimeout(state.stageTimer);
    };
    frame.src = simUrl(id);
    state.stageTimer = setTimeout(() => {
      if (version === state.stageLoadVersion && !$("stage-loading").hidden) {
        stageError("The simulator did not load. Check WebGL support or open the full lab.");
      }
    }, 110000);
  }

  function setCompareOptions() {
    for (const select of [$("body-a"), $("body-b")]) {
      const chosen = select.value;
      select.replaceChildren();
      for (const robot of state.catalog) {
        const option = document.createElement("option");
        option.value = robot.id;
        option.textContent = robot.name;
        select.append(option);
      }
      if (model(chosen)) select.value = chosen;
    }
    if (model("unitree_g1")) $("body-a").value = "unitree_g1";
    if (model("unitree_go2")) $("body-b").value = "unitree_go2";
  }

  function renderStats(id, suffix) {
    const name = $("compare-name-" + suffix);
    const stats = $("body-stats-" + suffix);
    const robot = model(id);
    name.textContent = robot ? robot.name : "Not available";
    stats.replaceChildren();
    const body = state.evidence?.bodies?.[id];
    if (!body) {
      stats.textContent = "Model metadata is unavailable. No morphology figures are asserted.";
      return;
    }
    for (const [label, key] of [
      ["JOINTS", "joints"],
      ["ACTUATORS", "actuators"],
      ["RIGID BODIES", "bodies"]
    ]) {
      const item = document.createElement("div");
      item.className = "stat-item";
      const value = document.createElement("strong");
      value.textContent = String(body[key]);
      const text = document.createElement("span");
      text.textContent = label;
      item.append(value, text);
      stats.append(item);
    }
  }

  function stopComparison({restoreStage = true} = {}) {
    if (!state.comparisonActive) return;
    state.comparisonActive = false;
    for (const key of ["a", "b"]) {
      $("compare-frame-" + key).src = "about:blank";
      $("compare-idle-" + key).hidden = false;
    }
    $("compare-stop").disabled = true;
    $("compare-run").disabled = false;
    $("compare-run").textContent = "Launch both simulations ↗";
    if (restoreStage) startStage(state.selected);
  }

  function launchComparison() {
    const a = $("body-a").value;
    const b = $("body-b").value;
    if (a === b) {
      $("body-b").focus();
      return;
    }
    if (!state.available.has(a) || !state.available.has(b)) return;
    if (!state.comparisonActive) {
      state.comparisonActive = true;
      ++state.stageLoadVersion;
      if (state.stageTimer) clearTimeout(state.stageTimer);
      $("stage-frame").src = "about:blank";
      $("stage-loading").hidden = true;
      $("stage-error").hidden = false;
      $("stage-error").querySelector("strong").textContent =
        "Single simulation paused for comparison.";
      $("stage-error").querySelector("span").textContent =
        "Stop the comparison to return to the main scene.";
      setStageStatus("SCENE PAUSED");
    }
    for (const [key, id] of [["a", a], ["b", b]]) {
      renderStats(id, key);
      $("compare-idle-" + key).hidden = true;
      $("compare-frame-" + key).src = simUrl(id);
    }
    $("compare-stop").disabled = false;
    $("compare-run").textContent = "Restart comparison ↻";
  }

  function displayCrossBodyP37() {
    const cross = state.evidence?.cross_body_p37;
    const capability = state.evidence?.cross_embodiment;
    if (!cross ||
        cross.same_checkpoint_used_for_all_bodies !== true ||
        cross.parameters_retrained_for_go2 !== false ||
        cross.qualified_for_cross_body_task_transfer !== false ||
        cross.browser_policy_attached !== false ||
        capability?.same_checkpoint_task_transfer_qualified !== false) {
      $("cross-p37-stats").textContent =
        "The shared-checkpoint experiment has not been validated for this build.";
      return;
    }
    const g1 = cross.bodies.unitree_g1;
    const go2 = cross.bodies.unitree_go2;
    if (g1?.inference_and_physics_executed !== true ||
        go2?.inference_and_physics_executed !== true) {
      $("cross-p37-stats").textContent = "Verified native P37 actuation data unavailable.";
      return;
    }
    $("cross-g1-actions").textContent = String(g1.actuators);
    $("cross-go2-actions").textContent = String(go2.actuators);
    $("cross-duration").textContent = Number(cross.horizon_s).toFixed(1) + " s";
    $("cross-retraining").textContent = "None";
    const url = cross.provenance?.workflow;
    if (/^https:\/\/github\.com\/OntosRobotics\/P37-Neuro\/actions\/runs\/\d+$/.test(url)) {
      $("cross-p37-source").href = url;
    }
  }

  function displayForces() {
    const root = $("force-results");
    root.replaceChildren();
    const data = state.evidence?.force_trials;
    if (!data) {
      root.textContent = "No signed-off disturbance measurement file was published.";
      return;
    }
    const required = [
      ["unitree_g1", "Unitree G1"],
      ["unitree_go2", "Unitree Go2"]
    ];
    const values = required.map(([key]) => data[key]?.displacement_vs_control_m || 0);
    const max = Math.max(...values, 0.001);
    for (const [key, label] of required) {
      const t = data[key];
      if (!t || t.controller !== "none" || t.repeat_deterministic !== true) continue;
      const row = document.createElement("div");
      row.className = "force-row";
      const heading = document.createElement("div");
      heading.className = "force-label";
      const name = document.createElement("strong");
      name.textContent = label;
      const result = document.createElement("span");
      result.textContent = (t.displacement_vs_control_m * 100).toFixed(2) + " cm";
      heading.append(name, result);
      const track = document.createElement("div");
      track.className = "force-track";
      const bar = document.createElement("div");
      bar.className = "force-fill";
      bar.style.width = ((t.displacement_vs_control_m / max) * 100).toFixed(1) + "%";
      track.append(bar);
      const detail = document.createElement("div");
      detail.className = "force-detail";
      detail.textContent = String(t.force_newtons) +
        " N external force · Repeated, deterministic simulated response";
      row.append(heading, track, detail);
      root.append(row);
    }
    if (!root.children.length) root.textContent = "No validated force trials could be displayed.";
  }

  function displayP37() {
    const root = $("p37-trials");
    root.replaceChildren();
    const report = state.evidence?.p37_g1;
    if (!report || report.qualification !== "unqualified" ||
        report.qualified_for_walking !== false ||
        report.browser_policy_attached !== false) {
      root.textContent = "A verified P37 evaluation record is not available.";
      return;
    }
    const trials = report.evaluation.seeds;
    $("trial-total").textContent = String(trials.length);
    for (const trial of trials) {
      const row = document.createElement("div");
      row.className = "p37-trial-row";
      const meta = document.createElement("div");
      const seed = document.createElement("strong");
      seed.textContent = "Seed " + trial.seed;
      const duration = document.createElement("span");
      duration.textContent = " · " + Number(trial.sim_seconds).toFixed(2) + " s";
      meta.append(seed, duration);
      const result = document.createElement("div");
      result.className = "trial-pill " + (trial.fallen ? "fell" : "horizon");
      result.textContent = trial.fallen ? "FELL" : "REACHED HORIZON";
      row.append(meta, result);
      root.append(row);
    }
    const provenance = report.provenance.training_workflow;
    if (/^https:\/\/github\.com\/OntosRobotics\/P37-Neuro\/actions\/runs\/\d+$/.test(provenance)) {
      $("p37-source").href = provenance;
    }
  }

  async function loadData() {
    const paths = ["../catalog.json", "../simulator/manifest.json", "./evidence.json"];
    const fetched = await Promise.all(paths.map(async (path) => {
      try {
        const response = await fetch(path, {cache: "no-store"});
        if (!response.ok) return null;
        return await response.json();
      } catch { return null; }
    }));
    const catalog = fetched[0];
    const manifest = fetched[1];
    const evidence = fetched[2];
    if (!catalog || !Array.isArray(catalog.robots) || !manifest) {
      stageError("The model catalog or simulation bundle is unavailable.");
      return;
    }
    state.catalog = catalog.robots;
    state.available = new Set((manifest.projects || []).flatMap((project) =>
      (project.scenes || []).map((scene) => scene.id)));
    state.evidence = evidence?.schema_version === 1 ? evidence : null;
    $("robot-total").textContent = String(state.catalog.length);
    $("force-total").textContent = String(Object.keys(state.evidence?.force_trials || {}).length);
    setCompareOptions();
    renderStats($("body-a").value, "a");
    renderStats($("body-b").value, "b");
    displayForces();
    displayP37();
    displayCrossBodyP37();
    startStage(state.selected);
  }

  function wire() {
    document.querySelectorAll("[data-scene]").forEach((button) =>
      button.addEventListener("click", () => {
        stopComparison({restoreStage: false});
        startStage(button.dataset.scene);
      })
    );
    $("stage-reset").addEventListener("click", () => {
      stopComparison({restoreStage: false});
      startStage(state.selected);
    });
    $("compare-run").addEventListener("click", launchComparison);
    $("compare-stop").addEventListener("click", () => stopComparison());
    for (const id of ["body-a", "body-b"]) {
      $(id).addEventListener("change", () => {
        renderStats($("body-a").value, "a");
        renderStats($("body-b").value, "b");
        if (state.comparisonActive) launchComparison();
      });
    }
    // Avoid leaving hidden high-cost WebGL simulations active after navigation.
    window.addEventListener("pagehide", () => {
      if (state.stageTimer) clearTimeout(state.stageTimer);
    });
  }

  wire();
  loadData();
})();