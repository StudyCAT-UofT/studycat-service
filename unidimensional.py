from adaptivetesting.implementations import TestAssembler
from adaptivetesting.models import TestItem, ItemPool
from adaptivetesting.math.estimators import BayesModal, NormalPrior
from adaptivetesting.math.item_selection import maximum_information_criterion
from adaptivetesting.services import IEstimator, ItemSelectionStrategy
from typing import Type, Any


class UnidimensionalModel:
    """
    Wrapper around TestAssembler for a single unidimensional IRT skill.
    Lets you customize ability estimator and item selection strategy.

    Attributes: 
        skill (str): The skill/concept this model is tracking 
        adaptive_test (TestAssembler): A 3PL IRT model.
    """

    def __init__(
        self,
        skill: str,
        item_pool: ItemPool,
        initial_theta: float = 0.0,
        ability_estimator: Type[IEstimator] = BayesModal,
        estimator_args: dict[str, Any] | None = None,
        item_selector: ItemSelectionStrategy = maximum_information_criterion,
        item_selector_args: dict[str, Any] | None = None,
        debug: bool = False,
    ):
        """
        Creates a UnidimensionalModel object. 

        Arguments: 
            skill (str): The skill/concept this model is tracking.
            item_pool (ItemPool): All unanswered TestItem objects relating to this skill/concept.
            initial_theta (float): The initial ability value estimate, defaults to 0.0
            ability_estimator (Type[IEstimator]): 
                The estimator class used to estimate theta, defaults to BayesModel
            estimator_args (dict[str, Any] | None): 
                Arguments to provide to the estimator class, defaults to None
            item_selector (ItemSelectionStrategy): 
                The selection strategy class used to select the next item, defaults to maximum_information_criterion
            item_selector_args (dict[str, Any] | None):
                Arguments to provide to the item selector class, defaults to None
            debug (bool):
                Whether to run the TestAssembler class in debug mode. Defaults to false
        """
        self.skill = skill

        # default args if not provided
        if estimator_args is None:
            estimator_args = {
                "prior": NormalPrior(0, 1),
                "optimization_interval": (-4, 4)
            }
        if item_selector_args is None:
            item_selector_args = {}

        # Each skill has its own TestAssembler instance
        self.adaptive_test = TestAssembler(
            item_pool=item_pool,
            simulation_id=f"{skill}_sim",
            participant_id="student",
            ability_estimator=ability_estimator,
            estimator_args=estimator_args,
            item_selector=item_selector,
            item_selector_args=item_selector_args,
            initial_ability_level=initial_theta,
            simulation=False,
            debug=debug,
        )

    def get_theta(self) -> float:
        """Return the current ability estimate (theta)."""
        return self.adaptive_test.ability_level

    def get_skill(self) -> str:
        """Return the skill this model is tracking."""
        return self.skill

    def get_responses(self) -> list[int]:
        """Return the response pattern so far (0 = incorrect, 1 = correct)."""
        return self.adaptive_test.response_pattern

    def get_next_item(self) -> TestItem:
        """
        Ask the underlying TestAssembler to select the next best item.
        """
        return self.adaptive_test.get_next_item()

    def record_response(self, response: int, item: TestItem) -> None:
        """
        Record a response and update ability estimate.
        """
        # store response + item
        self.adaptive_test.response_pattern.append(response)
        self.adaptive_test.answered_items.append(item)
        self.adaptive_test.item_pool.delete_item(item)

        # update theta using TestAssembler's estimation method
        est, se = self.adaptive_test.estimate_ability_level()
        self.adaptive_test.ability_level = est
        self.adaptive_test.standard_error = se
