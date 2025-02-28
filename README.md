# flake8-importlinter

A [Flake8](https://flake8.pycqa.org/) plugin that integrates [import-linter](https://github.com/seddonym/import-linter) to check for broken import restrictions.  With flake8's IDE integrations, you can see violations directly in your editor.

## Installation

```bash
pip install flake8-importlinter
```

## Usage

1. Create an import-linter configuration file (e.g. `.importlinter`, `setup.cfg`, `pyproject.toml`) as described in the [import-linter docs](https://import-linter.readthedocs.io/en/latest/configuration.html).

2. Install this plugin (and flake8) in your development environment.

3. Run Flake8 normally, or use it through your editor's integration.

The plugin will automatically detect import-linter configurations and report any architectural violations as flake8 errors.

## Error Codes

- `IMP000`: Error running import-linter
- `IMP001`: Contract violation (architecture boundary broken)
