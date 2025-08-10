import pytest
import tempfile
import json
from pathlib import Path

from api.stac.models import Template, Variable, ConstraintSet
from api.stac.database import (
    initialize_costings_tables,
    create_template,
    get_template_by_name,
    list_templates,
    delete_template
)
from api.stac.client import CopernicusSTACClient
from api.stac.optimizer import RequestOptimizer


class TestSTACCostingsIntegration:
    """Test integration of STAC costings functionality."""
    
    def test_template_creation_and_retrieval(self):
        """Test creating and retrieving templates."""
        # Initialize tables
        initialize_costings_tables()
        
        # Create a test template
        template_data = {
            "variables": ["temperature", "humidity"],
            "year": ["2023"],
            "month": ["01", "02", "03"]
        }
        
        template = Template(
            name="test_template",
            collection_id="test_collection",
            template_data=template_data,
            variables=["temperature", "humidity"],
            budget_limit=100.0
        )
        
        # Create template
        template_id = create_template(template)
        assert template_id > 0
        
        # Retrieve template
        retrieved = get_template_by_name("test_template")
        assert retrieved is not None
        assert retrieved.name == "test_template"
        assert retrieved.collection_id == "test_collection"
        assert retrieved.variables == ["temperature", "humidity"]
        assert retrieved.budget_limit == 100.0
        
        # List templates
        templates = list_templates()
        assert len(templates) >= 1
        assert any(t.name == "test_template" for t in templates)
        
        # Clean up
        delete_template(template_id)
    
    def test_variable_model(self):
        """Test Variable model creation and serialization."""
        variable = Variable(
            collection_id="test_collection",
            name="temperature",
            description="Air temperature",
            units="celsius",
            available_statistics=["mean", "min", "max"],
            time_resolution="hourly",
            compatible_variables=["humidity", "pressure"],
            temporal_constraints={"min_year": 2020, "max_year": 2023}
        )
        
        # Test model serialization
        data = variable.model_dump()
        assert data["name"] == "temperature"
        assert data["units"] == "celsius"
        assert "mean" in data["available_statistics"]
        
        # Test model validation
        assert variable.name == "temperature"
        assert variable.units == "celsius"
    
    def test_constraint_set_model(self):
        """Test ConstraintSet model creation and serialization."""
        constraint = ConstraintSet(
            collection_id="test_collection",
            constraint_set_id="test_constraints",
            variables=["temperature", "humidity"],
            daily_statistics=["mean", "max"],
            frequencies=["daily", "monthly"],
            time_zones=["UTC"],
            years=["2023"],
            months=["01", "02", "03"],
            days=["01", "15"],
            product_types=["reanalysis"]
        )
        
        # Test model serialization
        data = constraint.model_dump()
        assert data["constraint_set_id"] == "test_constraints"
        assert "temperature" in data["variables"]
        assert "daily" in data["frequencies"]
        
        # Test model validation
        assert constraint.constraint_set_id == "test_constraints"
        assert len(constraint.variables) == 2
    
    def test_stac_client_initialization(self):
        """Test STAC client initialization."""
        client = CopernicusSTACClient()
        assert client.base_url == "https://cds.climate.copernicus.eu/api"
        assert "catalogue/v1" in client.catalogue_url
    
    def test_optimizer_initialization(self):
        """Test optimizer initialization and strategies."""
        optimizer = RequestOptimizer()
        strategies = optimizer.get_optimization_strategies()
        
        expected_strategies = ["constraint-based", "time-based", "variable-based", "hybrid"]
        for strategy in expected_strategies:
            assert strategy in strategies
    
    def test_template_with_file_creation(self):
        """Test creating a template from a file."""
        # Create a temporary template file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            template_data = {
                "variables": ["sea_level", "ocean_temperature"],
                "year": ["2022", "2023"],
                "month": ["01", "02", "03", "04", "05", "06"],
                "frequency": "daily",
                "grid": [0.25, 0.25]
            }
            json.dump(template_data, f)
            temp_file = f.name
        
        try:
            # Test template creation from file
            template = Template(
                name="file_template",
                collection_id="ocean_collection",
                template_data=template_data,
                variables=template_data["variables"],
                budget_limit=200.0
            )
            
            template_id = create_template(template)
            assert template_id > 0
            
            # Verify template data
            retrieved = get_template_by_name("file_template")
            assert retrieved is not None
            assert retrieved.template_data["frequency"] == "daily"
            assert len(retrieved.template_data["variables"]) == 2
            
            # Clean up
            delete_template(template_id)
        
        finally:
            # Clean up temp file
            Path(temp_file).unlink(missing_ok=True)
    
    def test_cost_estimation_model(self):
        """Test CostEstimate model creation."""
        from api.stac.models import CostEstimate
        
        cost_estimate = CostEstimate(
            template_name="test_template",
            estimated_cost=75.50,
            budget_limit=100.0,
            is_within_budget=True,
            breakdown={
                "data_volume": 50.0,
                "processing": 25.50
            },
            warnings=["High data volume detected"]
        )
        
        assert cost_estimate.estimated_cost == 75.50
        assert cost_estimate.is_within_budget is True
        assert "data_volume" in cost_estimate.breakdown
        assert len(cost_estimate.warnings) == 1
    
    def test_validation_result_model(self):
        """Test ValidationResult model creation."""
        from api.stac.models import ValidationResult
        
        validation_result = ValidationResult(
            template_name="test_template",
            is_valid=False,
            errors=["Variable 'invalid_var' not found"],
            warnings=["High cost detected"],
            constraint_violations=["Year 2025 not available"],
            suggestions=["Check available variables", "Reduce time range"]
        )
        
        assert validation_result.is_valid is False
        assert len(validation_result.errors) == 1
        assert len(validation_result.suggestions) == 2
        assert "invalid_var" in validation_result.errors[0]
    
    def test_optimization_result_model(self):
        """Test OptimizationResult model creation."""
        from api.stac.models import OptimizationResult
        
        optimization_result = OptimizationResult(
            template_name="test_template",
            original_cost=150.0,
            optimized_cost=75.0,
            savings=75.0,
            optimization_strategy="hybrid",
            changes={
                "variables": "Reduced from 5 to 2 priority variables",
                "year": "Reduced from 3 years to 1 year"
            },
            is_within_budget=True
        )
        
        assert optimization_result.original_cost == 150.0
        assert optimization_result.optimized_cost == 75.0
        assert optimization_result.savings == 75.0
        assert optimization_result.optimization_strategy == "hybrid"
        assert optimization_result.is_within_budget is True
        assert len(optimization_result.changes) == 2 