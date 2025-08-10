"""
Integration tests for the costings module using the command line tool.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestCostingsCLI:
    """Test the costings module CLI commands."""
    
    def test_variables_command(self):
        """Test the variables command."""
        result = subprocess.run(
            ["python", "main.py", "costings", "variables", "derived-era5-single-levels-daily-statistics"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        assert result.returncode == 0
        assert "Available Variables" in result.stdout
        assert "variables" in result.stdout.lower()
    
    def test_variables_command_with_search(self):
        """Test the variables command with search."""
        result = subprocess.run(
            ["python", "main.py", "costings", "variables", "derived-era5-single-levels-daily-statistics", "--search", "temperature"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        assert result.returncode == 0
        assert "Found" in result.stdout
        assert "temperature" in result.stdout.lower()
    
    def test_variables_command_with_constraints(self):
        """Test the variables command with constraints."""
        result = subprocess.run(
            ["python", "main.py", "costings", "variables", "derived-era5-single-levels-daily-statistics", "--constraints"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        assert result.returncode == 0
        assert "Constraint Sets" in result.stdout
    
    def test_estimate_command(self):
        """Test the estimate command."""
        # Create a test template
        template_data = {
            "inputs": {
                "product_type": "reanalysis",
                "variable": ["2m_temperature"],
                "daily_statistic": "daily_mean",
                "time_zone": "utc+00:00",
                "year": "2023",
                "month": "08",
                "day": "01"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template_data, f)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ["python", "main.py", "costings", "estimate", "derived-era5-single-levels-daily-statistics", "--template", temp_file],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            assert result.returncode == 0
            assert "Cost Estimate:" in result.stdout
            assert "Total Cost:" in result.stdout
        finally:
            Path(temp_file).unlink()
    
    def test_estimate_command_with_budget(self):
        """Test the estimate command with budget check."""
        template_data = {
            "inputs": {
                "product_type": "reanalysis",
                "variable": ["2m_temperature"],
                "daily_statistic": "daily_mean",
                "time_zone": "utc+00:00",
                "year": "2023",
                "month": "08",
                "day": "01"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template_data, f)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ["python", "main.py", "costings", "estimate", "derived-era5-single-levels-daily-statistics", "--template", temp_file, "--budget", "10.0"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            assert result.returncode == 0
            assert "Budget Limit: 10.0" in result.stdout
        finally:
            Path(temp_file).unlink()
    
    def test_validate_command(self):
        """Test the validate command."""
        template_data = {
            "inputs": {
                "product_type": "reanalysis",
                "variable": ["2m_temperature"],
                "daily_statistic": "daily_mean",
                "time_zone": "utc+00:00",
                "year": "2023",
                "month": "08",
                "day": "01"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template_data, f)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ["python", "main.py", "costings", "validate", "derived-era5-single-levels-daily-statistics", "--template", temp_file],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            assert result.returncode == 0
            assert "Validation Result:" in result.stdout
            assert "Valid: Yes" in result.stdout
        finally:
            Path(temp_file).unlink()
    
    def test_validate_command_invalid_template(self):
        """Test the validate command with invalid template."""
        template_data = {
            "inputs": {
                "product_type": "reanalysis",
                # Missing required variable field
                "year": "2023"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template_data, f)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ["python", "main.py", "costings", "validate", "derived-era5-single-levels-daily-statistics", "--template", temp_file],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            assert result.returncode == 1
            assert "Missing required field: variable" in result.stdout
        finally:
            Path(temp_file).unlink()
    
    def test_optimize_command(self):
        """Test the optimize command."""
        template_data = {
            "inputs": {
                "product_type": "reanalysis",
                "variable": ["2m_temperature", "2m_dewpoint_temperature"],
                "daily_statistic": "daily_mean",
                "time_zone": "utc+00:00",
                "year": "2023",
                "month": "08",
                "day": "01"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template_data, f)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ["python", "main.py", "costings", "optimize", "derived-era5-single-levels-daily-statistics", "--template", temp_file, "--budget", "15.0"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            assert result.returncode == 0
            assert "Optimized Requests" in result.stdout
        finally:
            Path(temp_file).unlink()
    
    def test_optimize_command_with_analysis(self):
        """Test the optimize command with analysis."""
        template_data = {
            "inputs": {
                "product_type": "reanalysis",
                "variable": ["2m_temperature"],
                "daily_statistic": "daily_mean",
                "time_zone": "utc+00:00",
                "year": "2023",
                "month": "08",
                "day": "01"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template_data, f)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ["python", "main.py", "costings", "optimize", "derived-era5-single-levels-daily-statistics", "--template", temp_file, "--budget", "15.0", "--analyze"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            assert result.returncode == 0
            assert "Analysis:" in result.stdout
            assert "Total cost:" in result.stdout
        finally:
            Path(temp_file).unlink()
    
    def test_test_command(self):
        """Test the test command."""
        result = subprocess.run(
            ["python", "main.py", "costings", "test"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        assert result.returncode == 0
        assert "Testing costings module" in result.stdout
        assert "All tests completed successfully!" in result.stdout
    
    def test_help_command(self):
        """Test the help command."""
        result = subprocess.run(
            ["python", "main.py", "costings", "--help"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        assert result.returncode == 0
        assert "costings" in result.stdout
        assert "Validate requests, check costs, and optimize downloads" in result.stdout
    
    def test_variables_help(self):
        """Test the variables command help."""
        result = subprocess.run(
            ["python", "main.py", "costings", "variables", "--help"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        assert result.returncode == 0
        assert "DATASET_ID" in result.stdout
        assert "Discover available variables" in result.stdout


class TestErrorHandling:
    """Test error handling in the CLI."""
    
    def test_invalid_dataset(self):
        """Test with invalid dataset ID."""
        result = subprocess.run(
            ["python", "main.py", "costings", "variables", "invalid-dataset-id"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        # Should handle gracefully
        assert result.returncode == 0
        assert "No variables found" in result.stdout
    
    def test_missing_template_file(self):
        """Test with missing template file."""
        result = subprocess.run(
            ["python", "main.py", "costings", "estimate", "derived-era5-single-levels-daily-statistics", "--template", "nonexistent.json"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        assert result.returncode == 1
        assert "Error:" in result.stdout
    
    def test_invalid_json_template(self):
        """Test with invalid JSON template."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_file = f.name
        
        try:
            result = subprocess.run(
                ["python", "main.py", "costings", "estimate", "derived-era5-single-levels-daily-statistics", "--template", temp_file],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            assert result.returncode == 1
            assert "Error:" in result.stdout
        finally:
            Path(temp_file).unlink() 