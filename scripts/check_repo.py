"""Repository-level sanity checks that require no third-party dependencies."""

from pathlib import Path

REQUIRED = (
    "README.md",
    "pyproject.toml",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "docs/architecture.md",
    "docs/data-contract.md",
    "docs/safety.md",
    "docs/roadmap.md",
    "docs/language-architecture.md",
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
