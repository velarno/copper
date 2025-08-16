import json
from copy import deepcopy
from math import prod
from collections import deque
from typing import Optional, List
from api.stac.crud import TemplateUpdater, add_metadata

class TemplateOptimizer:
    """
    Class to break a template into less expensive templates to ensure a budget is met.
    Copernicus free tier requires each request to meet a credit budget, which is proportional
    to the product of the number of parameters in the request.

    Attributes:
        template_updater: TemplateUpdater object to update the template
        valid: deque of valid templates
        queue: deque of templates to be split
        splits: List[dict] list of splits of the template
        costs: List[float] list of costs of the splits
        highest_cost_index: int index of the highest cost template
        highest_cost: float highest cost of the templates
    """
    template_updater: TemplateUpdater
    budget: float
    splits: List[dict]
    costs: List[float]
    highest_cost_index: int
    
    def __init__(self,
        template_updater: Optional[TemplateUpdater] = None,
        template_name: Optional[str] = None
        ) -> None:
        if template_updater:
            self.template_updater = template_updater
        elif template_name:
            self.template_updater = TemplateUpdater(template_name=template_name)
        else:
            raise ValueError("Either template_updater or template_name must be provided")
        self.valid = deque()
        self.queue = deque()
        self.queue.append(self.template_updater.to_dict())

    def split_parameters(self, name: str, state: dict) -> None:
        param_values = state[name]
        num_params = len(param_values)
        cutoff = num_params // 2
        
        first, second = deepcopy(state), deepcopy(state)
        del first[name], second[name]
        first[name] = param_values[cutoff:]
        second[name] = param_values[:cutoff]

        self.queue.append(first)
        self.queue.append(second)

    def cost(self, state: dict) -> float:
        # TODO: centralize cost calculation and import it here
        num_params = {name: max(1, len(values)) for name, values in state.items()}
        return prod(num_params.values())
    
    def total_cost(self) -> float:
        return sum(self.costs)

    def min_cost(self) -> float:
        return min(self.costs)

    def ensure_budget(self, name: str, budget: float):
        # TODO: use a priority queue to split the highest cost state
        # TODO: enqueue the over budget states, each step pop the highest cost state & split it
        # TODO: if the state is under budget, yield it
        while self.queue:
            state = self.queue.pop()
            cost = self.cost(state)
            print(f"cost: {cost}, budget: {budget}")
            if cost <= budget:
                self.valid.append(state)
            else:
                self.split_parameters(name, state)
        return list(self.valid)

    def templates_as_json(self) -> List[dict]:
        return [ json.dumps(template) for template in self.valid ]

    def export_templates(self, prefix: str) -> None:
        for i, template in enumerate(self.valid):
            padded_index = str(i).zfill(3)
            with open(f"{prefix}-{padded_index}.json", "w") as f:
                json.dump(template, f)

    def persist_templates(self, prefix: str = "sub") -> None:
        base_name = self.template_updater.template_name
        for i, tpl_state in enumerate(self.valid):
            padded_index = str(i).zfill(3)
            self.template_updater.create_template_from_dict(
                add_metadata(
                    tpl_state,
                    self.template_updater.dataset_id,
                    f"{prefix}_{base_name}_{padded_index}"
                )
            )

if __name__ == "__main__":
    optimizer = TemplateOptimizer(template_name="expensive")
    print(optimizer.template_updater.to_json())
    print(optimizer.cost(optimizer.template_updater.to_dict()))
    templates = optimizer.ensure_budget("year", 400)
    for template in templates:
        print(template)
    optimizer.persist_templates()