import json
import logging
from copy import deepcopy
from math import prod
from collections import deque, OrderedDict
from typing import Optional, List, Dict, TypeVar, Union
from api.stac.crud import TemplateUpdater, add_metadata

logger = logging.getLogger(__name__)

TemplateState = TypeVar("TemplateState", bound=Dict[str, Union[list[str], str, int]])
TemplateCardinalities = TypeVar("TemplateCardinalities", bound=Dict[str, int])


def param_cardinalities(state: TemplateState) -> TemplateCardinalities:
    return {
        name: max(1, len(values) if isinstance(values, list) else 1)
        for name, values in state.items()
    }


def cost_from_cardinalities(cardinalities: TemplateCardinalities) -> float:
    return prod(cardinalities.values())


def param_factors(state: TemplateState) -> tuple[dict[str, int], OrderedDict[str, int]]:
    """
    Given a template state, returns a tuple of:
      - cardinalities: dict mapping parameter names to their cardinality (number of values)
      - factors: OrderedDict mapping parameter names to their smallest prime factor (from a fixed list) dividing their cardinality
    """
    cardinalities: dict[str, int] = param_cardinalities(state)
    factors: OrderedDict[str, int] = OrderedDict()
    prime_factors: List[int] = [
        2,
        3,
        5,
        7,
        11,
        13,
        17,
        19,
    ]  # TODO: check if more prime factors needed

    def sort_by_cardinality(cards: dict[str, int]) -> OrderedDict[str, int]:
        # Sorts the cardinalities in descending order of value
        return OrderedDict(sorted(cards.items(), reverse=True, key=lambda x: x[1]))

    for name, cardinality in sort_by_cardinality(cardinalities).items():
        for factor in prime_factors:
            if cardinality % factor == 0:
                factors[name] = factor
                break
        if cardinality == 1:
            break
    return cardinalities, factors


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

    def __init__(
        self,
        template_updater: Optional[TemplateUpdater] = None,
        template_name: Optional[str] = None,
        budget: Optional[float] = None,
    ) -> None:
        if template_updater:
            self.template_updater = template_updater
        elif template_name:
            self.template_updater = TemplateUpdater(template_name=template_name)
        else:
            raise ValueError(
                "Either template_updater or template_name must be provided"
            )
        self.valid = deque()
        self.queue = deque()
        self.queue.append(self.template_updater.to_dict())
        self.budget = budget

    def split_parameters(self, name: str, state: TemplateState, factor: int) -> None:
        param_values = state[name]
        logger.info(f"splitting parameter {name} with factor {factor}")
        num_params = len(param_values) if isinstance(param_values, list) else 1

        step: int = num_params // factor
        cutoffs: list[int] = [
            *range(0, num_params, step),
            -1,
        ]
        logger.info(f"cutoffs: {cutoffs}")

        for low, high in zip(cutoffs[:-1], cutoffs[1:]):
            split = deepcopy(state)
            del split[name]
            split[name] = (
                param_values[low:high]
                if isinstance(param_values, list)
                else param_values
            )
            self.queue.append(split)

    def split_largest_cardinality_parameter(self, state: TemplateState) -> None:
        """
        Splits the largest cardinality parameter of the state by its factor.

        Args:
            state: TemplateState the state to split
        """
        cardinalities, factors = param_factors(state)
        largest_cardinality_parameter = max(cardinalities, key=cardinalities.get)
        factor = factors[largest_cardinality_parameter]
        self.split_parameters(largest_cardinality_parameter, state, factor)

    def cost(self, state: TemplateState) -> float:
        # TODO: centralize cost calculation and import it here
        num_params = {
            name: max(1, len(values) if isinstance(values, list) else 1)
            for name, values in state.items()
        }
        return prod(num_params.values())

    def total_cost(self) -> float:
        return sum(self.costs)

    def min_cost(self) -> float:
        return min(self.costs)

    def ensure_budget(self):
        # TODO: use a priority queue to split the highest cost state
        # TODO: enqueue the over budget states, each step pop the highest cost state & split it
        # TODO: if the state is under budget, yield it
        while self.queue:
            state = self.queue.pop()
            cost = self.cost(state)
            if cost <= self.budget:
                logger.info(
                    f"appending sub-template with cost = {cost} <= {self.budget}"
                )
                self.valid.append(state)
            else:
                logger.info(
                    f"splitting sub-template with cost = {cost} > {self.budget}"
                )
                self.split_largest_cardinality_parameter(state)
        return list(self.valid)

    def templates_as_json(self) -> List[dict]:
        return [json.dumps(template) for template in self.valid]

    def export_templates(self, prefix: str) -> None:
        for i, template in enumerate(self.valid):
            padded_index = str(i).zfill(3)
            with open(f"{prefix}-{padded_index}.json", "w") as f:
                json.dump(template, f)

    def persist_templates(self, prefix: str = "sub") -> None:
        base_name = self.template_updater.template_name
        for i, tpl_state in enumerate(self.valid):
            padded_index = str(i).zfill(3)
            # TODO: test this with new session logic
            template, _ = self.template_updater.create_template_from_dict(
                add_metadata(
                    tpl_state,
                    self.template_updater.dataset_id,
                    f"{prefix}_{base_name}_{padded_index}",
                )
            )


if __name__ == "__main__":
    optimizer = TemplateOptimizer(template_name="expensive", budget=400)
    print(optimizer.template_updater.to_json())
    print(optimizer.cost(optimizer.template_updater.to_dict()))
    templates = optimizer.ensure_budget()
    for template in templates:
        print(template)
    optimizer.persist_templates()
