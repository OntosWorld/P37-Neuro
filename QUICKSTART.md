# P37 Neuro Quickstart

This guide gets a new contributor or tester from a fresh clone to a verified local P37 Neuro installation.

P37 Neuro is currently distributed from source. The package is not yet published to PyPI.

## Requirements

Required for the Python core:

- Git;
- Python **3.12**;
- [uv](https://docs.astral.sh/uv/).

Required only for the C++ runtime checks:

- CMake;
- a C++20 compiler.

NVIDIA Isaac Lab, ROS 2, CUDA and TensorRT are optional integrations and are **not** required for the basic quickstart.

## 1. Clone the repository

```bash
git clone https://github.com/OntosWorld/P37-Neuro.git
cd P37-Neuro
```

## 2. Install the core development environment

```bash
uv sync --all-groups
```

This creates the local environment and installs the Python core plus development dependencies.

## 3. Verify the CLI

```bash
uv run p37-neuro info
```

Expected output starts with:

```text
P37 Neuro 0.4.0
Ontos World general-purpose robot intelligence program
```

## 4. Run the core Python tests

```bash
uv run pytest
```

For the complete repository quality gate, including the C++20 runtime:

```bash
make check
```

`make check` requires CMake and a C++20 compiler.

## 5. Run your first P37 learning experiment

The fastest useful learning-path check is the E1 CPU cross-morphology smoke experiment.

```bash
cd ml
uv sync --all-groups
uv run python -m p37_neuro_ml.e1_smoke \
  --epochs 8 \
  --output artifacts/quickstart-e1
```

Inspect the generated metrics:

```bash
cat artifacts/quickstart-e1/metrics.json
```

This experiment trains one small P37 checkpoint across several synthetic robot morphologies and evaluates it on held-out joint counts.

**Important:** this is a synthetic smoke test. It verifies that the cross-morphology learning path runs end to end; it is not physical-robot capability evidence.

## 6. Run the simulation package checks

From the repository root:

```bash
cd ../sim
uv sync --all-groups
uv run pytest -q
```

The simulation package contains the MuJoCo integration and the P37 Isaac Lab task/launcher interfaces. Isaac Lab itself is an optional external installation and requires a compatible NVIDIA environment.

## 7. Choose your next path

### Test P37 capability

Read [docs/testing.md](docs/testing.md).

It defines held-out embodiment and task rules, E1–E6 test procedures, MuJoCo and Isaac Lab qualification, required ablations, ROS 2 / TensorRT / hardware-in-the-loop testing, physical robot qualification and evidence/reporting requirements.

### Understand the system

Start with:

- [Product and Technical Overview](docs/overview.md)
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Documentation index](docs/README.md)

### Contribute

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Optional integrations

P37 keeps heavy integrations outside the core package.

### Data / LeRobot

```bash
uv sync --extra data
```

### MuJoCo from the root package

```bash
uv sync --extra sim
```

### Training dependency from the root package

```bash
uv sync --extra train
```

### Cloud release backends

```bash
uv sync --extra cloud
```

For the complete ML environment, use the dedicated `ml/` package as shown above.

## Safety

Do not connect an unqualified research policy directly to unrestricted physical actuators.

Physical integrations require independent emergency stops, controller-level limits, watchdogs and the staged qualification process in [docs/testing.md](docs/testing.md).
