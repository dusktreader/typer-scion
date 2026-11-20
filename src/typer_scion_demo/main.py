"""
Main entry point for the typer-scion demo.
"""

from roadshow import Roadshow

import typer_scion_demo


def main():
    Roadshow(typer_scion_demo, title="typer-scion").run()


if __name__ == "__main__":
    main()
