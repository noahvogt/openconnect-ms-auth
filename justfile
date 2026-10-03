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

# Bump the version from the commits since the last tag, update the changelog,
# commit and tag it. Extra arguments go to `cz bump`, e.g. `--increment PATCH`
# or an explicit version. Push with: git push --follow-tags
release *args: lint test
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "$(git status --porcelain)" ]; then
        echo "working tree is dirty" >&2
        exit 1
    fi
    # Hook environments installed from inside the commit can clobber its index
    # (npm's git clone of cspell inherits GIT_INDEX_FILE), so install them first.
    uv run pre-commit install-hooks
    uv run cz bump --yes {{args}}
    version="$(uv run cz version --project)"
    echo "Tagged v$version. Next: git push --follow-tags, let the release"
    echo "workflow pass, then bump and publish it from the pkgbuilds repo."
