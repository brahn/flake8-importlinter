# Development Guide for flake8-importlinter

This document provides information for developing and contributing to the flake8-importlinter plugin.

## Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install development dependencies: `pip install -e ".[dev]"`

## Testing

Run tests with pytest:

```bash
pytest
```

## Import-Linter Integration Details

This plugin interacts with import-linter using the following API points:

1. `use_cases.create_report()` - Returns an import-linter Report object

2. (In progress) import-linter's rendering module is used to print the report to the console.  We'll use similar logic to extract violations from the report, and then tranform them into flake8-style errors.


## Key Components

### 1. Finding the Configuration

The plugin searches for `.importlinter` or `pyproject.toml` files in parent directories to identify import-linter projects.

### 2. Module Name Resolution

We convert filenames to Python module names to match against the violations reported by import-linter.

### 3. Processing the Report

We extract violations from the Report object that are specific to the current file, and convert them to Flake8 error messages.

### 4. Line Number Extraction

We extract line numbers from violations to report errors at the exact location of problematic imports.

## Common Challenges

1. **Different Contract Types**: Different contract types might structure their violations differently. The plugin attempts to handle these variations.

2. **Module Name Resolution**: Converting between file paths and module names can be tricky, especially with complex package structures.

3. **Caching**: We use import-linter's built-in caching to improve performance, but this might need tuning for large projects.
