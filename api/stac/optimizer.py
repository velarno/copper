from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json

from .models import Template, OptimizationResult, CostEstimate
from .client import stac_client
from .database import get_template_by_name, update_template, add_template_history
from .models import TemplateHistory


class RequestOptimizer:
    """Optimizes STAC requests to fit within budget constraints."""
    
    def __init__(self):
        self.optimization_strategies = {
            "constraint-based": self._optimize_constraint_based,
            "time-based": self._optimize_time_based,
            "variable-based": self._optimize_variable_based,
            "hybrid": self._optimize_hybrid
        }
    
    def optimize_template(self, template_name: str, budget_limit: float, 
                        strategy: str = "hybrid") -> OptimizationResult:
        """Optimize a template to fit within budget constraints."""
        template = get_template_by_name(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")
        
        # Get original cost estimate
        original_cost = template.estimated_cost or 0.0
        
        if original_cost <= budget_limit:
            # Already within budget
            return OptimizationResult(
                template_name=template_name,
                original_cost=original_cost,
                optimized_cost=original_cost,
                savings=0.0,
                optimization_strategy="none",
                changes={},
                is_within_budget=True
            )
        
        # Apply optimization strategy
        if strategy not in self.optimization_strategies:
            raise ValueError(f"Unknown optimization strategy: {strategy}")
        
        optimizer_func = self.optimization_strategies[strategy]
        optimized_data, changes = optimizer_func(template, budget_limit)
        
        # Estimate new cost
        cost_estimate = stac_client.estimate_request_cost(
            template.collection_id, optimized_data
        )
        optimized_cost = cost_estimate.estimated_cost
        
        # Update template with optimized data
        updates = {
            "template_data": optimized_data,
            "estimated_cost": optimized_cost,
            "budget_limit": budget_limit,
            "is_within_budget": optimized_cost <= budget_limit
        }
        
        updated_template = update_template(template.id, updates)
        
        # Record optimization in history
        history = TemplateHistory(
            template_id=template.id,
            action="optimize",
            old_data=template.template_data,
            new_data=optimized_data,
            cost_estimate=optimized_cost,
            validation_result={"strategy": strategy, "changes": changes}
        )
        add_template_history(history)
        
        return OptimizationResult(
            template_name=template_name,
            original_cost=original_cost,
            optimized_cost=optimized_cost,
            savings=original_cost - optimized_cost,
            optimization_strategy=strategy,
            changes=changes,
            is_within_budget=optimized_cost <= budget_limit
        )
    
    def _optimize_constraint_based(self, template: Template, budget_limit: float) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Optimize by adjusting constraints to reduce cost."""
        optimized_data = template.template_data.copy()
        changes = {}
        
        # Reduce time range if specified
        if "year" in optimized_data and isinstance(optimized_data["year"], list):
            original_years = optimized_data["year"]
            if len(original_years) > 1:
                # Take only the most recent year
                optimized_data["year"] = [original_years[-1]]
                changes["year"] = f"Reduced from {len(original_years)} years to 1 year"
        
        # Reduce variables if too many
        if "variables" in optimized_data and isinstance(optimized_data["variables"], list):
            original_vars = optimized_data["variables"]
            if len(original_vars) > 3:
                # Keep only the first 3 variables
                optimized_data["variables"] = original_vars[:3]
                changes["variables"] = f"Reduced from {len(original_vars)} to 3 variables"
        
        # Reduce spatial resolution if specified
        if "grid" in optimized_data:
            grid = optimized_data["grid"]
            if isinstance(grid, list) and len(grid) == 2:
                # Increase grid spacing to reduce data volume
                optimized_data["grid"] = [grid[0] * 2, grid[1] * 2]
                changes["grid"] = "Doubled grid spacing to reduce data volume"
        
        return optimized_data, changes
    
    def _optimize_time_based(self, template: Template, budget_limit: float) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Optimize by adjusting temporal parameters."""
        optimized_data = template.template_data.copy()
        changes = {}
        
        # Reduce time frequency
        if "frequency" in optimized_data:
            freq = optimized_data["frequency"]
            if freq == "hourly":
                optimized_data["frequency"] = "daily"
                changes["frequency"] = "Changed from hourly to daily frequency"
            elif freq == "daily":
                optimized_data["frequency"] = "monthly"
                changes["frequency"] = "Changed from daily to monthly frequency"
        
        # Reduce time range
        if "year" in optimized_data:
            if isinstance(optimized_data["year"], list):
                years = optimized_data["year"]
                if len(years) > 1:
                    # Take only the last 2 years
                    optimized_data["year"] = years[-2:]
                    changes["year"] = f"Reduced from {len(years)} years to last 2 years"
            elif isinstance(optimized_data["year"], str):
                # If single year, keep as is
                pass
        
        # Reduce months if specified
        if "month" in optimized_data and isinstance(optimized_data["month"], list):
            months = optimized_data["month"]
            if len(months) > 6:
                # Take only summer months (6-8) as example
                optimized_data["month"] = ["06", "07", "08"]
                changes["month"] = f"Reduced from {len(months)} months to 3 summer months"
        
        return optimized_data, changes
    
    def _optimize_variable_based(self, template: Template, budget_limit: float) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Optimize by selecting fewer or cheaper variables."""
        optimized_data = template.template_data.copy()
        changes = {}
        
        # Prioritize variables by cost (simplified heuristic)
        if "variables" in optimized_data and isinstance(optimized_data["variables"], list):
            variables = optimized_data["variables"]
            
            # Define variable priorities (lower cost variables first)
            variable_priorities = {
                "temperature": 1,
                "humidity": 2,
                "pressure": 3,
                "wind": 4,
                "precipitation": 5,
                "sea_level": 6,
                "ocean_temperature": 7,
                "ocean_salinity": 8
            }
            
            # Sort variables by priority
            sorted_vars = sorted(variables, key=lambda v: variable_priorities.get(v, 999))
            
            # Keep only the first 2 variables
            if len(sorted_vars) > 2:
                optimized_data["variables"] = sorted_vars[:2]
                changes["variables"] = f"Reduced from {len(variables)} to 2 priority variables"
        
        # Remove expensive statistics
        if "statistics" in optimized_data and isinstance(optimized_data["statistics"], list):
            stats = optimized_data["statistics"]
            # Keep only basic statistics
            basic_stats = ["mean", "min", "max"]
            optimized_stats = [s for s in stats if s in basic_stats]
            if len(optimized_stats) < len(stats):
                optimized_data["statistics"] = optimized_stats
                changes["statistics"] = f"Reduced from {len(stats)} to {len(optimized_stats)} basic statistics"
        
        return optimized_data, changes
    
    def _optimize_hybrid(self, template: Template, budget_limit: float) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Apply multiple optimization strategies in sequence."""
        optimized_data = template.template_data.copy()
        all_changes = {}
        
        # Apply constraint-based optimization
        optimized_data, changes1 = self._optimize_constraint_based(template, budget_limit)
        all_changes.update(changes1)
        
        # Apply time-based optimization
        temp_template = Template(**template.model_dump())
        temp_template.template_data = optimized_data
        optimized_data, changes2 = self._optimize_time_based(temp_template, budget_limit)
        all_changes.update(changes2)
        
        # Apply variable-based optimization
        temp_template.template_data = optimized_data
        optimized_data, changes3 = self._optimize_variable_based(temp_template, budget_limit)
        all_changes.update(changes3)
        
        return optimized_data, all_changes
    
    def analyze_optimization_potential(self, template_name: str, budget_limit: float) -> Dict[str, Any]:
        """Analyze the potential for optimization without applying changes."""
        template = get_template_by_name(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")
        
        analysis = {
            "template_name": template_name,
            "current_cost": template.estimated_cost or 0.0,
            "budget_limit": budget_limit,
            "cost_overrun": max(0, (template.estimated_cost or 0.0) - budget_limit),
            "optimization_opportunities": [],
            "recommended_strategies": []
        }
        
        # Analyze time-based opportunities
        if "year" in template.template_data:
            if isinstance(template.template_data["year"], list) and len(template.template_data["year"]) > 1:
                analysis["optimization_opportunities"].append({
                    "type": "time_reduction",
                    "description": f"Reduce from {len(template.template_data['year'])} years to 1-2 years",
                    "estimated_savings": "20-40%"
                })
        
        # Analyze variable-based opportunities
        if "variables" in template.template_data:
            vars_count = len(template.template_data["variables"])
            if vars_count > 3:
                analysis["optimization_opportunities"].append({
                    "type": "variable_reduction",
                    "description": f"Reduce from {vars_count} variables to 2-3 priority variables",
                    "estimated_savings": "30-50%"
                })
        
        # Analyze frequency opportunities
        if "frequency" in template.template_data:
            freq = template.template_data["frequency"]
            if freq in ["hourly", "daily"]:
                analysis["optimization_opportunities"].append({
                    "type": "frequency_reduction",
                    "description": f"Reduce frequency from {freq} to monthly",
                    "estimated_savings": "60-80%"
                })
        
        # Recommend strategies
        if analysis["cost_overrun"] > 0:
            if any("time_reduction" in opp["type"] for opp in analysis["optimization_opportunities"]):
                analysis["recommended_strategies"].append("time-based")
            if any("variable_reduction" in opp["type"] for opp in analysis["optimization_opportunities"]):
                analysis["recommended_strategies"].append("variable-based")
            analysis["recommended_strategies"].append("hybrid")
        
        return analysis
    
    def get_optimization_strategies(self) -> List[str]:
        """Get list of available optimization strategies."""
        return list(self.optimization_strategies.keys())


# Global optimizer instance
optimizer = RequestOptimizer() 