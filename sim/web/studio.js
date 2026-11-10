/* P37 Brain Lab — physical scene catalog, navigation and research evidence.
   No scripted locomotion: the iframe executes the real MuJoCo simulation. */
(() => {
  "use strict";

  const dom = (id) => document.getElementById(id);
  const state = {
    robots: [],
    selected: null,
    available: new Set(),
    manifestReady: false,
    category: "All",
    controlsOpen: false,
    inspector: "scene",
    drawer: null,
    frameVersion: 0,
    frameTimeout: null,
    toastTimeout: null
  };

  const categories = {
    Humanoids: "HU",
    Quadrupeds: "QD",
    Manipulators: "AR",
    Mobile: "MB",
    Aerial: "DR"
  };

  const details = {
    Humanoids: "Inspect joint articulation, gravity and upright stability. Push the physical model and watch the contact response. This viewer does not run a P37 walking controller.",
    Quadrupeds: "Four-legged contact mechanics, gravity and force response. Drag the simulated body to test its physical response; learned recovery is not enabled.",
    Manipulators: "Explore articulated robot-arm geometry, joint limits and simulated contacts. This viewer does not have a trained grasping policy.",
    Mobile: "Inspect the physical coupling between a wheeled base and articulated manipulator. Autonomous navigation is not enabled.",
    Aerial: "Explore the drone's physical rigid-body state and free motion. No trained flight controller is attached."
  };

  const offlineFallback = [
    {id:"unitree_g1", name:"Unitree G1",model:"unitree_g1",kind:"Humanoids",short:"29-DoF humanoid",capability:"Whole-body balance",task:"Balance under perturbation"},
    {id:"unitree_go2",name:"Unitree Go2",model:"unitree_go2",kind:"Quadrupeds",short:"12-DoF quadruped",capability:"Contact dynamics",task:"External-force challenge"},
    {id:"franka_panda",name:"Franka Panda",model:"franka_emika_panda",kind:"Manipulators",short:"7-axis robot arm",capability:"Grasping research",task:"Contact and interaction"}
  ];

  // Keep the real-time canvas unobstructed by default.
  // Drawers are modal interactions, never permanent columns.
  let focusBeforeDrawer = null;

  function closeDrawers({restoreFocus = true} = {}) {
    const wasOpen = Boolean(state.drawer);
    state.drawer = null;
    for (const id of ["robot-library-panel", "inspector"]) {
      const panel = dom(id);
      panel.classList.remove("open");
      panel.inert = true;
      panel.setAttribute("aria-hidden", "true");
    }
    for (const id of ["toggle-library", "browse-models", "toggle-inspector"]) {
      dom(id).setAttribute("aria-expanded", "false");
    }
    dom("surface-scrim").hidden = true;
    document.body.classList.remove("drawer-open");
    if (restoreFocus && wasOpen && focusBeforeDrawer?.isConnected) {
      focusBeforeDrawer.focus({preventScroll: true});
    }
    focusBeforeDrawer = null;
  }

  function openDrawer(name) {
    if (state.drawer === name) {
      closeDrawers();
      return;
    }
    if (!state.drawer) focusBeforeDrawer = document.activeElement;
    state.drawer = name;
    const library = name === "library";
    dom("robot-library-panel").classList.toggle("open", library);
    dom("inspector").classList.toggle("open", !library);
    dom("robot-library-panel").inert = !library;
    dom("inspector").inert = library;
    dom("robot-library-panel").setAttribute("aria-hidden", String(!library));
    dom("inspector").setAttribute("aria-hidden", String(library));
    dom("toggle-library").setAttribute("aria-expanded", String(library));
    dom("browse-models").setAttribute("aria-expanded", String(library));
    dom("toggle-inspector").setAttribute("aria-expanded", String(!library));
    dom("surface-scrim").hidden = false;
    document.body.classList.add("drawer-open");
    if (library) dom("robot-library").scrollTop = 0;
    (library ? dom("close-library") : dom("close-inspector")).focus({preventScroll: true});
  }

  function escapeForText(value) {
    return String(value ?? "");
  }

  function showToast(message) {
    const el = dom("toast");
    el.textContent = message;
    el.hidden = false;
    if (state.toastTimeout) clearTimeout(state.toastTimeout);
    state.toastTimeout = setTimeout(() => { el.hidden = true; }, 3200);
  }

  function externalModelUrl(robot) {
    return "https://live.mujoco.org/?model=github:google-deepmind/mujoco_menagerie/main/" +
      encodeURIComponent(robot.model) + "/scene.xml";
  }

  function setEngineStatus(message, type) {
    dom("engine-state").textContent = message;
    dom("engine-dot").className = "engine-dot" + (type ? " " + type : "");
  }

  function sceneUrl(robot) {
    const search = new URLSearchParams({
      project: "p37_robot_models",
      scene: robot.id,
      panel: state.controlsOpen ? "1" : "0"
    });
    return "./simulator/?" + search.toString();
  }

  function drawLibrary() {
    const list = dom("robot-library");
    list.replaceChildren();
    const filtered = state.robots.filter((robot) => state.category === "All" || robot.kind === state.category);
    for (let i = 0; i < filtered.length; ++i) {
      const robot = filtered[i];
      const button = document.createElement("button");
      button.type = "button";
      button.className = "robot-option";
      button.dataset.robot = robot.id;
      button.setAttribute("aria-pressed", String(robot.id === state.selected?.id));
      button.setAttribute("aria-label", "Load " + robot.name + " physics simulation");

      const icon = document.createElement("span");
      icon.className = "robot-emblem";
      icon.textContent = categories[robot.kind] || "RB";

      const content = document.createElement("span");
      const title = document.createElement("strong");
      title.textContent = robot.name;
      const short = document.createElement("small");
      short.textContent = robot.short;
      content.append(title, short);
      const arrow = document.createElement("span");
      arrow.className = "robot-arrow";
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = "↗";
      button.append(icon, content, arrow);
      button.addEventListener("click", () => selectRobot(robot.id));
      list.append(button);
    }
    if (!filtered.length) {
      const empty = document.createElement("p");
      empty.className = "no-models";
      empty.textContent = "No models available in this category.";
      list.append(empty);
    }
  }

  function drawSelectedRobot(robot) {
    const index = state.robots.findIndex((candidate) => candidate.id === robot.id);
    dom("crumb-robot").textContent = robot.name.toUpperCase();
    dom("scene-number").textContent = String(index + 1).padStart(2, "0") + " / " + String(state.robots.length).padStart(2, "0");
    dom("scene-badge").textContent = "Model-only physics";
    dom("scene-title").textContent = robot.name;
    dom("scene-subtitle").textContent = robot.short;
    dom("inspector-name").textContent = robot.name;
    dom("inspector-description").textContent = escapeForText(robot.capability) + ". " +
      "Interactive physical simulation using the upstream robot model.";
    dom("inspector-kind").textContent = robot.kind;
    dom("task-title").textContent = robot.task;
    dom("task-detail").textContent = details[robot.kind] || "Explore the real physics model.";
    dom("dock-title").textContent = robot.name + " / physics";
    dom("dock-description").textContent = "Actual rigid-body contacts, gravity and articulated joints";
    dom("inspector-controller").textContent = "Model-only";
    dom("fallback-link").href = externalModelUrl(robot);
    document.title = robot.name + " — P37 Brain Lab";
  }

  function showFallback(message) {
    if (state.frameTimeout) clearTimeout(state.frameTimeout);
    dom("scene-loading").hidden = true;
    dom("sim").hidden = true;
    dom("scene-fallback").hidden = false;
    dom("fallback-detail").textContent = message;
    setEngineStatus("MODEL UNAVAILABLE", "error");
  }

  function loadScene(robot) {
    const version = ++state.frameVersion;
    const frame = dom("sim");
    dom("scene-fallback").hidden = true;
    dom("scene-loading").hidden = false;
    dom("loading-title").textContent = "Loading " + robot.name;
    dom("loading-caption").textContent = "Preparing actual mesh, joints and physics";
    setEngineStatus("LOADING MODEL", "");
    if (state.frameTimeout) clearTimeout(state.frameTimeout);

    if (!state.manifestReady || !state.available.has(robot.id)) {
      showFallback("The compiled scene is not included in this build. Open the official MuJoCo viewer to inspect the same robot model.");
      return;
    }

    frame.hidden = false;
    frame.onload = () => {
      if (version !== state.frameVersion) return;
      if (state.frameTimeout) clearTimeout(state.frameTimeout);
      dom("scene-loading").hidden = true;
      setEngineStatus("SCENE LOADED", "ready");
    };
    frame.onerror = () => {
      if (version === state.frameVersion) {
        showFallback("The embedded simulator could not load. The official robot scene is available in MuJoCo Live.");
      }
    };
    frame.src = sceneUrl(robot);
    state.frameTimeout = setTimeout(() => {
      if (version === state.frameVersion && !dom("scene-loading").hidden) {
        showFallback("This browser could not load the MuJoCo scene. Check WebAssembly/WebGL support or use the official viewer.");
      }
    }, 120000);
  }

  function selectRobot(id, updateHistory = true) {
    const robot = state.robots.find((item) => item.id === id);
    if (!robot) return;
    state.selected = robot;
    drawSelectedRobot(robot);
    drawLibrary();
    if (updateHistory) {
      const url = new URL(window.location.href);
      url.searchParams.set("robot", robot.id);
      history.replaceState(null, "", url);
    }
    closeDrawers();
    loadScene(robot);
  }

  function setCategory(category) {
    state.category = category;
    document.querySelectorAll("[data-category]").forEach((button) => {
      const selected = button.dataset.category === category;
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    drawLibrary();
  }

  function setInspector(tab) {
    state.inspector = tab;
    const evidence = tab === "p37";
    dom("tab-scene").classList.toggle("selected", !evidence);
    dom("tab-p37").classList.toggle("selected", evidence);
    dom("tab-scene").setAttribute("aria-selected", String(!evidence));
    dom("tab-p37").setAttribute("aria-selected", String(evidence));
    dom("panel-scene").hidden = evidence;
    dom("panel-p37").hidden = !evidence;
    if (state.drawer !== "inspector") openDrawer("inspector");
  }

  async function loadEvidence() {
    const holder = dom("evidence-trials");
    try {
      const response = await fetch("./p37-evidence.json", {cache:"no-store"});
      if (!response.ok) throw new Error("Missing evidence file");
      const report = await response.json();
      if (report.qualification !== "unqualified" || !Array.isArray(report.evaluation?.seeds)) {
        throw new Error("Invalid research evidence schema");
      }
      holder.replaceChildren();
      for (const trial of report.evaluation.seeds) {
        const row = document.createElement("div");
        row.className = "trial-row";
        const left = document.createElement("div");
        const label = document.createElement("span");
        label.className = "trial-seed";
        label.textContent = "SEED " + trial.seed;
        const note = document.createElement("small");
        note.textContent = Number(trial.sim_seconds).toFixed(2) + " s · " +
          Number(trial.final_velocity_m_s).toFixed(2) + " m/s final velocity";
        left.append(label, note);
        const status = document.createElement("span");
        status.className = "trial-outcome" + (trial.fallen ? "" : " survived");
        status.textContent = trial.fallen ? "FELL" : "HORIZON";
        row.append(left, status);
        holder.append(row);
      }
      dom("onnx-error").textContent = Number(report.onnx.max_action_abs_error).toExponential(2);
      dom("evidence-link").href = report.provenance.onnx_workflow;
    } catch {
      holder.textContent = "Trial evidence could not be verified or loaded.";
      dom("onnx-error").textContent = "Unavailable";
    }
  }

  async function initialize() {
    document.querySelectorAll("[data-category]").forEach((button) => {
      button.addEventListener("click", () => setCategory(button.dataset.category));
    });
    dom("tab-scene").addEventListener("click", () => setInspector("scene"));
    dom("tab-p37").addEventListener("click", () => setInspector("p37"));
    dom("toggle-inspector").addEventListener("click", () => {
      if (state.drawer === "inspector") closeDrawers();
      else setInspector("p37");
    });
    dom("toggle-library").addEventListener("click", () => openDrawer("library"));
    dom("browse-models").addEventListener("click", () => openDrawer("library"));
    dom("close-library").addEventListener("click", () => closeDrawers());
    dom("close-inspector").addEventListener("click", () => closeDrawers());
    dom("surface-scrim").addEventListener("click", () => closeDrawers());
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && state.drawer) {
        event.preventDefault();
        closeDrawers();
      }
      if (event.key === "Tab" && state.drawer) {
        const panel = dom(state.drawer === "library" ? "robot-library-panel" : "inspector");
        const focusables = [...panel.querySelectorAll('button:not([disabled]),a[href]')]
          .filter((element) => element.getClientRects().length);
        if (!focusables.length) return;
        const first = focusables[0], last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    });
    dom("reset").addEventListener("click", () => {
      if (state.selected) { loadScene(state.selected); showToast("Simulation reset"); }
    });
    dom("toggle-engine").addEventListener("click", () => {
      state.controlsOpen = !state.controlsOpen;
      dom("toggle-engine").setAttribute("aria-pressed", String(state.controlsOpen));
      if (state.selected) loadScene(state.selected);
      showToast(state.controlsOpen ? "Simulator controls visible" : "Scene controls simplified");
    });
    dom("fullscreen").addEventListener("click", async () => {
      try {
        const stage = document.querySelector(".simulation-column");
        if (document.fullscreenElement) await document.exitFullscreen();
        else await stage.requestFullscreen();
      } catch { showToast("Fullscreen unavailable in this browser"); }
    });
    dom("copy-scene").addEventListener("click", async () => {
      if (!state.selected) return;
      const url = new URL(location.href);
      url.searchParams.set("robot", state.selected.id);
      try {
        await navigator.clipboard.writeText(url.toString());
        showToast("Link copied to clipboard");
      } catch { showToast("Copy unavailable — use the address bar"); }
    });

    const [catalogResponse, manifestResponse] = await Promise.allSettled([
      fetch("./catalog.json", {cache:"no-store"}),
      fetch("./simulator/manifest.json", {cache:"no-store"})
    ]);
    try {
      if (catalogResponse.status !== "fulfilled" || !catalogResponse.value.ok) throw new Error();
      const catalog = await catalogResponse.value.json();
      if (!Array.isArray(catalog.robots) || !catalog.robots.length) throw new Error();
      state.robots = catalog.robots;
    } catch {
      state.robots = offlineFallback;
    }
    try {
      if (manifestResponse.status !== "fulfilled" || !manifestResponse.value.ok) throw new Error();
      const manifest = await manifestResponse.value.json();
      state.available = new Set((manifest.projects || []).flatMap((project) =>
        (project.scenes || []).map((scene) => scene.id)
      ));
      state.manifestReady = state.available.size > 0;
    } catch {
      state.manifestReady = false;
    }

    dom("robot-count").textContent = String(state.robots.length).padStart(2, "0") + " models";
    dom("top-robot-count").textContent = String(state.robots.length);
    const requested = new URLSearchParams(location.search).get("robot");
    const first = state.robots.find((robot) => robot.id === requested) || state.robots[0];
    if (first) selectRobot(first.id, Boolean(requested));
    await loadEvidence();
  }

  initialize();
})();
