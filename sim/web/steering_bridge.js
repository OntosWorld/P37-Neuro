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
  let baseQposAddress = -1;
  let lastModel = null;
  let totalMass = 1;
  let readyReported = false;
  let frame = 0;
  let priorPosition = null;
  let originPosition = null;
  let measuredJoint = -1;
  let jointOrigin = null;
  let scriptedRun = false;
  let scriptedStart = null;
  let stableFrames = 0;
  // Browser task evidence is derived from real MuJoCo free-joint state.
  // Native Python qualification separately verifies finger/cube contact.
  let pandaSequence = { lifted: false, carried: false, released: false, completed: false };
  const TERRAIN = Object.freeze({unitree_go2: 1.7, anymal_c: 1.6});
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
      if (message.down) { scriptedRun = false; scriptedStart = null; }
    }
    if (message.type === 'p37:steering' && message.action === 'start-task'
        && Object.prototype.hasOwnProperty.call(TERRAIN, robot)) {
      resetInputs(); scriptedRun = true; scriptedStart = null; stableFrames = 0;
    }
    if (message.type === 'p37:steering' && message.action === 'stop-task') {
      scriptedRun = false; scriptedStart = null;
    }
  });

  // Keyboard input must work even when the MuJoCo canvas has focus.
  // The parent handles keys while its controls are focused; this bridge
  // handles the same keys while the viewer iframe receives keyboard events.
  const keymap = {
    w: 'forward', ArrowUp: 'forward', s: 'back', ArrowDown: 'back',
    a: 'left', ArrowLeft: 'left', d: 'right', ArrowRight: 'right',
    q: 'turnLeft', e: 'turnRight',
  };
  for (const eventName of ['keydown', 'keyup']) {
    window.addEventListener(eventName, event => {
      const target = event.target;
      if (target instanceof Element && target.closest(
        'input, select, textarea, [contenteditable="true"]')) return;
      const key = keymap[event.key] || keymap[event.key.toLowerCase()];
      if (!key) return;
      event.preventDefault();
      input[key] = eventName === 'keydown';
    });
  }
  window.addEventListener('blur', resetInputs);

  function locateBase(model) {
    const jointType = model.jnt_type;
    const jointBody = model.jnt_bodyid;
    if (!jointType || !jointBody) return -1;
    // mujoco.mjtJoint.mjJNT_FREE == 0. The floating base belongs to the real
    // model body. Never apply fake translation to a fixed industrial arm.
    if (robot === 'franka_panda' || robot === 'universal_robots_ur5e') return -1;
    for (let j = 0; j < model.njnt; j++) {
      if (jointType[j] === 0 && jointBody[j] > 0) return jointBody[j];
    }
    return -1;
  }

  function freeBodies(model, data) {
    const found = [];
    for (let j=0; j<model.njnt; j++) {
      if (model.jnt_type[j] !== 0) continue;
      const adr = model.jnt_qposadr[j];
      if (adr < 0 || adr + 2 >= data.qpos.length) continue;
      const xyz = [0,1,2].map(i => Number(data.qpos[adr+i]));
      if (xyz.every(Number.isFinite)) found.push(xyz);
    }
    return found;
  }

  function taskObservation(model, data) {
    if (robot !== 'franka_panda' && robot !== 'hello_robot_stretch') return {};
    const free = freeBodies(model, data);
    if (robot === 'franka_panda' && free.length >= 2) {
      // Two cubes were added, in order, after the factory Panda model.
      const [blue, amber] = free;
      const offset = Math.hypot(blue[0] - amber[0], blue[1] - amber[1]);
      const gap = blue[2] - amber[2];
      // A geometrically aligned cube in midair is not a settled stack.
      // Require the source gripper to be open and both free-body velocities
      // to be near zero in the real MuJoCo state over repeated frames.
      const jawOpen = data.qpos && Number(data.qpos[7]) >= 0.035;
      const velocities = data.qvel ? Array.from(data.qvel).slice(-12) : [];
      const objectsStill = velocities.length === 12 &&
        Math.hypot(...velocities.map(v => Number(v) || 0)) < 0.16;
      // Require an observed, ordered physical sequence, not merely two cubes
      // being close together (which could happen after a manual disturbance).
      const liftedNow = blue[2] >= 0.67;
      const transportedNow = blue[1] >= 0.045 && blue[2] >= 0.64;
      if (liftedNow && !jawOpen) pandaSequence.lifted = true;
      if (pandaSequence.lifted && transportedNow && !jawOpen) pandaSequence.carried = true;
      if (pandaSequence.carried && jawOpen && blue[1] >= 0.045) pandaSequence.released = true;
      const validStack = offset <= 0.050 && gap >= 0.052 && gap <= 0.085
        && blue[2] >= 0.62 && amber[2] >= 0.55 &&
        jawOpen && objectsStill && pandaSequence.released;
      stableFrames = validStack ? stableFrames + 1 : 0;
      pandaSequence.completed = stableFrames >= 20;
      return { taskKind: 'cube-stack', objectDistance: Number(offset.toFixed(4)),
        stackHeight: Number(gap.toFixed(4)), stackStable: pandaSequence.completed,
        taskLiftObserved: pandaSequence.lifted,
        taskCarryObserved: pandaSequence.carried,
        taskReleaseObserved: pandaSequence.released,
        taskSequenceComplete: pandaSequence.completed,
        observedObjects: 2,
        bluePosition: blue.map(v => Number(v.toFixed(3))),
        amberPosition: amber.map(v => Number(v.toFixed(3))) };
    }
    if (robot === 'hello_robot_stretch' && free.length >= 2) {
      // Official Stretch scene has a native, independently moving object.
      // The robot base is the first free joint; the source object is last.
      const object = free[free.length - 1];
      const goal = [0.72,0.55,0.48];
      const distance = Math.hypot(object[0]-goal[0],object[1]-goal[1]);
      const delivered = distance < 0.19 && object[2] > 0.445 && object[2] < 0.56;
      stableFrames = delivered ? stableFrames + 1 : 0;
      return { taskKind: 'object-delivery', objectDistance: Number(distance.toFixed(4)),
        objectDelivered: stableFrames >= 20, observedObjects: 1,
        objectPosition: object.map(v => Number(v.toFixed(3))) };
    }
    return { taskKind: 'unavailable', observedObjects: free.length };
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
      baseQposAddress = -1;
      for (let joint = 0; joint < model.njnt; joint++) {
        if (model.jnt_type[joint] === 0 &&
            model.jnt_bodyid[joint] === selectedBody) {
          baseQposAddress = model.jnt_qposadr[joint];
          break;
        }
      }
      totalMass = Math.max(0.1, Array.from(model.body_mass || []).reduce(
        (sum, value) => sum + Math.max(0, Number(value) || 0), 0
      ));
      readyReported = false;
      priorPosition = null;
      originPosition = null;
      jointOrigin = null;
      measuredJoint = -1;
      for (let j = 0; j < model.njnt; j++) {
        // MuJoCo hinge joint type is 3; never substitute a free-base pose.
        if (model.jnt_type[j] === 3) { measuredJoint = j; break; }
      }
      frame = 0;
      scriptedRun = false; scriptedStart = null; stableFrames = 0;
      pandaSequence = { lifted: false, carried: false, released: false, completed: false };
      resetInputs();
    }
    if (selectedBody < 0) {
      frame++;
      if (!readyReported || frame % 8 === 0) {
        const address = measuredJoint < 0 ? -1 : model.jnt_qposadr[measuredJoint];
        const angle = address >= 0 ? Number(data.qpos[address]) : NaN;
        if (Number.isFinite(angle) && jointOrigin === null) jointOrigin = angle;
        send({ status: 'fixed', controllable: false,
          jointDelta: Number.isFinite(angle) && jointOrigin !== null
            ? Number(Math.abs(angle - jointOrigin).toFixed(5)) : undefined,
          jointName: 'Hinge ' + Math.max(1, measuredJoint + 1),
          taskTime: Number((Number(data.time) || 0).toFixed(2)),
          message: 'Measured native hinge motion; fixed arm cannot walk or drive.',
          ...taskObservation(model, data) });
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
    let x = (headingX * forward - headingY * sideways) / length;
    let y = (headingY * forward + headingX * sideways) / length;
    if (scriptedRun && Object.prototype.hasOwnProperty.call(TERRAIN, robot)
        && baseQposAddress >= 0) {
      const progressX = Number(data.qpos[baseQposAddress]);
      const progressY = Number(data.qpos[baseQposAddress + 1]);
      if (scriptedStart === null) scriptedStart = Number(data.time) || 0;
      const elapsed = (Number(data.time) || 0) - scriptedStart;
      if (elapsed > 18 || progressX >= TERRAIN[robot] + 0.05) {
        scriptedRun = false;
      } else {
        // A reference controller drives horizontal force only. It cannot
        // teleport the body, cancel gravity, attach objects or create a gait.
        // Crossing or failing is determined by real collision dynamics.
        x = Math.max(-1,Math.min(1,(TERRAIN[robot] - progressX)*1.4));
        y = Math.max(-0.50,Math.min(0.50,-progressY*1.1));
      }
    }
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
    const accelerating = scriptedRun || forward !== 0 || sideways !== 0;
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
    // Send an initial position immediately, and sample every rendered frame
    // while the user is steering. Metal/headless renderers may run below 8 fps.
    if (frame !== 1 && frame % 8 !== 0 && !accelerating && turn === 0) return;
    // A free joint's qpos address holds the actual world position [x,y,z].
    // Do not depend on derived render-body xpos buffers, which can be absent
    // or delayed on headless Metal/GPU builds.
    const pos = data.qpos;
    const indexPosition = baseQposAddress;
    if (!pos || indexPosition < 0 || pos.length <= indexPosition + 2) return;
    const xyz = [
      Number(pos[indexPosition]) || 0,
      Number(pos[indexPosition + 1]) || 0,
      Number(pos[indexPosition + 2]) || 0,
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
      relativeX: Number(dx.toFixed(4)), relativeY: Number(dy.toFixed(4)),
      relativeZ: Number((xyz[2] - originPosition[2]).toFixed(4)),
      distance: Number(distance.toFixed(3)), moved: Number(moved.toFixed(4)),
      steering: accelerating || turn !== 0,
      scriptedTaskRunning: scriptedRun,
      scriptedTaskElapsed: scriptedStart===null ? 0 :
        Number(Math.max(0,(Number(data.time)||0)-scriptedStart).toFixed(2)),
      ...taskObservation(model, data) });
  }

  requestAnimationFrame(tick);
})();
