# Setup

## Requirements

* Python 3.10–3.14 (for example via [pyenv](https://github.com/pyenv/pyenv#installation))
* uv: [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)
* Graphviz (only required for UML/doc generation):
    * macOS: `$ brew install graphviz`
    * Linux / Windows: [https://graphviz.org/download](https://graphviz.org/download/)

To confirm these system dependencies are configured correctly:

```text
$ ./bin/verchew
```

## Installation

Install project dependencies into a virtual environment:

```text
$ uv sync
```

Install the pre-commit hooks (run once per clone):

```text
$ uv run pre-commit install --install-hooks
```

# Development Tasks

## Manual

There is no automated test suite yet. Static checks are the primary safety net.

Docstrings follow the NumPy convention; the pre-commit hooks (docformatter and
Ruff) keep them consistent automatically.

```text
$ uv run ruff format aiomusiccast
$ uv run ruff check aiomusiccast
$ uv run mypy aiomusiccast --config-file=.mypy.ini
```

Build the documentation:

```text
$ uv run mkdocs build --clean --strict
```

## Automatic

Use your editor’s on-save hooks or a simple watcher such as `entr` to rerun the commands above, e.g.
`find aiomusiccast -name '*.py' | entr -r uv run ruff check aiomusiccast`.

You can also run the full hook suite manually:

```text
$ uv run pre-commit run --all-files
```

# Continuous Integration

CI runs the same Ruff and mypy checks defined above.

# Demo Tasks

Run the program:

```text
$ uv run python aiomusiccast/__main__.py
```

Launch an IPython session:

```text
$ uv run ipython --ipython-dir=notebooks
```

# Release Tasks

Release to PyPI:

```text
$ uv build
$ UV_PUBLISH_TOKEN=... uv publish
```
