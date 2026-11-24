"""
Main entry point for the typer-scion demo.
"""

from roadshow import Roadshow

import typer_scion_demo


def main():
    Roadshow(
        typer_scion_demo,
        title="typer-scion",
        feature_order=["receiving", "values", "nesting", "errors"],
    ).run()


if __name__ == "__main__":
    main()
