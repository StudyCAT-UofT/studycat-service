from .unidimensional import UnidimensionalModel
from adaptivetesting.models import TestItem, ItemPool
from adaptivetesting.math.estimators import BayesModal, NormalPrior
from adaptivetesting.math.item_selection import maximum_information_criterion
from adaptivetesting.services import IEstimator, ItemSelectionStrategy
from typing import Type, Any
import math

class MultidimensionalModel: 
    """
    A between-item multidimensional IRT model, composed of several UnidimensionalModel objects.

    Attributes: 
        student_id (int): A unique identifier for the student this model is tracking.
        test_id (int): A unique identifier for the test this model is administering. 
        models (dict[str, UnidimensionalModel]): 
            A dictionary of unidimensional models. Keys are the skills which these models track. 
        lowest_theta (tuple[float, str]): 
            The current lowest theta value across all unidimensional models. Organized by (theta, skill)
    """

    def __init__(self, student_id: int, test_id: int):
        self.student_id = student_id
        self.test_id = test_id
        self.models = {}

    def add_model(self, 
        skill: str, 
        mastery_threshold: float,
        item_pool: ItemPool, 
        initial_theta: float = 0.0, 
        ability_estimator: Type[IEstimator] = BayesModal,
        estimator_args: dict[str, Any] | None = None,
        item_selector: ItemSelectionStrategy = maximum_information_criterion,
        item_selector_args: dict[str, Any] | None = None
    ) -> None:
        """
        Adds a new unidimensional model tracking the specified skill. 

        Arguments: 
            skill (str): The skill/concept this model is tracking.
            mastery_threshold (float): The value theta should reach to stop asking questions from this skill/concept. 
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
        """

        model = UnidimensionalModel(skill=skill,
                                    mastery_threshold=mastery_threshold,
                                    item_pool=item_pool,
                                    initial_theta=initial_theta,
                                    ability_estimator=ability_estimator,
                                    estimator_args=estimator_args,
                                    item_selector=item_selector,
                                    item_selector_args=item_selector_args)
        
        self.models[skill] = model

    def get_theta(self, skill: str) -> None:
        """
        Returns the theta value of the given skill. 

        Arguments: 
            skill (str): The skill whose theta value will be returned.
        """
        return self.models[skill].get_theta()
    
    def record_response(self, skill: str, response: int, item: TestItem) -> None:
        """
        Records the response to a given TestItem for a certain skill.
        Updates the theta estimate for that specific skill.

        Arguments:
            skill (str): The skill associated with this question
            response (int): 0 for incorrect, 1 for correct
            item (TestItem): The TestItem object for the specific question asked
        """
        self.models[skill].record_response(response, item)

    def get_next_item(self) -> TestItem:
        """
        Returns the TestItem object associated with the next question that should be asked to the student.

        Currently chooses a question from the model with the lowest current estimated theta value.
        NOTE: in the testing phase, perhaps try out different question picking strategies. 

        Return:
            TestItem: The next question that should be asked in the adaptive test, or None if no TestItems are left. 
        """
        sorted_models = sorted(
            self.models.items(), 
            key=lambda kv: kv[1].get_theta()
        )

        for skill, model in sorted_models:
            if not model.questions_left:
                continue
            if model.mastery_reached:
                continue

            next_item = model.get_next_item()
            if next_item is not None:
                return next_item

        # if all are exhausted or mastered
        return None


