# flake8-importlinter

A Flake8 plugin that integrates [import-linter](https://github.com/seddonym/import-linter) to check for architecture violations directly in your editor.

## Installation

```bash
pip install flake8-importlinter
```

## Usage

1. Set up import-linter in your project by creating a `.importlinter` configuration file
2. Install this plugin in your development environment
3. Run Flake8 normally, or use it through your editor's integration

The plugin will automatically detect import-linter configurations and report any architectural violations as Flake8 errors.

## Error Codes

- `IMP000`: Error running import-linter
- `IMP001`: Contract violation (architecture boundary broken)

## Example

When you have an import that violates your architectural boundaries:

```python
# In a file module.py that shouldn't import from restricted_module
from restricted_module import some_function  # IMP001 LayersContract: Forbidden import of restricted_module
```

Your editor will show this as a Flake8 error, just like any other linting issue.

## Configuration

The plugin uses the same configuration as import-linter. You don't need to configure anything special for Flake8 - just set up import-linter as normal.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development instructions.
