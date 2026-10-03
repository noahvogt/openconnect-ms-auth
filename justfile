# Development and release tasks. The Arch package lives in the pkgbuilds repo
# (https://github.com/noahvogt/pkgbuilds), which is also where it is published
# to the AUR from, so that no SSH key has to live in CI.

set shell := ["bash", "-euo", "pipefail", "-c"]

# List the available recipes
default:
    @just --list

# Run the test suite
test:
    uv run pytest -q

# Check lint and formatting
lint:
    uv run ruff check ocma tests
    uv run ruff format --check ocma tests

# Bump the version, commit and tag it. Push with: git push --follow-tags
release new_version: lint test
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "$(git status --porcelain)" ]; then
        echo "working tree is dirty" >&2
        exit 1
    fi
    uv version "{{new_version}}"
    git add pyproject.toml uv.lock
    git commit -m "chore(release): {{new_version}}"
    git tag -a "v{{new_version}}" -m "v{{new_version}}"
    echo "Tagged v{{new_version}}. Next: git push --follow-tags, let the package"
    echo "workflow pass, then bump and publish it from the pkgbuilds repo."
