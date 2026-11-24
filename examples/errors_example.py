"""
Errors: each way of misconfiguring inheritance raises its own subclass of `ScionError`.

Every case builds a small app, runs it, and prints the error that results. All of them derive from `ScionError`, so
a single `except ScionError` catches any of them.

The script makes one invocation per error.
"""

from typing import Annotated

import typer
from typer_scion import Inheritable, Inherited, ScionError, inherit


def attempt(app: typer.Typer, *args: str) -> None:
    """Run the app and report the `ScionError` it raises."""
    print(f"\n$ errors_example.py {' '.join(args)}")
    try:
        app(list(args), standalone_mode=False)
    except ScionError as err:
        print(f"{type(err).__name__}: {err}")


def unknown_option() -> typer.Typer:
    """
    An `Inherited()` parameter must match an option that an ancestor marks `Inheritable()`.

    The parent shares `--level`, but the child asks for `depth`, so nothing can supply it. The same error appears when
    the option lives above a group whose callback is not decorated with `@inherit`.
    """
    app = typer.Typer()

    @app.callback()
    def parent(level: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @app.command()
    @inherit
    def child(depth: Annotated[int, Inherited()]): ...

    return app


def inherited_default() -> typer.Typer:
    """An `Inherited()` parameter takes its default from the parent, so it may not declare one."""
    app = typer.Typer()

    @app.callback()
    def parent(level: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @app.command()
    @inherit
    def child(level: Annotated[int, Inherited()] = 5): ...

    return app


def inheritable_on_command() -> typer.Typer:
    """
    Options are shared downward through group callbacks only.

    A command's options are never visible to its siblings, so marking one `Inheritable()` on a command is rejected.
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
    return root


if __name__ == "__main__":
    print("== UnknownInheritedOptionError: no ancestor shares the requested option ==")
    attempt(unknown_option(), "child")

    print("\n== InheritedDefaultError: an Inherited() parameter declares a default ==")
    attempt(inherited_default(), "child")

    print("\n== InheritableOnCommandError: Inheritable() used on a command ==")
    attempt(inheritable_on_command(), "sub", "child")
