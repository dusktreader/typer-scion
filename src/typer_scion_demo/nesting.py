"""
Demos of options flowing through several levels of nested apps.

Apps are named for a tree: `root` is the outermost app, `trunk` and `branch` are the groups nested beneath it, and
`leaf` is the command at the very end.
"""

from typing import Annotated

import typer
from roadshow import demo
from typer_scion import Inheritable, Inherited, inherit


@demo("nesting")
def demo_chain():
    """
    Demonstrate options flowing down a chain of apps

    A command inherits from the app it is registered on. To reach further up, each group callback is also decorated
    with `@inherit`, so it passes along whatever it inherits in turn.

    Here the `leaf` command lives on `branch`, which is added to `trunk`, which is added to `root`. Each level shares
    one option and the leaf receives all three. `--a` is given on the command line, while `b` and `c` take their
    defaults.

    Each callback prints the option it declares, so the output shows every level running from the outside in. Since
    `--a` is given to the leaf, the callbacks run a second time with that value as it ascends.
    """
    root, trunk, branch = typer.Typer(), typer.Typer(), typer.Typer()

    @root.callback()
    def r(a: Annotated[int, typer.Option(), Inheritable()] = 1):
        print(f"root sees a={a}")

    @trunk.callback()
    @inherit
    def t(b: Annotated[int, typer.Option(), Inheritable()] = 2):
        print(f"trunk sees b={b}")

    @branch.callback()
    @inherit
    def br(c: Annotated[int, typer.Option(), Inheritable()] = 3):
        print(f"branch sees c={c}")

    @branch.command()
    @inherit
    def leaf(
        a: Annotated[int, Inherited()],
        b: Annotated[int, Inherited()],
        c: Annotated[int, Inherited()],
    ):
        print(f"a={a} b={b} c={c}")

    trunk.add_typer(branch, name="branch")
    root.add_typer(trunk, name="trunk")
    root(["trunk", "branch", "leaf", "--a", "9"])


@demo("nesting")
def demo_relay():
    """
    Demonstrate a callback that both receives and shares an option

    A group callback can take an option from above with `Inherited()` and share one of its own with `Inheritable()`
    in the same signature. It then acts as a relay: the callback uses what it receives, and the leaf below gets both.

    Here `trunk` receives `--a` from `root` and combines it with its own `--b`. The leaf receives `a` and `b`
    together. Passing `--a 5` shows the value reaching `trunk` and then the leaf, with the callbacks running a second
    time as the value ascends.
    """
    root, trunk = typer.Typer(), typer.Typer()

    @root.callback()
    def r(a: Annotated[int, typer.Option(), Inheritable()] = 1):
        print(f"root sees a={a}")

    @trunk.callback()
    @inherit
    def t(
        a: Annotated[int, Inherited()],
        b: Annotated[int, typer.Option(), Inheritable()] = 2,
    ):
        print(f"trunk received a={a} and shares b={b} (a*b={a * b})")

    @trunk.command()
    @inherit
    def leaf(a: Annotated[int, Inherited()], b: Annotated[int, Inherited()]):
        print(f"leaf sees a={a} b={b}")

    root.add_typer(trunk, name="trunk")
    root(["trunk", "leaf", "--a", "5"])


@demo("nesting")
def demo_broken_chain():
    """
    Demonstrate a group that does not pass options along

    Inheritance only reaches as far as the chain of `@inherit` decorators goes. Here `trunk` declares `--b` but its
    callback is not decorated, so `trunk` does not pass on what it would get from `root`.

    The `leaf` command can receive `--b` from its parent, but not `--a` from the grandparent. Asking for `a` with
    `Inherited()` here would raise an `UnknownInheritedOptionError`.
    """
    root, trunk = typer.Typer(), typer.Typer()

    @root.callback()
    def r(a: Annotated[int, typer.Option(), Inheritable()] = 1):
        print(f"root sees a={a}")

    @trunk.callback()
    def t(b: Annotated[int, typer.Option(), Inheritable()] = 2):
        print(f"trunk sees b={b}")

    @trunk.command()
    @inherit
    def leaf(b: Annotated[int, Inherited()]):
        print(f"b={b}")

    root.add_typer(trunk, name="trunk")
    root(["trunk", "leaf"])


@demo("nesting")
def demo_nearest_wins():
    """
    Demonstrate the nearest app winning a name clash

    When two apps in the chain share an option with the same name, the nearer one defines it for the leaf, the way a
    closer relative's trait takes precedence in a family tree.

    Both `root` and `trunk` declare `mode`. The leaf sees the default from `trunk`, which is nearer, while each
    callback still sees its own declaration.
    """
    root, trunk = typer.Typer(), typer.Typer()

    @root.callback()
    def r(mode: Annotated[str, typer.Option(), Inheritable()] = "from-root"):
        print(f"root sees mode={mode}")

    @trunk.callback()
    @inherit
    def t(mode: Annotated[str, typer.Option(), Inheritable()] = "from-trunk"):
        print(f"trunk sees mode={mode}")

    @trunk.command()
    @inherit
    def leaf(mode: Annotated[str, Inherited()]):
        print(f"mode={mode}")

    root.add_typer(trunk, name="trunk")
    root(["trunk", "leaf"])


@demo("nesting")
def demo_skipped_level():
    """
    Demonstrate a group without a callback

    A group that declares no callback has no options to share, so it contributes nothing and the search continues
    with its own parent.

    `trunk` has no callback, so `leaf` receives the options of `root` straight through it.
    """
    root, trunk = typer.Typer(), typer.Typer()

    @root.callback()
    def r(a: Annotated[int, typer.Option(), Inheritable()] = 1):
        print(f"root sees a={a}")

    @trunk.command()
    @inherit
    def leaf(a: Annotated[int, Inherited()]):
        print(f"leaf sees a={a}")

    @trunk.command()
    def other(): ...

    root.add_typer(trunk, name="trunk")
    root(["trunk", "leaf"])
