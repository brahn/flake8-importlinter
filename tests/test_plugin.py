"""
Tests for the ImportLinterPlugin.
"""

from unittest import mock

import pytest

from flake8_importlinter.plugin import ImportLinterPlugin
from tests.fixtures.mock_importlinter import MockViolation, MockContractCheck, MockContract, MockReport


@pytest.fixture
def plugin():
    """Create a plugin instance for testing."""
    return ImportLinterPlugin(
        tree=None,
        filename="/path/to/myproject/mypackage/module.py",
        project_root_dir="/path/to/myproject",
        config_filepath="/path/to/myproject/.importlinter",
    )


@pytest.fixture
def mock_create_report():
    """Mock the create_report function."""
    with mock.patch("flake8_importlinter.plugin.create_report") as mock_create:
        yield mock_create


@pytest.fixture
def mock_read_options():
    """Mock the read_user_options function."""
    with mock.patch("flake8_importlinter.plugin.read_user_options") as mock_read:
        yield mock_read


def test_plugin_initialization(plugin):
    """Test that the plugin initializes correctly."""
    assert plugin.filename == "/path/to/myproject/mypackage/module.py"


def test_get_module_name(plugin):
    """Test conversion of filenames to module names."""
    # Mock the config file
    plugin._config_file = "/path/to/myproject/.importlinter"

    # Test with a normal module
    plugin.filename = "/path/to/myproject/mypackage/subpackage/module.py"
    module_name = plugin._get_module_name(plugin.project_root_dir)
    assert module_name == "mypackage.subpackage.module"

    # Test with an __init__.py file
    plugin.filename = "/path/to/myproject/mypackage/subpackage/__init__.py"
    module_name = plugin._get_module_name(plugin.project_root_dir)
    assert module_name == "mypackage.subpackage"

    # Test with a file outside the project
    plugin.filename = "/some/other/path/module.py"
    module_name = plugin._get_module_name(plugin.project_root_dir)
    assert module_name is None


def test_extract_violations(plugin):
    """Test extracting violations from a report."""
    # Create a mock report with violations
    contract1 = MockContract(name="Forbidden Contract")
    check1 = MockContractCheck(
        kept=False,
        violations=[
            MockViolation(
                importer="mypackage.module",
                imported="forbidden.module",
                line_number=10,
                line_contents="from forbidden.module import func",
            ),
            MockViolation(importer="other.module", imported="forbidden.module", line_number=5),
        ],
    )

    contract2 = MockContract(name="Layers Contract")
    check2 = MockContractCheck(kept=True)

    report = MockReport(contract_checks=[(contract1, check1), (contract2, check2)])

    # Extract violations for our module
    violations = plugin._extract_violations(report, "mypackage.module")

    # We should have one contract with violations
    assert len(violations) == 1
    contract_name, contract_violations = violations[0]

    # Check the contract name
    assert contract_name == "Forbidden Contract"

    # Check the violations
    assert len(contract_violations) == 1
    line_num, message = contract_violations[0]
    assert line_num == 10
    assert "Forbidden import of forbidden.module" in message


@mock.patch("flake8_importlinter.plugin.IMPORT_LINTER_AVAILABLE", True)
@mock.patch.object(ImportLinterPlugin, "_get_module_name")
@mock.patch.object(ImportLinterPlugin, "_extract_violations")
def test_run_with_violations(
    mock_extract, mock_get_module, mock_read_options, mock_create_report, plugin
):
    """Test the run method with violations."""
    # Set up mocks
    mock_get_module.return_value = "mypackage.module"
    mock_extract.return_value = [("Forbidden Contract", [(10, "Forbidden import of forbidden.module")])]

    # Convert the generator to a list
    errors = list(plugin.run())

    # Check that we got one error with the expected format
    assert len(errors) == 1
    line, col, message, instance = errors[0]
    assert line == 10
    assert col == 0
    assert "IMP001 Forbidden Contract: Forbidden import of forbidden.module" in message
    assert isinstance(instance, type)


@mock.patch("flake8_importlinter.plugin.IMPORT_LINTER_AVAILABLE", True)
@mock.patch("flake8_importlinter.plugin.read_user_options")
@mock.patch("flake8_importlinter.plugin.create_report")
@mock.patch("flake8_importlinter.plugin._register_contract_types")
def test_run_no_config(mock_register_types, mock_create_report, mock_read_options, plugin):
    """Test the run method when no config file is found."""
    # Set the config file to None
    plugin.config_filepath = None

    # Create a simplified user_options mock
    mock_read_options.return_value = {}

    # Make the _register_contract_types function a no-op
    mock_register_types.return_value = None

    # Mock create_report to return a report with no violations
    mock_report = MockReport(contract_checks=[])
    mock_create_report.return_value = mock_report

    # Mock _get_module_name to return None, indicating file is outside project
    with mock.patch.object(ImportLinterPlugin, "_get_module_name", return_value=None):
        # Run should not yield any errors
        errors = list(plugin.run())
        assert len(errors) == 0


@mock.patch("flake8_importlinter.plugin.IMPORT_LINTER_AVAILABLE", True)
def test_run_with_exception(mock_read_options, plugin):
    """Test the run method when an exception occurs."""
    # Set up mocks
    mock_read_options.side_effect = Exception("Test exception")

    # Run should yield an error
    errors = list(plugin.run())
    assert len(errors) == 1
    line, col, message, instance = errors[0]
    assert line == 1
    assert col == 0
    assert "IMP000 Error running import-linter: Test exception" in message
