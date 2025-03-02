"""
Integration tests for flake8-importlinter.

These tests verify that the plugin works with actual import-linter contracts.
"""

import os
import sys
from pathlib import Path

import pytest  # noqa: F401 - used for fixtures

from flake8_importlinter.plugin import ImportLinterPlugin

# Adding the integration test directory to path
sys.path.append(str(Path(__file__).parent))


class TestIntegration:
    """Integration tests for the flake8-importlinter plugin."""

    def setup_method(self):
        """Set up the test environment."""
        # Get the path to the integration test directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.integration_dir = os.path.join(current_dir, "integration")

        # Add integration dir to path so import-linter can find modules
        if self.integration_dir not in sys.path:
            sys.path.append(self.integration_dir)

    def teardown_method(self):
        """Clean up after the test."""
        # Remove integration dir from path
        if self.integration_dir in sys.path:
            sys.path.remove(self.integration_dir)

    def test_forbidden_contract(self):
        """Test the plugin with a forbidden contract."""
        # Create a plugin instance with a file that violates the contract
        module_path = os.path.join(self.integration_dir, "mypackage", "high", "module_a.py")
        plugin = ImportLinterPlugin(
            tree=None,
            filename=module_path,
            project_root_dir=self.integration_dir,
            config_filepath=os.path.join(self.integration_dir, ".importlinter.forbidden_contract"),
        )

        # Run the plugin and collect any errors
        errors = list(plugin.run())

        # Check that we got one error with the expected format
        msg = f"Expected 1 error, got {len(errors)}: {errors}"
        assert len(errors) == 1, msg
        line, col, message, instance = errors[0]

        # Import is on line 2, import-linter might report line 1
        line_msg = f"Expected line 1 or 2, got {line}"
        assert line in (1, 2), line_msg

        assert col == 0
        assert "IMP001" in message
        assert "Forbidden" in message
        assert "mypackage.low" in message

    def test_layers_contract(self):
        """Test the plugin with a layers contract."""
        # Create a plugin instance with a file that violates the layers contract
        # We need to use a different config file for this test
        original_path = list(sys.path)

        # Define file paths
        import_linter_path = os.path.join(self.integration_dir, ".importlinter.forbidden_contract")
        layers_import_linter_path = os.path.join(self.integration_dir, ".importlinter.layers_contract")
        backup_path = os.path.join(self.integration_dir, ".importlinter.backup")

        try:
            # If the actual file exists, rename it temporarily
            if os.path.exists(import_linter_path):
                os.rename(import_linter_path, backup_path)

            # Copy the layers version to the expected location
            with open(layers_import_linter_path, "r") as f_src:
                with open(import_linter_path, "w") as f_dst:
                    f_dst.write(f_src.read())

            # Create a plugin instance with a file that violates the layers contract
            module_path = os.path.join(self.integration_dir, "mypackage", "low", "module_c.py")
            plugin = ImportLinterPlugin(
                tree=None,
                filename=module_path,
                config_filepath=os.path.join(self.integration_dir, ".importlinter.layers_contract"),
                project_root_dir=self.integration_dir,
            )

            # Run the plugin and collect any errors
            errors = list(plugin.run())

            # Check that we got at least one error with the expected format
            msg = f"Expected at least 1 error, got {len(errors)}: {errors}"
            assert len(errors) >= 1, msg

            # Check the first error
            line, col, message, instance = errors[0]
            assert col == 0
            assert "IMP001" in message
            assert "Layer" in message

        finally:
            # Clean up - restore original .importlinter file
            if os.path.exists(import_linter_path):
                os.remove(import_linter_path)
            if os.path.exists(backup_path):
                os.rename(backup_path, import_linter_path)

            # Restore the original sys.path
            sys.path = original_path
