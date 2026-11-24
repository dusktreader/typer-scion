"""
Three levels of nesting: `app` (root) -> `db` -> `migrations`, whose commands receive options from all three groups.

`@inherit` always uses the app a function is registered on as its parent. A command therefore inherits from its own
group directly, and reaches the groups above that because each group callback is decorated with `@inherit` too. The
root's `--verbose` flag also configures logging (INFO by default, DEBUG with `--verbose`), and ascends to the root callback no matter
where on the command line it is written.

Two more groups hang off the root to show how the chain can be interrupted. `quiet` has no callback, so it is skipped
over. `broken` has a callback that is not decorated with `@inherit`, so it ends the chain.

The script makes several invocations of the CLI in turn.
"""

import logging
import sys
from typing import Annotated

import typer
from typer_scion import Inheritable, Inherited, inherit

log = logging.getLogger("demo")

# Group callbacks record what they receive here, so commands (and the reader) can see that the callbacks did real work.
settings: dict[str, object] = {}

app = typer.Typer(help="Root app")
db = typer.Typer(help="Database commands")
migrations = typer.Typer(help="Migration commands")


@app.callback()
def root(
    verbose: Annotated[
        bool,
        typer.Option(help="Log at DEBUG instead of INFO."),
        Inheritable(),
    ] = False,
):
    """
    Root callback (level 3 from a leaf command's point of view).

    `--verbose` is marked `Inheritable()`, so it is available to any command that opts in with `@inherit`, and to
    deeper levels as long as every group callback in between is decorated with `@inherit` as well. A `--verbose` given
    to a leaf command is also handed back to this callback, which is invoked again with that value. Typer runs a parent callback before it
    parses the subcommand's arguments, so without this the callback would only see the flag when it is written
    before the subcommand name. Keep such a callback idempotent (`force=True` lets `basicConfig` reconfigure).
    """
    level = logging.DEBUG if verbose else logging.INFO
    settings["verbose"] = verbose
    logging.basicConfig(level=level, format="  [%(levelname)s] %(message)s", stream=sys.stdout, force=True)


@db.callback()
@inherit
def db_options(
    verbose: Annotated[bool, Inherited()],
    dsn: Annotated[str, typer.Option(help="Database URL."), Inheritable()] = "sqlite://",
):
    """
    Callback for the `db` group (level 2).

    This callback is both a receiver and a sharer. `verbose` is `Inherited()` from the root, and `--dsn` is
    `Inheritable()`, shared with every opted-in command below `db`, including those in nested groups like
    `migrations`. Because this callback is decorated with `@inherit`, the root's `--verbose` also passes through it to
    those groups.

    The callback acts on what it receives: it records the DSN in `settings` and logs it. Like the root callback, it
    can run again when a descendant is given `--dsn`, so it only assigns and logs.
    """
    settings["dsn"] = dsn
    log.debug("db callback: verbose=%s", verbose)
    log.info("db callback: using %s", dsn)


@migrations.callback()
@inherit
def migration_options(
    dsn: Annotated[str, Inherited()],
    lock_timeout: Annotated[int, typer.Option(help="Seconds to wait."), Inheritable()] = 30,
):
    """
    Callback for the `migrations` group (level 1, the nearest group to its commands).

    `--lock-timeout` is shared with the commands registered directly on `migrations`. `@inherit` on this callback
    pulls in `--dsn` and `--verbose` from the groups above, so the commands below receive all three. This callback
    asks for `dsn` by name, and then uses it together with its own `--lock-timeout` to log a summary and record
    the timeout in `settings`.
    """
    settings["lock_timeout"] = lock_timeout
    log.info("migrations callback: %s, waiting up to %ss for the lock", dsn, lock_timeout)


@migrations.command()
@inherit
def apply(
    lock_timeout: Annotated[int, Inherited()],
    dsn: Annotated[str, Inherited()],
    verbose: Annotated[bool, Inherited()],
    dry_run: bool = False,
):
    """
    Apply migrations, receiving options from all three groups.

    `--dry-run` is this command's own option. `--lock-timeout` (migrations), `--dsn` (db) and `--verbose` (root) are
    all received through `Inherited()`. Only the `migrations` group is its direct parent, but the chain of decorated
    callbacks carries the rest. If two groups declared the same option name, the nearest group would win. The log level was already set by the root callback before this body runs.
    """
    log.debug("inherited options: lock_timeout=%s dsn=%s verbose=%s", lock_timeout, dsn, verbose)
    log.info("applying migrations (dry_run=%s)", dry_run)
    log.debug("settings recorded by the group callbacks: %s", settings)


@migrations.command()
@inherit
def shadow(
    lock_timeout: Annotated[int, Inherited()],
    verbose: Annotated[bool, Inherited()],
    dsn: int = 0,
):
    """
    Declare an option that has the same name as an inherited one.

    The child's own declaration always wins, the way a subclass attribute shadows its parent's. Here `--dsn` is an
    `int` instead of the db group's string, and the remaining inherited options are still merged in.
    """
    log.info("shadow: dsn=%r (%s), lock_timeout=%s, verbose=%s", dsn, type(dsn).__name__, lock_timeout, verbose)


quiet = typer.Typer(help="A group without a callback")
broken = typer.Typer(help="A group whose callback does not pass options along")


@quiet.command()
@inherit
def ping(verbose: Annotated[bool, Inherited()]):
    """
    Receive the root's `--verbose` straight through a group that has no callback.

    `quiet` declares nothing to share, so it contributes nothing and the search simply continues with its parent.
    """
    log.debug("ping inherited verbose=%s", verbose)
    log.info("ping (settings=%s)", settings)


@broken.callback()
def broken_options(tag: Annotated[str, typer.Option(help="A label."), Inheritable()] = "none"):
    """
    Callback for the `broken` group, deliberately left without `@inherit`.

    `--tag` is shared with the commands below, but this callback does not pass along what the root shares. It takes no
    `Inherited()` parameters for that reason: `verbose` is out of reach here.
    """
    settings["tag"] = tag
    log.info("broken callback: tag=%s", tag)


@broken.command()
@inherit
def show(tag: Annotated[str, Inherited()]):
    """
    Receive `--tag` from the direct parent. Asking for `verbose` as well would raise `UnknownInheritedOptionError`.
    """
    log.info("show: tag=%s, settings=%s", tag, settings)


# Group registration wires up Typer's command tree.
db.add_typer(migrations, name="migrations")
app.add_typer(db, name="db")
app.add_typer(quiet, name="quiet")
app.add_typer(broken, name="broken")


def run(*args: str) -> None:
    """Announce a CLI invocation, then run it through the app as if it had been typed in a shell."""
    print(f"\n$ nested_example.py {' '.join(args)}")
    settings.clear()  # each invocation starts fresh, as a real process would
    app(list(args), standalone_mode=False)


if __name__ == "__main__":
    print("== Defaults: INFO logging, inherited options carry their declared defaults ==")
    run("db", "migrations", "apply")

    print("\n== --verbose given to the root group: DEBUG is enabled ==")
    run("--verbose", "db", "migrations", "apply")

    print(
        "\n== --verbose given to the leaf command: the value ascends to the root callback, so DEBUG is enabled too =="
    )
    run("db", "migrations", "apply", "--verbose")

    print("\n== --verbose given to both: the leaf's explicit value wins and is what ascends ==")
    run("--verbose", "db", "migrations", "apply", "--no-verbose")

    print("\n== Options from all three levels, plus the command's own --dry-run ==")
    run("db", "migrations", "apply", "--dsn", "sqlite:///x", "--lock-timeout", "5", "--dry-run")

    print("\n== a child's own --dsn (an int) wins over the inherited str one ==")
    run("db", "migrations", "shadow", "--dsn", "42")

    print("\n== A group without a callback is skipped over ==")
    run("quiet", "ping", "--verbose")

    print("\n== A callback without @inherit ends the chain, but still shares its own options ==")
    run("broken", "show", "--tag", "x")

    print("\n== Merged --help shows options from every level ==")
    run("db", "migrations", "apply", "--help")
