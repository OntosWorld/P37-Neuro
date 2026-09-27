# Research and Engineering Roadmap

## P37-E0 — Foundation

- [x] package skeleton
- [x] embodiment schema
- [x] observation/action/episode schema
- [x] policy interfaces
- [x] deterministic joint safety envelope
- [x] simulator protocol
- [ ] config loader + schema validation
- [ ] URDF importer
- [ ] MJCF importer
- [ ] USD importer
- [ ] RLDS importer
- [ ] episode serialization format
- [ ] deterministic replay harness
- [ ] experiment/checkpoint registry

## P37-E1 — Cross-morphology locomotion

- [ ] Isaac Lab environment family
- [ ] procedural morphology generator
- [ ] domain-randomization registry
- [ ] baseline PPO locomotion teacher
- [ ] cross-morphology policy
- [ ] long-context adaptation
- [ ] held-out-body benchmark
- [ ] payload / actuator-fault benchmark

## P37-E2 — Cross-embodiment manipulation

- [ ] public manipulation dataset adapters
- [ ] teleoperation ingestion
- [ ] action-space normalization
- [ ] single-arm baseline
- [ ] multi-arm / mobile-manipulator training
- [ ] cross-body transfer benchmark

## P37-E3 — Demonstration conditioning

- [ ] demonstration-video pipeline
- [ ] temporal visual encoder baseline
- [ ] demonstration/task context API
- [ ] one-shot task-composition benchmark

## P37-E4 — Long horizon

- [ ] recurrent task memory
- [ ] progress representation
- [ ] recovery policy curriculum
- [ ] multi-minute evaluation suite

## P37-E5 — RL post-training

- [ ] offline evaluation gate
- [ ] simulation RL post-training
- [ ] adversarial disturbance curriculum
- [ ] physical transfer gate

## P37-E6 — Data flywheel

- [ ] fleet episode logger
- [ ] automated quality scoring
- [ ] review queue
- [ ] dataset lineage
- [ ] model registry
- [ ] deployment promotion / rollback
