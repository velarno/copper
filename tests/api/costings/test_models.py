"""
Unit tests for the costings module data models.
"""

import pytest
from pydantic import ValidationError

from api.costings.models import (
    Variable, ConstraintSet, ValidationResult, CostEstimate, 
    OptimizedRequest, CostingsConfig
)


class TestVariable:
    """Test the Variable model."""
    
    def test_variable_creation(self):
        """Test creating a variable with minimal data."""
        var = Variable(name="test_variable")
        assert var.name == "test_variable"
        assert var.description is None
        assert var.units is None
        assert var.available_statistics == []
        assert var.compatible_variables == []
    
    def test_variable_with_full_data(self):
        """Test creating a variable with all fields."""
        var = Variable(
            name="temperature",
            description="Air temperature at 2m",
            units="K",
            available_statistics=["daily_mean", "daily_max"],
            time_resolution="hourly",
            compatible_variables=["humidity", "pressure"],
            temporal_constraints={"year": ["2020", "2021"]}
        )
        assert var.name == "temperature"
        assert var.description == "Air temperature at 2m"
        assert var.units == "K"
        assert "daily_mean" in var.available_statistics
        assert "humidity" in var.compatible_variables


class TestConstraintSet:
    """Test the ConstraintSet model."""
    
    def test_constraint_set_creation(self):
        """Test creating a constraint set."""
        constraint_set = ConstraintSet(
            variables=["temp", "humidity"],
            daily_statistics=["daily_mean"],
            frequencies=["hourly"],
            time_zones=["utc+00:00"],
            years=["2023"],
            months=["08"],
            days=["01"],
            product_types=["reanalysis"]
        )
        assert len(constraint_set.variables) == 2
        assert "temp" in constraint_set.variables
        assert "daily_mean" in constraint_set.daily_statistics


class TestValidationResult:
    """Test the ValidationResult model."""
    
    def test_valid_validation_result(self):
        """Test creating a valid validation result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            constraints={},
            constraint_sets=[]
        )
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_invalid_validation_result(self):
        """Test creating an invalid validation result with errors."""
        result = ValidationResult(
            is_valid=False,
            errors=["Missing required field: variable"],
            warnings=["Consider reducing time range"],
            constraints={"time_range": "2023-01-01/2023-12-31"},
            constraint_sets=[]
        )
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Missing required field" in result.errors[0]


class TestCostEstimate:
    """Test the CostEstimate model."""
    
    def test_cost_estimate_creation(self):
        """Test creating a cost estimate."""
        estimate = CostEstimate(
            total_cost=12.0,
            budget_limit=400.0,
            is_within_budget=True,
            request_is_valid=True,
            invalid_reason=None
        )
        assert estimate.total_cost == 12.0
        assert estimate.budget_limit == 400.0
        assert estimate.is_within_budget is True
        assert estimate.request_is_valid is True
    
    def test_cost_estimate_with_breakdown(self):
        """Test creating a cost estimate with breakdown."""
        estimate = CostEstimate(
            total_cost=15.0,
            budget_limit=400.0,
            is_within_budget=True,
            cost_breakdown={"variables": 10.0, "time_range": 5.0},
            estimated_size_gb=2.5,
            request_is_valid=True
        )
        assert estimate.total_cost == 15.0
        assert estimate.cost_breakdown["variables"] == 10.0
        assert estimate.estimated_size_gb == 2.5


class TestOptimizedRequest:
    """Test the OptimizedRequest model."""
    
    def test_optimized_request_creation(self):
        """Test creating an optimized request."""
        constraint_set = ConstraintSet(
            variables=["temp"],
            daily_statistics=["daily_mean"],
            frequencies=["hourly"],
            time_zones=["utc+00:00"],
            years=["2023"],
            months=["08"],
            days=["01"],
            product_types=["reanalysis"]
        )
        
        request = OptimizedRequest(
            request_template={"variable": ["temp"]},
            estimated_cost=5.0,
            priority=1,
            description="Single variable request",
            constraint_set=constraint_set
        )
        assert request.estimated_cost == 5.0
        assert request.priority == 1
        assert request.description == "Single variable request"
        assert request.constraint_set is not None


class TestCostingsConfig:
    """Test the CostingsConfig model."""
    
    def test_default_config(self):
        """Test creating config with default values."""
        config = CostingsConfig()
        assert config.default_budget == 400.0
        assert config.optimization_strategy == "constraint-based"
        assert config.cache_duration == 3600
        assert config.max_retries == 3
        assert config.timeout == 30
        assert config.enable_caching is True
    
    def test_custom_config(self):
        """Test creating config with custom values."""
        config = CostingsConfig(
            default_budget=200.0,
            optimization_strategy="time-based",
            cache_duration=1800,
            max_retries=5,
            timeout=60,
            enable_caching=False
        )
        assert config.default_budget == 200.0
        assert config.optimization_strategy == "time-based"
        assert config.cache_duration == 1800
        assert config.max_retries == 5
        assert config.timeout == 60
        assert config.enable_caching is False 