from types import SimpleNamespace
from typing import Annotated, Any

import pytest
import typer
from typer.testing import CliRunner
from typer_scion import (
    Inheritable,
    InheritableOnCommandError,
    Inherited,
    InheritedDefaultError,
    ScionError,
    UnknownInheritedOptionError,
    get_inherited,
    inherit,
)

# Typer forces colored output on CI, which splits help text with ANSI codes; keep the output plain for assertions.
runner = CliRunner(env={"_TYPER_FORCE_DISABLE_TERMINAL": "1", "NO_COLOR": "1"})


def make() -> typer.Typer:
    root, mid, leaf = typer.Typer(), typer.Typer(), typer.Typer()

    @root.callback()
    def _root(verbose: Annotated[bool, typer.Option(help="Be loud."), Inheritable()] = False): ...

    @mid.callback()
    @inherit
    def _mid(retries: Annotated[int, typer.Option(), Inheritable()] = 3, local: str = "x"): ...

    @leaf.command()
    @inherit
    def run(name: str, **kw: Any):
        print(name, sorted(kw.items()))

    @leaf.command()
    def other(): ...

    mid.add_typer(leaf, name="leaf")  # add before the mid->root link exists: order must not matter
    root.add_typer(mid, name="mid")
    return root


def test_plain_typer_and_multilevel_defaults_types():
    root = make()
    assert type(root) is typer.Typer
    r = runner.invoke(root, ["mid", "leaf", "run", "bob"])
    assert r.exit_code == 0, r.output
    assert "[('retries', 3), ('verbose', False)]" in r.output
    r = runner.invoke(root, ["mid", "leaf", "run", "bob", "--verbose", "--retries", "7"])
    assert "[('retries', 7), ('verbose', True)]" in r.output
    assert runner.invoke(root, ["mid", "leaf", "run", "bob", "--retries", "x"]).exit_code == 2


def test_help_shows_options_and_help_text():
    out = runner.invoke(make(), ["mid", "leaf", "run", "--help"]).output
    assert "--verbose" in out and "--retries" in out and "Be loud." in out
    assert "--local" not in out  # only marked options are shared
    assert "[default: 3]" in out


def test_child_declaration_wins_over_inherited_name():
    root = typer.Typer()

    @root.callback()
    def _r(verbose: Annotated[bool, typer.Option(), Inheritable()] = False): ...

    sub = typer.Typer()

    @sub.command()
    @inherit
    def good(verbose: int = 5):
        print("v", verbose)

    @sub.command()
    def other(): ...

    root.add_typer(sub, name="sub")
    r = runner.invoke(root, ["sub", "good", "--verbose", "9"])
    assert "v 9" in r.output  # child's int, not the parent's flag
    assert "v 5" in runner.invoke(root, ["sub", "good"]).output


def test_ctx_helper_without_signature_change_and_explicit_parent():
    root = typer.Typer()
    other = typer.Typer()

    @root.callback()
    def _r(level: Annotated[int, typer.Option(), Inheritable()] = 4): ...

    @other.command()
    @inherit
    def go(ctx: typer.Context):
        print(get_inherited(ctx))
        print(get_inherited())

    @other.command()
    def nop(): ...

    root.add_typer(other, name="o")
    r = runner.invoke(root, ["o", "go", "--level", "8"])
    assert r.output.count("{'level': 8}") == 2


def test_ascend_without_parent_context():
    from typer_scion.inherit import InheritingCommand

    command = InheritingCommand(lambda: None)
    command._ascend(SimpleNamespace(parent=None), {})


def test_ascend_with_short_context_chain():
    from typer_scion.inherit import InheritingCommand

    command = InheritingCommand(lambda: None)
    command._lineage = [typer.Typer(), typer.Typer()]
    command._ascend(SimpleNamespace(parent=SimpleNamespace(parent=None)), {})


def test_no_context_and_unlinked_command():
    from typer_scion.inherit import InheritingCommand

    assert InheritingCommand(lambda: None)._ancestors() == []
    top = typer.Typer()

    @top.command()
    @inherit
    def lone():
        print("ok")

    @top.command()
    def other(): ...

    assert "ok" in runner.invoke(top, ["lone"]).output
    assert get_inherited(typer.Context(typer.main.get_command(top))) == {}
    with pytest.raises(RuntimeError):
        get_inherited()


def test_repr_and_plain_params_ignored():
    assert repr(Inheritable()) == "Inheritable()"
    app = typer.Typer()

    @app.callback()
    def common(plain: int = 1, other: Annotated[int, "x"] = 2): ...

    from typer_scion.inherit import InheritingCommand

    assert InheritingCommand._app_params(app) == {}
    assert InheritingCommand._app_params(typer.Typer()) == {}


def make_logging_app(calls: list[bool]) -> typer.Typer:
    app = typer.Typer()

    @app.callback()
    def main(verbose: Annotated[bool, typer.Option(), Inheritable()] = False):
        calls.append(verbose)

    @app.command()
    @inherit
    def work(**kw: Any):
        print("child sees", kw["verbose"])

    @app.command()
    def other(): ...

    return app


@pytest.mark.parametrize(
    ("args", "calls", "child"),
    [
        (["work"], [False], False),
        (["--verbose", "work"], [True], True),  # parent only: no re-invocation needed, child sees it
        (["work", "--verbose"], [False, True], True),  # child only: parent callback re-invoked
        (["--verbose", "work", "--no-verbose"], [True, False], False),  # explicit child value wins
    ],
)
def test_ascend_to_parent(args: list[str], calls: list[bool], child: bool):
    seen: list[bool] = []
    r = runner.invoke(make_logging_app(seen), args)
    assert r.exit_code == 0, r.output
    assert seen == calls
    assert f"child sees {child}" in r.output


def test_ascend_multilevel_and_marker_repr():
    assert repr(Inheritable()) == "Inheritable()"
    seen: list[str] = []
    root, mid = typer.Typer(), typer.Typer()

    @root.callback()
    def _r(level: Annotated[int, typer.Option(), Inheritable()] = 0):
        seen.append(f"root{level}")

    @mid.callback()
    @inherit
    def _m(level: Annotated[int, typer.Option(), Inheritable()] = 0):
        seen.append(f"mid{level}")

    @mid.command()
    @inherit
    def go(): ...

    @mid.command()
    def other(): ...

    root.add_typer(mid, name="mid")
    assert runner.invoke(root, ["mid", "go", "--level", "5"]).exit_code == 0
    assert seen == ["root0", "mid0", "root5", "mid5"]


def test_callback_options_can_be_registered_as_sources():
    seen: list[int] = []

    def group_cb(level: Annotated[int, typer.Option(), Inheritable()] = 0):
        seen.append(level)

    root, sub = typer.Typer(), typer.Typer(callback=group_cb)

    @sub.command()
    @inherit
    def go(): ...

    @sub.command()
    def other(): ...

    root.add_typer(sub, name="s")
    result = runner.invoke(root, ["s", "go", "--level", "2"])
    assert result.exit_code == 0, result.output
    assert seen == [0, 2]


def test_only_the_effective_group_callback_counts():
    def from_init(a: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    def from_decorator(b: Annotated[int, typer.Option(), Inheritable()] = 2): ...

    def build() -> typer.Typer:
        root, sub = typer.Typer(), typer.Typer(callback=from_init)
        sub.callback()(from_decorator)

        @sub.command()
        @inherit
        def go(**kw: Any):
            print(sorted(kw))

        @sub.command()
        def other(): ...

        root.callback()(lambda: None)
        root.add_typer(sub, name="s")
        return root

    assert "['b']" in runner.invoke(build(), ["s", "go"]).output


def make_inherited_app() -> typer.Typer:
    root, sub = typer.Typer(), typer.Typer(name="sub")

    @root.callback()
    def _r(verbose: Annotated[bool, typer.Option(help="Be loud."), Inheritable()] = False, depth: int = 0): ...

    @sub.callback()
    @inherit
    def _s(retries: Annotated[int, typer.Option(), Inheritable()] = 3): ...

    @sub.command()
    @inherit
    def work(verbose: Annotated[bool, Inherited()], retries: Annotated[int, Inherited()], **kw: Any):
        print("got", verbose, retries, sorted(kw))

    @sub.command()
    def other(): ...

    root.add_typer(sub, name="sub")
    return root


def test_inherited_marker_receives_value_with_parent_definition():
    app = make_inherited_app()
    assert "got False 3 []" in runner.invoke(app, ["sub", "work"]).output
    assert "got True 9 []" in runner.invoke(app, ["sub", "work", "--verbose", "--retries", "9"]).output
    assert runner.invoke(app, ["sub", "work", "--retries", "x"]).exit_code == 2


def test_inherited_options_are_labelled_in_help():
    out = runner.invoke(make_inherited_app(), ["sub", "work", "--help"]).output
    assert "Inherited from the root command" in out and "Inherited from `sub`" in out
    assert "Be loud." in out and "[default: 3]" in out
    assert "--depth" not in out  # unmarked parent options are not shared


def test_inherited_without_a_matching_ancestor_option_raises():
    app, sub = typer.Typer(), typer.Typer()
    app.callback()(lambda: None)

    @sub.command()
    @inherit
    def work(missing: Annotated[int, Inherited()]): ...

    @sub.command()
    def other(): ...

    app.add_typer(sub, name="sub")
    with pytest.raises(UnknownInheritedOptionError, match="missing"):
        runner.invoke(app, ["sub", "work"], catch_exceptions=False)


def test_inherited_parameter_cannot_set_its_own_default():
    root, sub = typer.Typer(), typer.Typer()

    @root.callback()
    def _r(value: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @sub.command()
    @inherit
    def work(value: Annotated[int, Inherited()] = 2): ...

    @sub.command()
    def other(): ...

    root.add_typer(sub, name="sub")
    with pytest.raises(InheritedDefaultError, match="cannot declare a default"):
        runner.invoke(root, ["sub", "work", "--help"], catch_exceptions=False)


def test_label_does_not_mutate_parent_option_or_override_its_panel():
    root, sub = typer.Typer(), typer.Typer()
    info = typer.Option(rich_help_panel="Mine")

    @root.callback()
    def _r(a: Annotated[int, info, Inheritable()] = 1): ...

    @sub.command()
    @inherit
    def work(**kw: Any): ...

    @sub.command()
    def other(): ...

    root.add_typer(sub)  # unnamed sub-app: nothing to flatten into a name
    out = runner.invoke(root, ["work", "--help"]).output
    assert "Mine" in out and "Inherited from" not in out
    assert info.rich_help_panel == "Mine"


def test_plain_marked_parameter_without_typer_option_is_labelled():
    assert repr(Inherited()) == "Inherited()"
    root, sub = typer.Typer(), typer.Typer()

    @root.callback()
    def _r(plain: Annotated[int, Inheritable()] = 4): ...

    @sub.command()
    @inherit
    def work(plain: Annotated[int, Inherited()]):
        print("plain", plain)

    @sub.command()
    def other(): ...

    root.add_typer(sub, name="sub")
    assert "Inherited from the root command" in runner.invoke(root, ["sub", "work", "--help"]).output
    assert "plain 4" in runner.invoke(root, ["sub", "work"]).output


def test_inherit_kwarg_on_command_and_callback():
    seen: list[tuple[str, Any]] = []
    root, sub = typer.Typer(), typer.Typer()

    @root.callback()
    def _r(verbose: Annotated[bool, typer.Option(), Inheritable()] = False):
        seen.append(("root", verbose))

    @sub.callback()
    @inherit
    def _s(retries: Annotated[int, typer.Option(), Inheritable()] = 3, *, verbose: Annotated[bool, Inherited()]):
        seen.append(("sub", verbose))

    @sub.command()
    @inherit
    def work(**kw: Any):
        print("work", sorted(kw))

    @sub.command()
    @inherit
    def full(**kw: Any):
        print("full", sorted(kw), get_inherited())

    root.add_typer(sub, name="sub")
    r = runner.invoke(root, ["sub", "work", "--retries", "4"])
    assert "work ['retries', 'verbose']" in r.output, r.output
    out = runner.invoke(root, ["sub", "full", "--verbose"]).output
    assert "full ['retries', 'verbose']" in out, out
    assert ("root", True) in seen and ("sub", True) in seen  # ascended through both callbacks
    help_out = runner.invoke(root, ["sub", "--help"]).output
    assert "--verbose" in help_out and "Inherited from the root command" in help_out


def test_inherit_decorator_wraps_registered_command():
    app = typer.Typer()

    @app.command("hi")
    @inherit
    def hi():
        print("hi")

    @app.command()
    def other(): ...

    assert "hi" in runner.invoke(app, ["hi"]).output


def test_inheriting_an_app_includes_what_that_app_inherits():
    root, mid, leaf = typer.Typer(), typer.Typer(), typer.Typer()

    @root.callback()
    def _r(a: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @mid.callback()
    @inherit
    def _m(b: Annotated[int, typer.Option(), Inheritable()] = 2): ...

    @leaf.command()
    @inherit
    def run(**kw: Any):
        print(sorted(kw.items()))

    @leaf.command()
    def other(): ...

    mid.add_typer(leaf, name="leaf")
    root.add_typer(mid, name="mid")
    r = runner.invoke(root, ["mid", "leaf", "run", "--a", "7"])
    assert "[('a', 7), ('b', 2)]" in r.output, r.output


def test_value_given_to_root_survives_intermediate_callbacks():
    root, mid = typer.Typer(), typer.Typer()

    @root.callback()
    def _r(a: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @mid.callback()
    @inherit
    def _m(b: Annotated[int, typer.Option(), Inheritable()] = 2): ...

    @mid.command()
    @inherit
    def run(**kw: Any):
        print(sorted(kw.items()))

    @mid.command()
    def other(): ...

    root.add_typer(mid, name="mid")
    r = runner.invoke(root, ["--a", "5", "mid", "run"])
    assert "[('a', 5), ('b', 2)]" in r.output, r.output


def test_callback_given_to_the_constructor_inherits_from_its_owner():
    root = typer.Typer()

    @root.callback()
    def _r(a: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @inherit
    def group_cb(b: Annotated[int, typer.Option(), Inheritable()] = 2): ...

    mid, bare = typer.Typer(callback=group_cb), typer.Typer()

    @mid.command()
    @inherit
    def run(**kw: Any):
        print(sorted(kw))

    @bare.command()
    @inherit
    def lone(**kw: Any):
        print(sorted(kw))

    root.add_typer(mid, name="mid")
    root.add_typer(bare, name="bare")
    assert "['a', 'b']" in runner.invoke(root, ["mid", "run"]).output
    assert "['a']" in runner.invoke(root, ["bare", "lone"]).output


def test_inheritable_on_a_command_raises():
    root, sub = typer.Typer(), typer.Typer()

    @root.callback()
    def _r(): ...

    @sub.command()
    @inherit
    def cmd(x: Annotated[int, typer.Option(), Inheritable()] = 1): ...

    @sub.command()
    def other(): ...

    root.add_typer(sub, name="sub")
    with pytest.raises(InheritableOnCommandError, match="only allowed on group callbacks"):
        runner.invoke(root, ["sub", "cmd"], catch_exceptions=False)


def test_specific_errors_share_a_base_class():
    for error in (InheritedDefaultError, UnknownInheritedOptionError, InheritableOnCommandError):
        assert issubclass(error, ScionError)
