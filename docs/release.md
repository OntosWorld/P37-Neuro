# Release Engineering

P37 publishes multiple artifacts because the research/control plane and real-time runtime have different deployment needs.

A tagged release produces:
- Python wheel and source distribution;
- native Linux x86_64 C++ runtime bundle containing headers and the static runtime library;
- SHA-256 checksums;
- SPDX JSON SBOM;
- GitHub artifact attestations;
- GitHub Release assets;
- a GHCR image containing the non-real-time `p37` CLI/control-plane package.

The OCI image is **not** the only actuator-runtime path. The deterministic C++ runtime remains available as a native artifact for host/controller integration.

## PyPI

Trusted PyPI publishing is prepared but opt-in. Configure PyPI Trusted Publishing for this repository and set:

```text
P37_PYPI_PUBLISH=true
```

Until that trust relationship is configured, tagged releases still publish GitHub artifacts and GHCR images without a PyPI token.

## Version discipline

A release tag must match the package version. Update `pyproject.toml`, `p37_neuro.__version__` and `CHANGELOG.md` together before tagging.

Capability evidence is released independently and must not be inferred from the software version.
