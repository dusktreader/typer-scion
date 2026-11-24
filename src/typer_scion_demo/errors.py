"""
Demos of the errors raised when inheritance is configured incorrectly.
"""

from typing import Annotated

import typer
from roadshow import demo
from typer_scion import Inheritable, Inherited, ScionError, inherit


def attempt(app: typer.Typer, *args: str) -> None:
    """Run the app and report the `ScionError` it raises."""
    try:
        app(list(args), standalone_mode=False)
    except ScionError as err:
        print(f"{type(err).__name__}: {err}")


@demo("errors")
def demo_unknown_option():
    """
    Demonstrate UnknownInheritedOptionError

    A parameter marked `Inherited()` must match the name of an option that an ancestor marks `Inheritable()`. Here the
    parent shares `--level`, but the child asks for `depth`, so there is nothing to supply it.
    """
    app = typer.Typer()

    @app.callback()
    def parent(level: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @app.command()
    @inherit
    def child(depth: Annotated[int, Inherited()]): ...

    attempt(app, "child")


@demo("errors")
def demo_inherited_default():
    """
    Demonstrate InheritedDefaultError

    An `Inherited()` parameter takes its default from the ancestor's declaration, so it may not declare one itself.
    """
    app = typer.Typer()

    @app.callback()
    def parent(level: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @app.command()
    @inherit
    def child(level: Annotated[int, Inherited()] = 5): ...

    attempt(app, "child")


@demo("errors")
def demo_inheritable_on_command():
    """
    Demonstrate InheritableOnCommandError

    Options are shared downward through group callbacks only. A command's options are never visible to its siblings,
    so marking one `Inheritable()` on a command is rejected. Move the option to a group callback instead.
    """
    root, sub = typer.Typer(), typer.Typer()

    @root.callback()
    def r(): ...

    @sub.command()
    @inherit
    def child(level: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @sub.command()
    def other(): ...

    root.add_typer(sub, name="sub")
    attempt(root, "sub", "child")
