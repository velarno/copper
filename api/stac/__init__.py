"""
STAC API module for Copernicus Climate Data Store.

This module provides functionality for:
- STAC API interactions with authentication and rate limiting
- Template management with validation
- Cost estimation and optimization
- Request validation against constraints
- Variable discovery and caching
- Comprehensive error handling and logging
"""

# Import configuration and setup logging first
from .config import config, setup_logging

# Setup logging when module is imported
logger = setup_logging()

# from .exceptions import (
#     STACError,
#     STACValidationError,
#     STACDatabaseError,
#     STACAPIError,
#     STACAuthenticationError,
#     STACRateLimitError,
#     STACOptimizationError,
#     STACConfigurationError
# )

# from .models import (
#     Template,
#     TemplateHistory,
#     Variable,
#     ConstraintSet,
#     CostEstimate,
#     ValidationResult,
#     OptimizationResult
# )

# from .client import stac_client, CopernicusStacClient
# from .database import (
#     initialize_costings_tables,
#     create_template,
#     get_template,
#     get_template_by_name,
#     list_templates,
#     update_template,
#     delete_template,
#     add_template_history,
#     store_variables,
#     get_variables,
#     get_variable_by_name,
#     store_constraints,
#     get_constraints,
#     get_constraint_set
# )
# from .optimizer import optimizer, RequestOptimizer
# from .utils import (
#     fetch_collection_links,
#     store_collection_links,
#     fetch_collection_data,
#     store_collection_data,
#     fetch_all_collections,
#     fetch_collection_variables,
#     fetch_collection_constraints,
#     get_collection_info,
#     list_available_collections,
#     search_collections,
#     estimate_request_cost,
#     validate_request,
#     get_collection_variables_from_db,
#     get_collection_constraints_from_db
# )

__all__ = [
    # Configuration and logging
    "config",
    "logger",
    
    # Exceptions
    "STACError",
    "STACValidationError", 
    "STACDatabaseError",
    "STACAPIError",
    "STACAuthenticationError",
    "STACRateLimitError",
    "STACOptimizationError",
    "STACConfigurationError",
    
    # Models
    "Template",
    "TemplateHistory", 
    "Variable",
    "ConstraintSet",
    "CostEstimate",
    "ValidationResult",
    "OptimizationResult",
    
    # Client
    "stac_client",
    "CopernicusStacClient",
    
    # Database operations
    "initialize_costings_tables",
    "create_template",
    "get_template",
    "get_template_by_name",
    "list_templates",
    "update_template",
    "delete_template",
    "add_template_history",
    "store_variables",
    "get_variables",
    "get_variable_by_name",
    "store_constraints",
    "get_constraints",
    "get_constraint_set",
    
    # Optimizer
    "optimizer",
    "RequestOptimizer",
    
    # Utilities
    "fetch_collection_links",
    "store_collection_links",
    "fetch_collection_data",
    "store_collection_data",
    "fetch_all_collections",
    "fetch_collection_variables",
    "fetch_collection_constraints",
    "get_collection_info",
    "list_available_collections",
    "search_collections",
    "estimate_request_cost",
    "validate_request",
    "get_collection_variables_from_db",
    "get_collection_constraints_from_db"
] 