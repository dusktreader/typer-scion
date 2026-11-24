"""
Share options declared on a parent Typer app with its subcommands.

Everything works with plain `typer.Typer()` instances. Mark an option on a parent's callback with the
`Inheritable()` marker inside `Annotated` metadata. Decorate child commands with `@inherit`. A group callback
can itself be decorated with `@inherit` to pass its own inherited options down. The merged options appear in the
child's `--help`, grouped in a panel naming the
ancestor they came from. They are forwarded to the child as keyword arguments (to a parameter marked `Inherited()`
or to `**kwargs`) and are always available through `get_inherited()`. Explicitly listing source apps avoids
modifying Typer and makes the ancestry clear.
"""

import copy
import functools
import gc
import inspect
from collections.abc import Callable
from typing import Annotated, Any, cast, get_args, get_origin, get_type_hints

import typer
from buzz import Buzz
from typer.models import ParameterInfo

try:  # Typer >= 0.29 vendors click
    from typer._click.core import ParameterSource
    from typer._click.globals import get_current_context
except ImportError:  # pragma: no cover
    from click import get_current_context  # type: ignore[assignment]
    from click.core import ParameterSource  # type: ignore[assignment]

META_KEY = "typer_scion.inherited"


class ScionError(Buzz):
    """Base class for all errors raised for invalid inheritance configuration."""


class InheritedDefaultError(ScionError):
    """Raised when a parameter marked `Inherited()` also declares a default, since the default comes from the parent."""


class UnknownInheritedOptionError(ScionError):
    """Raised when a parameter marked `Inherited()` names an option that no app in the chain shares."""


class InheritableOnCommandError(ScionError):
    """
    Raised when `Inheritable()` is used on a command instead of a group callback.

    Options are shared downward through group callbacks only. A command's own options are never visible to its
    siblings, and a command has no subcommands to receive them.
    """


class Inheritable:
    """
    Marker placed in `Annotated` metadata on a parent's option to make it shareable with subcommands.

    A value given to a *child* on the command line also ascends to the parent callback that declared the option:
    once the child's options are parsed, the parent callback is invoked again with the child's value. (Typer runs
    a parent's callback before it looks at the subcommand's arguments, so a re-invocation is the only way for the
    parent to learn the child's value.) Parent callbacks that declare inheritable options should therefore be
    idempotent, which is natural for configuration like logging.
    """

    def __repr__(self) -> str:
        return "Inheritable()"


class Inherited:
    """
    Marker placed in `Annotated` metadata on a child's parameter to receive an option shared by an ancestor.

    The parameter carries no default and no option definition of its own: both come from the ancestor, and the
    option is listed in `--help` as inherited. `UnknownInheritedOptionError` is raised if no ancestor shares an option with that
    name. Example: `def child(verbose: Annotated[bool, Inherited()]): ...`
    """

    def __repr__(self) -> str:
        return "Inherited()"


def get_marked_params(func: Callable[..., Any]) -> dict[str, inspect.Parameter]:
    """
    Return the parameters of `func` marked with `Inheritable()`, with the marker stripped.

    Args:
        func: The callback whose signature is inspected.

    Returns:
        The marked parameters by name, each converted to keyword-only.
    """
    hints = get_type_hints(func, include_extras=True)
    found: dict[str, inspect.Parameter] = {}
    for name, param in inspect.signature(func).parameters.items():
        hint = hints.get(name, param.annotation)
        if get_origin(hint) is not Annotated:
            continue

        base, *meta = get_args(hint)
        annotation = base
        markers = []
        kept = []
        for entry in meta:
            if isinstance(entry, Inheritable):
                markers.append(entry)
            else:
                kept.append(entry)
        if len(markers) == 0:
            continue
        if len(kept) != 0:
            annotation = Annotated[(base, *kept)]
        found[name] = param.replace(annotation=annotation, kind=inspect.Parameter.KEYWORD_ONLY)

    return found


def inherit(func: Callable[..., Any]) -> Any:
    """
    Add the inheritable options of the parent app to a Typer command or callback.

    Use it bare, below the Typer registration decorator: `@app.command()` then `@inherit`.

    The parent is found when Typer first inspects the function: for a command it is the app the command is registered
    on, and for a group callback it is the app that group was added to. The options come from the parent's callback and
    from everything that callback inherits in turn. A command can only ever see its own parent and, through the
    parent's own `@inherit`, that parent's ancestors.

    Args:
        func: The command or callback function.

    Returns:
        The wrapped callable to register with Typer.
    """
    return InheritingCommand(func)


class InheritingCommand:
    """A callable that exposes ancestor options in the signature Typer inspects."""

    @staticmethod
    def _app_callback(app: typer.Typer) -> Callable[..., Any] | None:
        """
        Return the group callback in effect for an app.

        Args:
            app: The app to inspect.

        Returns:
            The callback registered with `@app.callback()` if present, else the one given to the constructor, else `None`.
        """
        callback = app.registered_callback.callback if app.registered_callback is not None else app.info.callback
        callback = getattr(callback, "value", callback)
        return callback if callable(callback) else None

    @classmethod
    def _app_params(cls, app: typer.Typer) -> dict[str, inspect.Parameter]:
        """
        Return the inheritable parameters declared by an app's callback.

        Args:
            app: The app to inspect.

        Returns:
            The marked parameters by name, or an empty dict if the app has no callback.
        """
        callback = cls._app_callback(app)
        return get_marked_params(callback) if callback is not None else {}

    @staticmethod
    def _is_inherited_ref(annotation: Any) -> bool:
        """
        Check whether an annotation carries the `Inherited()` marker.

        Args:
            annotation: A resolved type hint, possibly `Annotated`.

        Returns:
            `True` if `Inherited()` appears in the annotation's metadata.
        """
        return get_origin(annotation) is Annotated and any(isinstance(m, Inherited) for m in get_args(annotation)[1:])

    @staticmethod
    def _describe(node: typer.Typer, is_root: bool) -> str:
        """
        Name an app for use in a help panel title.

        Args:
            node: The app to describe.
            is_root: Whether the app is the outermost one in the lineage.

        Returns:
            The app's name in backticks, else "the root command" or "an ancestor" when it has no name.
        """
        name = getattr(node.info.name, "value", node.info.name)
        return f"`{name}`" if name else "the root command" if is_root else "an ancestor"

    @classmethod
    def _label(cls, param: inspect.Parameter, node: typer.Typer, is_root: bool) -> inspect.Parameter:
        """
        Return `param` with its help panel set to say which ancestor it was inherited from.

        The parent's own option declaration is copied, never mutated, and an explicit `rich_help_panel` is kept.

        Args:
            param: The inheritable parameter, marker already stripped.
            node: The app that declared the parameter.
            is_root: Whether `node` is the outermost app in the lineage.

        Returns:
            A copy of `param` whose annotation names the source app in its help panel.
        """
        panel = f"Inherited from {cls._describe(node, is_root)}"
        annotation = param.annotation
        if get_origin(annotation) is Annotated:
            base, *meta = get_args(annotation)
        else:
            base, meta = annotation, []
        for index, entry in enumerate(meta):
            if isinstance(entry, ParameterInfo):
                entry = copy.copy(entry)  # never mutate the parent's own declaration
                if entry.rich_help_panel is None:
                    entry.rich_help_panel = panel
                meta[index] = entry
                break
        else:
            meta.append(typer.Option(rich_help_panel=panel))
        return param.replace(annotation=cast(Any, Annotated)[(base, *meta)])

    @staticmethod
    def _callback_of(info: Any) -> Any:
        """
        Return the plain callback from a Typer info object.

        Args:
            info: A command info, callback info, or app info.

        Returns:
            The callback, with Typer's `Default` wrapper removed.
        """
        return getattr(info.callback, "value", info.callback)

    @staticmethod
    def _owner(app: typer.Typer) -> typer.Typer | None:
        """
        Return the app that `app` was added to as a group.

        Args:
            app: The sub-app whose parent is wanted.

        Returns:
            The parent app, or `None` if `app` has not been added to another app.
        """
        for other in (obj for obj in gc.get_objects() if isinstance(obj, typer.Typer)):
            if any(group.typer_instance is app for group in other.registered_groups):
                return other
        return None

    @classmethod
    def _is_command(cls, func: Any) -> bool:
        """
        Check whether a function is registered as a command, as opposed to a group callback.

        Args:
            func: The wrapped function.

        Returns:
            `True` if some app has registered `func` as a command.
        """
        apps = (obj for obj in gc.get_objects() if isinstance(obj, typer.Typer))
        return any(cls._callback_of(info) is func for app in apps for info in app.registered_commands)

    @classmethod
    def _find_parent(cls, func: Any) -> typer.Typer | None:
        """
        Return the parent app for a function decorated with `@inherit`.

        For a command this is the app it is registered on. For a group callback it is the app that group was added to.

        Args:
            func: The wrapped command or callback.

        Returns:
            The parent app, or `None` if the function is not registered anywhere yet.
        """
        apps = [obj for obj in gc.get_objects() if isinstance(obj, typer.Typer)]
        for app in apps:
            if any(cls._callback_of(info) is func for info in app.registered_commands):
                return app
            if app.registered_callback is not None and cls._callback_of(app.registered_callback) is func:
                return cls._owner(app)
            if cls._callback_of(app.info) is func:
                return cls._owner(app)
        return None

    @classmethod
    def _chain(cls, app: typer.Typer | None) -> list[typer.Typer]:
        """
        Return `app` plus whatever its callback inherits.

        An app without a callback contributes nothing itself, so the search continues with its own parent.

        Args:
            app: The parent app, or `None`.

        Returns:
            The apps whose options are available, nearest first.
        """
        if app is None:
            return []
        callback = cls._app_callback(app)
        if isinstance(callback, InheritingCommand):
            return [app, *callback._ancestors()]
        return [app] if callback is not None else [app, *cls._chain(cls._owner(app))]

    def __init__(self, func: Callable[..., Any]):
        functools.update_wrapper(self, func)
        self.func = func
        self._shadowed: set[str] = set()
        self._resolved: tuple[inspect.Signature, dict[str, Any], list[str]] | None = None
        self._lineage: list[typer.Typer] | None = None

    def _ancestors(self) -> list[typer.Typer]:
        """Return the parent app followed by the apps its own callback inherits from."""
        if self._lineage is None:
            self._lineage = self._chain(self._find_parent(self))
        return self._lineage

    def _resolve(self) -> tuple[inspect.Signature, dict[str, Any], list[str]]:
        """
        Build, once, the merged signature that Typer inspects.

        The function's own parameters come first and win name clashes. Parameters marked `Inherited()` are filled from
        the lineage, and any remaining inheritable options are appended.

        Returns:
            The merged signature, its annotations by name, and the names of all inheritable options.

        Raises:
            InheritedDefaultError: If an `Inherited()` parameter declares a default.
            UnknownInheritedOptionError: If no app in the chain shares an option named by an `Inherited()` parameter.
            InheritableOnCommandError: If the wrapped function is a command that marks an option `Inheritable()`.
        """
        if self._resolved is not None:
            return self._resolved
        name_ = getattr(self.func, "__name__", type(self.func).__name__)
        if self._is_command(self) and get_marked_params(self.func):
            raise InheritableOnCommandError(
                f"{name_}: Inheritable() is only allowed on group callbacks, not on commands"
            )
        inherited: dict[str, tuple[inspect.Parameter, typer.Typer, bool]] = {}
        lineage_ = self._ancestors()
        for index, node in enumerate(lineage_):
            for name, param in self._app_params(node).items():
                inherited.setdefault(name, (param, node, index == len(lineage_) - 1))

        sig = inspect.signature(self.func)
        hints = get_type_hints(self.func, include_extras=True)
        merged: list[inspect.Parameter] = []
        shadowed: set[str] = set()
        for name, param in sig.parameters.items():
            if param.kind is inspect.Parameter.VAR_KEYWORD:
                continue  # `**kwargs` is invisible to Typer; it only receives the forwarded values
            annotation = hints.get(name, param.annotation)
            if self._is_inherited_ref(annotation):
                if param.default is not inspect.Parameter.empty:
                    raise InheritedDefaultError(f"{name_}: inherited parameter {name!r} cannot declare a default")
                if name not in inherited:
                    raise UnknownInheritedOptionError(f"{name_}: no ancestor shares an option named {name!r}")
                merged.append(self._label(*inherited[name]))
            else:
                shadowed.update({name} & inherited.keys())
                merged.append(param.replace(annotation=annotation, kind=inspect.Parameter.KEYWORD_ONLY))
        # A child's own parameter of the same name takes precedence over the inherited one.
        own_names = {p.name for p in merged}
        merged += [self._label(p, node, is_root) for n, (p, node, is_root) in inherited.items() if n not in own_names]
        self._shadowed = shadowed
        self._resolved = (
            sig.replace(parameters=merged),
            {p.name: p.annotation for p in merged},
            list(inherited),
        )
        return self._resolved

    @property
    def __signature__(self) -> inspect.Signature:  # type: ignore[override]
        return self._resolve()[0]

    @property
    def __annotations__(self) -> dict[str, Any]:  # type: ignore[override]
        return self._resolve()[1]

    def _ascend(self, ctx: Any, kwargs: dict[str, Any]) -> None:
        """
        Exchange values with the ancestor callbacks.

        Values the ancestors parsed fill in options the user did not give here. Values given to this command on the
        command line are sent back up by calling the declaring callbacks again.

        Args:
            ctx: The running command's click context.
            kwargs: The parsed keyword arguments, updated in place.
        """
        group_ctx = ctx.parent
        if group_ctx is None:
            return
        pairs = []
        for node in self._ancestors():
            if group_ctx is None:
                break
            pairs.append((node, group_ctx))
            group_ctx = group_ctx.parent
        for node, group_ctx in reversed(pairs):
            callback = self._app_callback(node)
            if callback is None:
                continue
            shared = set(get_marked_params(callback))
            if isinstance(callback, InheritingCommand):
                shared |= set(callback._resolve()[2])
            names = shared & kwargs.keys() - self._shadowed
            given = {name for name in names if ctx.get_parameter_source(name) is ParameterSource.COMMANDLINE}
            for name in (names - given) & set(get_marked_params(callback)):  # only the declaring app supplies a value
                if name in group_ctx.params:
                    kwargs[name] = group_ctx.params[name]
            if given:
                params = inspect.signature(callback).parameters
                call = {name: group_ctx.params[name] for name in params if name in group_ctx.params}
                call.update({name: kwargs[name] for name in given})
                if isinstance(callback, InheritingCommand):
                    callback.forward((), call)
                else:
                    callback(**call)

    def forward(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        """
        Call the wrapped function with only the keyword arguments it accepts.

        Args:
            args: Positional arguments.
            kwargs: Keyword arguments, filtered unless the function takes `**kwargs`.

        Returns:
            Whatever the wrapped function returns.
        """
        parameters = inspect.signature(self.func).parameters
        accepts_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())
        return self.func(*args, **{key: value for key, value in kwargs.items() if key in parameters or accepts_kwargs})

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        inherited = self._resolve()[2]
        ctx = get_current_context(silent=True)
        if ctx is not None:
            self._ascend(ctx, kwargs)
            ctx.meta[META_KEY] = {name: kwargs[name] for name in inherited if name in kwargs}
        return self.forward(args, kwargs)


def get_inherited(ctx: typer.Context | None = None) -> dict[str, Any]:
    """
    Return the inherited option values for the running command.

    Args:
        ctx: The context to read. Defaults to the current one.

    Returns:
        The inherited options by name, or an empty dict if the command inherits none.
    """
    context = cast(Any, ctx or get_current_context())
    return dict(context.meta.get(META_KEY, {}))
