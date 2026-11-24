# Quickstart

## Requirements

* Python 3.12 to 3.15


## Installation

This will install the latest release from pypi via uv:

```shell
uv add typer-scion
```


## Using

A typical app has two parts: a parent callback that shares an option, and a command that receives it.

1. Declare the shared option on the parent callback and mark it with `Inheritable()`.
2. Decorate the command with `@inherit`, placed below `@app.command()`.
3. Annotate a parameter of the command with `Inherited()` to receive the value.

```python
from typing import Annotated

import typer
from typer_scion import Inheritable, Inherited, inherit

app = typer.Typer()


@app.callback()
def main(verbose: Annotated[bool, typer.Option(), Inheritable()] = False): ...


@app.command()
@inherit
def work(verbose: Annotated[bool, Inherited()]):
    print(f"verbose={verbose}")
```

With that in place, `app work --verbose` works, and so does `app --verbose work`. The `work` command lists
`--verbose` in its `--help`, and the option keeps the default and help text the parent gave it.


## Run the demo

The demo walks through each feature in an isolated environment with `uv`:

```shell
uvx --from typer-scion typer-scion-demo
```

Passing `--help` to the command shows the available options.


---

## Learn about more features

The [Features](features.md) page covers everything `typer-scion` provides.
