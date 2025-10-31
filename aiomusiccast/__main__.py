#!/usr/bin/env python

"""Package entry point."""


def main() -> None:
    """Abort because no command-line interface is provided."""
    raise SystemExit("aiomusiccast does not expose a CLI entry point.")


if __name__ == "__main__":  # pragma: no cover
    main()
