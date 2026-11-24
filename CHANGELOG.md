# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]


## [0.1.0] - 2026-11-20

### Added

- Project generated from the [xerox-python](https://github.com/dusktreader/xerox-python) template
- `Inheritable()` marker for options on a group callback that subcommands may share
- `@inherit` decorator that merges a parent's shared options into a command's or group callback's signature
- `Inherited()` marker to receive a shared option by name, plus `**kwargs` and `get_inherited()` as other ways to read them
- Inherited options listed in `--help` in their own "Inherited from ..." panel
- Values given to a child ascend to the parent callback that declared the option
- Multi-level nesting, with the nearest group winning name clashes and groups without callbacks skipped
- Child parameters shadow inherited options of the same name
- `ScionError` and specific subclasses: `UnknownInheritedOptionError`, `InheritedDefaultError`, `InheritableOnCommandError`
- Runnable demo (`typer-scion-demo`), example scripts, and documentation
