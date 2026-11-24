"""
Demos of how values travel between a child command and the parent callback that declared the option.
"""

from typing import Annotated

import typer
from roadshow import demo
from typer_scion import Inheritable, Inherited, inherit


@demo("values")
def demo_ascend():
    """
    Demonstrate a child's value ascending to the parent

    Tagging the option `Inheritable()` makes a value given to the child travel back up to the parent.
    Once the child's options are parsed, the parent callback is called again with the child's value.

    The parent callback runs twice here: first with the default, then with `True`. Keep such callbacks idempotent,
    which is natural for configuration like logging.
    """
    app = typer.Typer()

    @app.callback()
    def parent(verbose: Annotated[bool, typer.Option(), Inheritable()] = False):
        print(f"parent sees verbose={verbose}")

    @app.command()
    @inherit
    def child(verbose: Annotated[bool, Inherited()]):
        print(f"child sees verbose={verbose}")

    app(["child", "--verbose"])


@demo("values")
def demo_parent_value():
    """
    Demonstrate a child seeing the parent's value

    A value written before the subcommand is parsed by the parent. The child's own default does not hide it: the
    child sees the parent's effective value.

    Nothing ascends here, because the child was not given the option. The parent callback runs only once.
    """
    app = typer.Typer()

    @app.callback()
    def parent(verbose: Annotated[bool, typer.Option(), Inheritable()] = False):
        print(f"parent sees verbose={verbose}")

    @app.command()
    @inherit
    def child(verbose: Annotated[bool, Inherited()]):
        print(f"child sees verbose={verbose}")

    app(["--verbose", "child"])


@demo("values")
def demo_child_wins():
    """
    Demonstrate a child's explicit value ascending over the parent's

    If the option is given to both, the value written on the child is the one that ascends. The parent callback runs
    first with its own value, then again with the child's.

    This makes the most specific value the final one, so the parent ends up configured the way the child asked.
    """
    app = typer.Typer()

    @app.callback()
    def parent(verbose: Annotated[bool, typer.Option(), Inheritable()] = False):
        print(f"parent sees verbose={verbose}")

    @app.command()
    @inherit
    def child(verbose: Annotated[bool, Inherited()]):
        print(f"child sees verbose={verbose}")

    app(["--verbose", "child", "--no-verbose"])
