/* P37 physical steering bridge for the real MuJoCo WebAssembly runtime.
 *
 * Unlike a fake 3D translation, user input applies a bounded external wrench
 * to the real floating base, so collisions, contacts, inertia, and gravity
 * remain under MuJoCo. This is an *assisted physics sandbox*, never a trained
 * gait or a claim that the ONNX policy was conditioned on WASD.
 *
 * Parent messages are accepted ONLY from the same origin and the parent frame.
 */
(() => {
  'use strict';
  const KEYS = Object.freeze(['forward', 'back', 'left', 'right', 'turnLeft', 'turnRight']);
  const input = Object.fromEntries(KEYS.map(key => [key, false]));
  let selectedBody = -1;
  let lastModel = null;
  let totalMass = 1;
  let readyReported = false;
  let frame = 0;
  let priorPosition = null;
  let originPosition = null;
  const robot = new URLSearchParams(window.location.search).get('scene') || '';

  function send(payload) {
    if (window.parent === window) return;
    window.parent.postMessage({ type: 'p37:telemetry', robot, ...payload }, window.location.origin);
  }

  function resetInputs() {
    for (const key of KEYS) input[key] = false;
  }

  window.addEventListener('message', event => {
    if (event.source !== window.parent || event.origin !== window.location.origin) return;
    const message = event.data;
    if (!message || message.type !== 'p37:steering') return;
    if (message.robot !== robot) return;
    if (message.action === 'release') {
      resetInputs();
      return;
    }
    if (message.action === 'input' && KEYS.includes(message.key) &&
        typeof message.down === 'boolean') {
      input[message.key] = message.down;
    }
  });

  function locateBase(model) {
    const jointType = model.jnt_type;
    const jointBody = model.jnt_bodyid;
    if (!jointType || !jointBody) return -1;
    // mujoco.mjtJoint.mjJNT_FREE == 0. The floating base belongs to the real
    // model body. Never apply fake translation to a fixed industrial arm.
    for (let j = 0; j < model.njnt; j++) {
      if (jointType[j] === 0 && jointBody[j] > 0) return jointBody[j];
    }
    return -1;
  }

  function tick() {
    requestAnimationFrame(tick);
    const engine = window.__p37Engine;
    const runtime = engine && engine.runtime;
    const model = runtime && runtime.mjModel;
    const data = runtime && runtime.mjData;
    if (!model || !data || !data.xfrc_applied) return;
    if (model !== lastModel) {
      lastModel = model;
      selectedBody = locateBase(model);
      totalMass = Math.max(0.1, Array.from(model.body_mass || []).reduce(
        (sum, value) => sum + Math.max(0, Number(value) || 0), 0
      ));
      readyReported = false;
      priorPosition = null;
      originPosition = null;
      resetInputs();
    }
    if (selectedBody < 0) {
      if (!readyReported) {
        send({ status: 'fixed', controllable: false,
          message: 'Fixed-base robot: joint motion only; it cannot walk or drive.' });
        readyReported = true;
      }
      return;
    }
    const body = selectedBody;
    const force = data.xfrc_applied;
    const index = body * 6;
    if (index + 5 >= force.length) return;

     const orient = data.xmat;
    const ori = body * 9;
    const headingX = orient ? orient[ori] : 1;
    const headingY = orient ? orient[ori + 3] : 0;
    const forward = Number(input.forward) - Number(input.back);
    const sideways = Number(input.left) - Number(input.right);
    const turn = Number(input.turnLeft) - Number(input.turnRight);
    const length = Math.max(1, Math.hypot(forward, sideways));
    const x = (headingX * forward - headingY * sideways) / length;
    const y = (headingY * forward + headingX * sideways) / length;
    const wantedVelocity = 0.65; // m/s; physics outcome is not guaranteed
    const qvel = data.qvel;
    // Floating-base velocity comes from the MuJoCo qvel address, not the camera.
    let bodyJoint = -1;
    for (let j = 0; j < model.njnt; j++) {
      if (model.jnt_type[j] === 0 && model.jnt_bodyid[j] === body) {
        bodyJoint = j;
        break;
      }
    }
    const veladr = bodyJoint >= 0 ? model.jnt_dofadr[bodyJoint] : -1;
    const vx = veladr >= 0 ? Number(qvel[veladr]) || 0 : 0;
    const vy = veladr >= 0 ? Number(qvel[veladr + 1]) || 0 : 0;
    // Use bounded body-frame locomotion assistance. We write the REAL MuJoCo
    // external force vector, so contact dynamics, gravity and inertia still run.
    // The force is proportional to body mass and resists sliding when released.
    const accelerating = forward !== 0 || sideways !== 0;
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    // Account for the mass of the complete robot, not only its torso link.
    // Otherwise the force cannot overcome the floor friction on a quadruped.
    const gain = 18 * totalMass;
    const maxForce = 15 * totalMass;
    force[index] = clamp(((accelerating ? x * wantedVelocity : 0) - vx) * gain,
      -maxForce, maxForce);
    force[index + 1] = clamp(((accelerating ? y * wantedVelocity : 0) - vy) * gain,
      -maxForce, maxForce);
    // Preserve model dynamics: no vertical supporting force or anti-fall clamp.
    force[index + 2] = 0;
    force[index + 3] = 0;
    force[index + 4] = 0;
    const yawV = veladr >= 0 ? Number(qvel[veladr + 5]) || 0 : 0;
    force[index + 5] = clamp((turn * 0.65 - yawV) * 1.5 * totalMass,
      -2.5 * totalMass, 2.5 * totalMass);

    if (!readyReported) {
      send({ status: 'ready', controllable: true,
        message: 'Assisted steering uses physical external forces on the floating base.' });
      readyReported = true;
    }
    frame++;
    if (frame % 8 !== 0) return;
    const pos = data.xpos;
    if (!pos || pos.length <= body * 3 + 2) return;
    const xyz = [
      Number(pos[body * 3]) || 0,
      Number(pos[body * 3 + 1]) || 0,
      Number(pos[body * 3 + 2]) || 0,
    ];
    if (!originPosition) originPosition = xyz;
    const dx = xyz[0] - originPosition[0];
    const dy = xyz[1] - originPosition[1];
    const distance = Math.hypot(dx, dy);
    const moved = priorPosition ? Math.hypot(
      xyz[0] - priorPosition[0], xyz[1] - priorPosition[1]) : 0;
    priorPosition = xyz;
    send({ status: 'running', controllable: true,
      x: xyz[0], y: xyz[1], z: xyz[2],
      distance: Number(distance.toFixed(3)), moved: Number(moved.toFixed(4)),
      steering: accelerating || turn !== 0 });
  }

  requestAnimationFrame(tick);
})();
