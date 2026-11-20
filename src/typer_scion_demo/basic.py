"""
Basic demo functions for typer-scion.
"""

from roadshow import demo
from typer_scion import __version__


@demo("get version")
def demo_version():
    """
    This demo shows how to get the version of `typer-scion`.

    The version is available as a module-level variable.
    """
    print(f"typer-scion version: {__version__}")


@demo("hello world")
def demo_hello_world():
    """
    This demo shows a simple hello world example.

    This is a placeholder demo that you can replace with actual features.
    """
    print("Hello from typer-scion!")
    print("Replace this with your own demo functions.")
