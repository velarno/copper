"""
Unit tests for the costings module utility functions.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from api.costings.models import CostEstimate, ValidationResult, Variable
from api.costings.utils import (
    load_request_template,
    save_request_template,
    format_cost_estimate,
    format_validation_result,
    format_variables,
    format_constraint_sets,
    search_variables,
    validate_request_template,
    estimate_total_cost,
    check_budget_compliance,
    create_cache_key,
    get_cache_dir,
    save_to_cache,
    load_from_cache
)


class TestTemplateLoading:
    """Test template loading and saving functions."""
    
    def test_load_valid_template(self):
        """Test loading a valid JSON template."""
        template_data = {
            "inputs": {
                "variable": ["temperature"],
                "year": "2023",
                "month": "08"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template_data, f)
            temp_file = f.name
        
        try:
            loaded_template = load_request_template(temp_file)
            assert loaded_template == template_data
        finally:
            Path(temp_file).unlink()
    
    def test_load_nonexistent_file(self):
        """Test loading a non-existent file."""
        with pytest.raises(ValueError, match="Request template file not found"):
            load_request_template("nonexistent.json")
    
    def test_load_invalid_json(self):
        """Test loading invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_request_template(temp_file)
        finally:
            Path(temp_file).unlink()
    
    def test_save_template(self):
        """Test saving a template to file."""
        template_data = {"variable": ["temperature"]}
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            save_request_template(template_data, temp_file)
            
            with open(temp_file, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data == template_data
        finally:
            Path(temp_file).unlink()


class TestFormatting:
    """Test formatting functions."""
    
    def test_format_cost_estimate(self):
        """Test formatting a cost estimate."""
        estimate = CostEstimate(
            total_cost=12.0,
            budget_limit=400.0,
            is_within_budget=True,
            request_is_valid=True,
            invalid_reason=None
        )
        
        formatted = format_cost_estimate(estimate)
        assert "Cost Estimate:" in formatted
        assert "Total Cost: 12.0" in formatted
        assert "Within Budget: Yes" in formatted
    
    def test_format_cost_estimate_with_breakdown(self):
        """Test formatting a cost estimate with breakdown."""
        estimate = CostEstimate(
            total_cost=15.0,
            budget_limit=400.0,
            is_within_budget=True,
            cost_breakdown={"variables": 10.0, "time": 5.0},
            request_is_valid=True
        )
        
        formatted = format_cost_estimate(estimate)
        assert "Cost Breakdown:" in formatted
        assert "variables: 10.0" in formatted
    
    def test_format_validation_result_valid(self):
        """Test formatting a valid validation result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            constraints={},
            constraint_sets=[]
        )
        
        formatted = format_validation_result(result)
        assert "Validation Result:" in formatted
        assert "Valid: Yes" in formatted
    
    def test_format_validation_result_invalid(self):
        """Test formatting an invalid validation result."""
        result = ValidationResult(
            is_valid=False,
            errors=["Missing field: variable"],
            warnings=["Consider reducing time range"],
            constraints={},
            constraint_sets=[]
        )
        
        formatted = format_validation_result(result)
        assert "Valid: No" in formatted
        assert "Missing field: variable" in formatted
    
    def test_format_variables(self):
        """Test formatting variables."""
        variables = [
            Variable(name="temp", description="Temperature"),
            Variable(name="humidity", description="Humidity")
        ]
        
        formatted = format_variables(variables)
        assert "Available Variables (2):" in formatted
        assert "- temp" in formatted
        assert "- humidity" in formatted
    
    def test_format_variables_detailed(self):
        """Test formatting variables with detailed information."""
        variables = [
            Variable(
                name="temp",
                description="Temperature",
                units="K",
                available_statistics=["daily_mean"]
            )
        ]
        
        formatted = format_variables(variables, detailed=True)
        assert "Description: Temperature" in formatted
        assert "Units: K" in formatted
        assert "Statistics: daily_mean" in formatted


class TestSearch:
    """Test search functionality."""
    
    def test_search_variables(self):
        """Test searching variables."""
        variables = [
            Variable(name="temperature", description="Air temperature"),
            Variable(name="humidity", description="Relative humidity"),
            Variable(name="pressure", description="Atmospheric pressure")
        ]
        
        # Search by name
        results = search_variables(variables, "temp")
        assert len(results) == 1
        assert results[0].name == "temperature"
        
        # Search by description
        results = search_variables(variables, "humidity")
        assert len(results) == 1
        assert results[0].name == "humidity"
        
        # Search with no matches
        results = search_variables(variables, "nonexistent")
        assert len(results) == 0


class TestValidation:
    """Test template validation."""
    
    def test_validate_valid_template(self):
        """Test validating a valid template."""
        template = {
            "inputs": {
                "variable": ["temperature"],
                "year": "2023",
                "month": "08"
            }
        }
        
        errors = validate_request_template(template)
        assert len(errors) == 0
    
    def test_validate_missing_variable(self):
        """Test validating template with missing variable field."""
        template = {
            "inputs": {
                "year": "2023"
            }
        }
        
        errors = validate_request_template(template)
        assert len(errors) == 1
        assert "Missing required field: variable" in errors[0]
    
    def test_validate_empty_variable_list(self):
        """Test validating template with empty variable list."""
        template = {
            "inputs": {
                "variable": []
            }
        }
        
        errors = validate_request_template(template)
        assert len(errors) == 1
        assert "cannot be empty" in errors[0]
    
    def test_validate_invalid_field_type(self):
        """Test validating template with invalid field type."""
        template = {
            "inputs": {
                "variable": "temperature",  # Should be list
                "year": 2023  # Should be string
            }
        }
        
        errors = validate_request_template(template)
        assert len(errors) >= 1


class TestCostCalculations:
    """Test cost calculation functions."""
    
    def test_estimate_total_cost(self):
        """Test calculating total cost from multiple estimates."""
        estimates = [
            CostEstimate(total_cost=5.0, budget_limit=400.0, is_within_budget=True, request_is_valid=True),
            CostEstimate(total_cost=10.0, budget_limit=400.0, is_within_budget=True, request_is_valid=True),
            CostEstimate(total_cost=15.0, budget_limit=400.0, is_within_budget=True, request_is_valid=True)
        ]
        
        total = estimate_total_cost(estimates)
        assert total == 30.0
    
    def test_check_budget_compliance(self):
        """Test checking budget compliance."""
        estimates = [
            CostEstimate(total_cost=5.0, budget_limit=400.0, is_within_budget=True, request_is_valid=True),
            CostEstimate(total_cost=10.0, budget_limit=400.0, is_within_budget=True, request_is_valid=True)
        ]
        
        # Within budget
        assert check_budget_compliance(estimates, 20.0) is True
        
        # Over budget
        assert check_budget_compliance(estimates, 10.0) is False


class TestCaching:
    """Test caching functions."""
    
    def test_create_cache_key(self):
        """Test creating cache keys."""
        key = create_cache_key("dataset1", "variables", search="temp")
        assert "dataset1" in key
        assert "variables" in key
        assert "search:temp" in key
    
    def test_get_cache_dir(self):
        """Test getting cache directory."""
        cache_dir = get_cache_dir()
        assert cache_dir.exists()
        assert cache_dir.is_dir()
        assert ".copper" in str(cache_dir)
    
    @patch('api.costings.utils.get_cache_dir')
    def test_save_and_load_cache(self, mock_get_cache_dir):
        """Test saving and loading from cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_get_cache_dir.return_value = Path(temp_dir)
            
            # Test saving
            test_data = {"key": "value"}
            save_to_cache("test_key", test_data)
            
            # Test loading
            loaded_data = load_from_cache("test_key")
            assert loaded_data == test_data
            
            # Test loading non-existent key
            loaded_data = load_from_cache("nonexistent")
            assert loaded_data is None 