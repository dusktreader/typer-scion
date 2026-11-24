"""
Demos of how a child command receives, shadows, or opts out of the options its parent shares.
"""

import logging
import sys
from typing import Annotated, Any

import typer
from roadshow import demo
from typer_scion import Inheritable, Inherited, get_inherited, inherit


@demo("receiving")
def demo_kwargs():
    """
    Demonstrate inheriting an option as a keyword argument

    The parent callback declares `--verbose` and tags it with `Inheritable()` inside its `Annotated` metadata. That
    tag is the only thing that makes the option shareable. The child opts in by placing `@inherit` below
    `@app.command()`.

    `@inherit` merges the parent's marked options into the child's signature before Typer builds the command, so
    `--verbose` is parsed for the child like any option it declared itself. Because the child accepts `**shared`,
    the parsed value is passed in through that dict. Here the parent sets up logging from the flag, and the child
    logs at both levels, so DEBUG output appears because `--verbose` was given.
    """
    app = typer.Typer()
    log = logging.getLogger("demo")

    @app.callback()
    def parent(verbose: Annotated[bool, typer.Option(), Inheritable()] = False):
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=level, format="[%(levelname)s] %(message)s", stream=sys.stdout, force=True)

    @app.command()
    @inherit
    def child(**shared: Any):
        log.debug("debug detail (verbose=%s)", shared["verbose"])
        log.info("doing work")

    app(["child", "--verbose"])


@demo("receiving")
def demo_named():
    """
    Demonstrate receiving an inherited option by name with `Inherited()`

    A child parameter annotated `Inherited()` has no default and no option definition of its own. Both come from the
    parent, so the default of 3 would apply if the flag were absent, and the supplied `7` is parsed as an `int`.

    The option is defined once, on the parent. If no ancestor shares an option with that name, `UnknownInheritedOptionError` is
    raised, so a typo cannot silently create a new option.
    """
    app = typer.Typer()

    @app.callback()
    def parent(retries: Annotated[int, typer.Option(), Inheritable()] = 3): ...

    @app.command()
    @inherit
    def child(retries: Annotated[int, Inherited()]):
        print(retries, type(retries).__name__)

    app(["child", "--retries", "7"])


@demo("receiving")
def demo_context():
    """
    Demonstrate reading inherited values from the context

    Sometimes a command should not have `**kwargs` cluttering its signature. A child that accepts no extra keyword
    arguments is not handed the inherited values, but they are still parsed.

    `get_inherited()` returns them as a dict for the running command, so the body can read what it needs. The context
    is found automatically, or you can pass one: `get_inherited(ctx)`.
    """
    app = typer.Typer()

    @app.callback()
    def parent(level: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @app.command()
    @inherit
    def child():
        print(get_inherited())

    app(["child", "--level", "5"])


@demo("receiving")
def demo_help():
    """
    Demonstrate inherited options appearing in --help

    Inherited options are merged into the child's signature before Typer builds the command, so they are part of
    the child's `--help` with the help text and default from the parent's declaration.

    They are listed in their own panel, "Inherited from ...", naming the ancestor that shares them, so a reader can
    tell them apart from the options the child declares itself.
    """
    app = typer.Typer()

    @app.callback()
    def parent(level: Annotated[int, typer.Option(help="How deep."), Inheritable()] = 1): ...

    @app.command()
    @inherit
    def child(name: str): ...

    app(["child", "--help"])


@demo("receiving")
def demo_opt_out():
    """
    Demonstrate opting out by leaving off the decorator

    Marking an option `Inheritable()` on the parent does not change any command by itself. Only commands that are
    registered with `@inherit` receive the shared options.

    `plain` is an ordinary Typer command, so its `--help` shows no `--level` option. `shared` opts in and would
    receive it.
    """
    app = typer.Typer()

    @app.callback()
    def parent(level: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @app.command()
    def plain():
        print("plain")

    @app.command()
    @inherit
    def shared(level: Annotated[int, Inherited()]):
        print(f"level={level}")

    app(["plain", "--help"])


@demo("receiving")
def demo_shadow():
    """
    Demonstrate a child shadowing an inherited option

    When the child declares a parameter with the same name as an inherited option, the child's own declaration
    wins, much like a subclass attribute shadowing its parent's. The inherited option is simply not added.

    Here the parent's `--size` is a string, but the child declares its own `--size` as an `int`, so `42` is parsed as
    a number.
    """
    app = typer.Typer()

    @app.callback()
    def parent(size: Annotated[str, typer.Option(), Inheritable()] = "small"): ...

    @app.command()
    @inherit
    def child(size: int = 0):
        print(repr(size))

    app(["child", "--size", "42"])
