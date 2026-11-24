# Features

Every feature below has a runnable demo, and the `examples` directory of the repository holds complete scripts. The
demo's `--help` lists the available features:

```shell
uvx --from typer-scion typer-scion-demo --help
```


## Sharing an option

A parent callback shares an option by marking it with `Inheritable()` inside `Annotated`. The option stays an ordinary
option of the group, so `app --verbose cmd` keeps working. Only commands decorated with `@inherit` receive it. Every
other command behaves exactly like a plain Typer command.


## Receiving options

A command has three ways to receive inherited options:

- **By name.** A parameter annotated `Annotated[T, Inherited()]` takes its default and option definition from the
  parent, so the child never repeats them.
- **As keyword arguments.** A command that accepts `**shared` gets every inherited option in a dict.
- **From the context.** Calling `get_inherited()` inside the command reads the values without touching the signature.

Typer merges inherited options into the command's signature, so they appear in `--help` under an
"Inherited from ..." panel that names the ancestor sharing them.


## Values flow both ways

A value given to the child on the command line also ascends to the parent. Once the child's options are parsed, the
parent callback runs again with the child's value. Because of this re-invocation, parent callbacks that declare
inheritable options work best when they are idempotent, which suits configuration such as logging.


## Shadowing

A command can declare its own parameter with the same name as an inherited option. The command's declaration wins,
much like a subclass attribute shadows its parent's, and the inherited option is simply not added.


## Nested groups

A command inherits from the app it is registered on. Options from higher groups reach it because each intermediate
group callback is decorated with `@inherit` as well, and passes along whatever it inherits in turn.

A callback can both receive an option with `Inherited()` and share its own with `Inheritable()`. A few rules govern
how the chain behaves:

- When two groups declare the same name, the nearest group wins.
- A group without a callback contributes nothing, so the search continues with its parent.
- A group whose callback is not decorated with `@inherit` ends the chain, and groups above it stay out of reach.


## Errors

Misconfiguration surfaces as a `ScionError`, with a more specific subclass for each case:

- `UnknownInheritedOptionError` appears when an `Inherited()` parameter matches no option shared by an ancestor.
- `InheritedDefaultError` appears when an `Inherited()` parameter declares a default, since the parent supplies it.
- `InheritableOnCommandError` appears when `Inheritable()` is used on a command instead of a group callback. Options
  flow downward through group callbacks only, so a command's options never reach its siblings.
