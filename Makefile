.PHONY: sync test lint format typecheck cpp-test check

sync:
	uv sync --all-groups

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy src

cpp-test:
	cmake -S runtime_cpp -B runtime_cpp/build
	cmake --build runtime_cpp/build --parallel
	ctest --test-dir runtime_cpp/build --output-on-failure

check: lint typecheck test cpp-test
