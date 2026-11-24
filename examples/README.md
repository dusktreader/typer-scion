# Examples

Worked examples of typer-scion. Each file is self-contained and heavily commented, and together they cover the same
use cases as the demo.

- `basic_example.py` - Marking options with `Inheritable()`, opting in with `@inherit`, the three ways of receiving them (`Inherited()`, `**kwargs`, `get_inherited()`), values ascending to the parent, shadowing, and opting out
- `nested_example.py` - Three-level nesting, nearest-wins, values flowing up and down, groups without a callback, and chains that end at an undecorated callback
- `errors_example.py` - The specific `ScionError` subclasses raised for misconfiguration

The `typer-scion-demo` program walks through the same features one at a time, and the
[documentation](https://dusktreader.github.io/typer-scion) explains them in prose.
