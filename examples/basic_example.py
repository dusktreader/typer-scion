"""
Basic usage: options marked with `Inheritable()` on the root callback flow into opted-in subcommands.

The root app is a plain `typer.Typer()`. Two options (`--shout`, `--repeat`) are declared once on its callback and
tagged with the `Inheritable()` marker. Any command registered with `@inherit` gets those options added to its own
signature, so they show up in its `--help` and are parsed by Typer like any other option.

It makes several invocations of the CLI in turn.
"""

from typing import Annotated, Any

import typer
from typer_scion import Inheritable, Inherited, get_inherited, inherit

app = typer.Typer()


@app.callback()
def main(
    shout: Annotated[bool, typer.Option(help="Use upper case."), Inheritable()] = False,
    repeat: Annotated[int, typer.Option(help="Times to repeat."), Inheritable()] = 1,
):
    """
    Root callback that declares the shared options.

    Both parameters carry `Inheritable()` in their `Annotated` metadata, which is what marks them as shareable. They are
    still ordinary options of the root app (so `app --shout greet Ada` works too). The marker only makes them
    available to subcommands that opt in with `@inherit`.
    """


@app.command()
@inherit
def greet(name: str, repeat: Annotated[int, Inherited()], shout: Annotated[bool, Inherited()]):
    """
    Greet someone, receiving inherited options by name.

    `@inherit` opts this command in. `name` is this command's own argument. `repeat` and `shout` are annotated
    `Inherited()`: they have no default or option definition here, both come from the root callback. The options are
    merged into the signature Typer sees, so they are listed in `--help` under "Inherited from the root command".
    """
    text = f"Hello, {name}!"
    for _ in range(repeat):
        print(text.upper() if shout else text)


@app.command()
@inherit
def wave(name: str, **shared: Any):
    """
    Wave at someone, collecting every inherited option in `**shared` instead of naming each one.

    This is the alternative to `Inherited()` when a command wants all of the shared options as a dict.
    """
    print(f"*waves at {name}* {shared}")


@app.command()
@inherit
def bye(name: str):
    """
    Say goodbye, reading the inherited options from the context instead of the signature.

    This function does not accept `**kwargs`, so the inherited values are not passed in. They are still parsed (try
    `bye Ada --shout`), and `get_inherited()` returns them as a dict for the running command. This is handy when
    the command body does not want its signature cluttered with shared options.
    """
    shared = get_inherited()
    print(f"Bye, {name}!" + (" (loudly)" if shared["shout"] else ""))


@app.command()
@inherit
def echo(name: str, shout: Annotated[bool, Inherited()], repeat: int = 99):
    """
    Declare an option that has the same name as an inherited one.

    The command's own declaration wins, the way a subclass attribute shadows its parent's. Here `--repeat` has a
    different default from the root's, and the remaining inherited options (`--shout`) are still merged in.
    """
    print(f"{name} x{repeat} (shout={shout})")


@app.command()
def plain():
    """
    A command that does not opt in.

    Without `@inherit` nothing changes: this command has no `--shout` or `--repeat`, and behaves exactly as it
    would in plain Typer.
    """
    print("plain")


def run(*args: str) -> None:
    """Announce a CLI invocation, then run it through the app as if it had been typed in a shell."""
    print(f"\n$ basic_example.py {' '.join(args)}")
    app(list(args), standalone_mode=False)


if __name__ == "__main__":
    print("== Inherited options arrive by name, through the Inherited() marker ==")
    run("greet", "Ada")
    run("greet", "Ada", "--shout", "--repeat", "2")

    print("\n== Or all together as keyword arguments (collected by **shared) ==")
    run("wave", "Ada", "--repeat", "3")

    print("\n== A value given to the root is visible to the child ==")
    run("--shout", "greet", "Ada")

    print("\n== They are merged into the command's --help ==")
    run("greet", "--help")

    print("\n== A command without **kwargs reads the same values with get_inherited() ==")
    run("bye", "Ada", "--shout")

    print(
        "\n== A value given to the child also ascends to the root callback (see the nested example for a visible effect) =="
    )
    run("greet", "Ada", "--shout")

    print("\n== A command's own parameter shadows the inherited one of the same name ==")
    run("echo", "Ada", "--repeat", "4")

    print("\n== A command without the inherit decorator has no shared options ==")
    run("plain")
