# Models README

## UnidimensionalModel

This class provides a simple wrapper around [`adaptivetesting`](https://github.com/condecon/adaptivetesting)'s `TestAssembler` class for managing a 3PL unidimensional IRT model.
Each instance of `UnidimensionalModel` tracks a single skill or concept for a student, keeping an estimate of their current ability (theta) and managing the adaptive testing process for this skill.

### UnidimensionalModel Methods

- `get_theta()`: Returns the current estimated ability value (theta) as a float.
- `set_theta(theta: float)`: Sets the current ability estimate directly. Used to seed the model with a stored theta value at the start of a session.
- `get_next_item()`: Returns the `TestItem` object associated with the next question that should be asked. Item selection strategy can be customised via the `item_selector` parameter at construction time. Defaults to maximum information criterion. Returns `None` if no items remain in the pool.
- `record_response(response: int, item: TestItem)`: Records a correct (1) or incorrect (0) response to a particular item and updates the theta estimate.

### UnidimensionalModel Attributes

- `skill (str)`: The skill/concept this model is tracking.
- `mastery_threshold (float)`: The theta value at which the student is considered to have mastered this skill.
- `mastery_reached (bool)`: `True` once theta has exceeded `mastery_threshold`.
- `questions_left (bool)`: `False` once the item pool is exhausted.

## MultidimensionalModel

This class represents one adaptive test for a particular student. It tracks multiple theta values across different skills through the `models` attribute, which holds one `UnidimensionalModel` per skill.

`MultidimensionalModel` selects the next question from the skill with the lowest current theta value that has neither been mastered nor exhausted its item pool.

### MultidimensionalModel Methods

- `add_model(skill: str, mastery_threshold: float, item_pool: ItemPool, initial_theta: float = 0.0, ability_estimator: Type[IEstimator] = BayesModal, estimator_args: dict[str, Any] | None = None, item_selector: ItemSelectionStrategy = maximum_information_criterion, item_selector_args: dict[str, Any] | None = None)`: Creates a new `UnidimensionalModel` and registers it under the given skill key.
- `get_theta(skill: str) -> float`: Returns the current estimated ability value for the specified skill.
- `record_response(skill: str, response: int, item: TestItem)`: Records a correct/incorrect response for an item belonging to the given skill and updates that skill's theta estimate.
- `get_next_item() -> TestItem | None`: Returns the next question to ask. Chooses from the skill with the lowest theta that still has items available and has not yet been mastered. Returns `None` if all skills are either exhausted or mastered.
- `determine_model_mastered() -> bool`: Returns `True` if every skill in the model has reached its mastery threshold.
