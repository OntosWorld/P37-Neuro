/** P37 live MuJoCo observations. These are sampled from the physics engine
 * every control step (50 Hz); no keyframes or decorative animation are used.
 * The checkpoint is experimental and has no walking qualification.
 */
import { ObservationBase } from 'mjswan/observation';
import type { PolicyState } from 'mjswan/types';

type JointConfig = {
  name: string;
  count: number;
  default_pose: number[];
};
export class P37JointResidual extends ObservationBase<JointConfig> {
  get size(): number { return this.config.count * 2; }
  compute(state: PolicyState): Float32Array {
    const n = this.config.count;
    if (!state.jointPos || !state.jointVel ||
        state.jointPos.length !== n || state.jointVel.length !== n ||
        this.config.default_pose.length !== n) {
      throw new Error('P37 observation joint count mismatch: refusing unsafe inference');
    }
    const output = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      const q = state.jointPos[i] - this.config.default_pose[i];
      const dq = state.jointVel[i];
      if (!Number.isFinite(q) || !Number.isFinite(dq)) {
        throw new Error('P37 observed non-finite joint state');
      }
      output[2 * i] = q;
      output[2 * i + 1] = dq;
    }
    return output;
  }
}

type TaskConfig = {
  name: string;
  desired_velocity_x: number;
};
export class P37TaskContext extends ObservationBase<TaskConfig> {
  get size(): number { return 8; }
  compute(state: PolicyState): Float32Array {
    const v = state.rootLinVel;
    const q = state.rootQuat;
    if (!v || v.length < 3 || !q || q.length < 4) {
      throw new Error('P37 requires measured base linear velocity and orientation');
    }
    // Rotate world gravity (0,0,-1) into base coordinates. MuJoCo's free-body
    // quaternion is wxyz, and the gravity projection is computed in body frame.
    const [w,x,y,z] = q;
    const gx = 2 * (x*z - w*y);
    const gy = 2 * (y*z + w*x);
    const gz = 1 - 2 * (x*x + y*y);
    // Eight features: measured base v_xyz, gravity_xyz, desired vx, task flag.
    // This is the initial experimental task contract; it does not imply an
    // independently qualified imitation of the native training environment.
    const out = new Float32Array([
      v[0], v[1], v[2], -gx, -gy, -gz,
      this.config.desired_velocity_x, 0,
    ]);
    if (!out.every(Number.isFinite)) {
      throw new Error('P37 observed non-finite task context');
    }
    return out;
  }
}
