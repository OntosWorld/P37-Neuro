"""Repository-level sanity checks that require no third-party dependencies."""

from pathlib import Path

REQUIRED = (
    "README.md",
    "QUICKSTART.md",
    "LICENSE",
    "pyproject.toml",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "COMPATIBILITY.md",
    "CHANGELOG.md",
    "docs/README.md",
    "docs/overview.md",
    "docs/testing.md",
    "docs/architecture.md",
    "docs/enterprise-deployment.md",
    "docs/data-governance.md",
    "docs/observability.md",
    "docs/integration-kit.md",
    "docs/api-stability.md",
    "docs/quality-declaration.md",
    "docs/data-contract.md",
    "docs/safety.md",
    "docs/roadmap.md",
    "docs/language-architecture.md",
    "Dockerfile",
    "examples/README.md",
    "docs/release.md",
    "docs/supply-chain-security.md",
    ".github/workflows/security.yml",
    ".github/workflows/release.yml",
    "runtime_cpp/CMakeLists.txt",
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    missing = [path for path in REQUIRED if not (root / path).is_file()]
    if missing:
        raise SystemExit(f"missing required repository files: {missing}")
    print("repository structure: OK")


if __name__ == "__main__":
    main()
