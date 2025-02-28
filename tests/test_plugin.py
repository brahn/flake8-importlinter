from unittest import mock

import pytest
from importlinter.domain.contract import Violation
from importlinter.contracts._common import ImportNote

from flake8_importlinter.plugin import ImportLinterPlugin
from tests.fixtures.mock_importlinter import MockReport


@pytest.fixture
def plugin():
    """Create a plugin instance for testing."""
    return ImportLinterPlugin(
        tree=None,
        filename="/path/to/myproject/mypackage/module.py",
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


def test_flake8_errors_for_module(plugin):
    """Test the _flake8_errors_for_module method."""

    # Create a violation with multiple line numbers
    violation1 = Violation(
        summary="some_summary_1",
        import_notes=[
            ImportNote(
                module="mypackage.module",
                msg="some_msg_1",
                line_numbers=(10, 15),
            )
        ],
    )

    # Create a violation for a different module
    violation2 = Violation(
        summary="some_summary_2",
        import_notes=[
            ImportNote(
                module="other.module",
                msg="some_msg_2",
                line_numbers=(5,),
            )
        ],
    )

    # Create a violation with no line numbers
    violation3 = Violation(
        summary="some_summary_3",
        import_notes=[
            ImportNote(
                module="mypackage.module",
                msg="some_msg_3",
                line_numbers=(None,),
            )
        ],
    )

    # Create mock contracts
    contractA = mock.Mock()
    contractA.name = "contract_name_A"
    contractA.violations.return_value = [violation1, violation2]
    contractB = mock.Mock()
    contractB.name = "contract_name_B"
    contractB.violations.return_value = [violation3]

    # Create mock report
    report = mock.Mock()
    report.get_contracts_and_checks.return_value = [
        (contractA, mock.Mock()),
        (contractB, mock.Mock()),
    ]

    # Get errors for our module
    errors = plugin._flake8_errors_for_module(report, "mypackage.module")

    # Check that we got three errors: two from violation1, and one from violation3
    assert len(errors) == 3

    # Check first and second errors (with line numbers)
    line, col, message, _instance = errors[0]
    assert (line, col) == (10, 0)
    assert "IMP001 contract_name_A: some_summary_1" in message
    line, col, message, instance = errors[1]
    assert (line, col) == (15, 0)
    assert "IMP001 contract_name_A: some_summary_1" in message

    # Check third error (from contractB, no line number)
    line, col, message, _instance = errors[2]
    assert (line, col) == (1, 0)  # Default to line 1 when no line number is available
    assert "IMP001 contract_name_B: some_summary_3" in message
