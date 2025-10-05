from adaptivetesting.models import ItemPool, TestItem
from adaptivetesting.math.estimators import BayesModal, NormalPrior
from adaptivetesting.math.item_selection import maximum_information_criterion
import random
import uuid

from unidimensional import UnidimensionalModel
from multidimensional import MultidimensionalModel


def create_dummy_pool(skill_name: str, num_items: int = 5) -> ItemPool:
    """
    Creates a small ItemPool with dummy difficulty values.

    Each item pool will have items with difficulty parameters (b)
    roughly centered around 0, spreading across [-3, 3].
    """
    items = []
    for i in range(num_items):
        a = round(random.uniform(0.5, 2.0), 2)      # discrimination (slope)
        b = round(random.uniform(-3.0, 3.0), 2)     # difficulty
        c = 0.25                                    # guessing (fixed)
        item_id = f"{skill_name}_{i+1}"

        item = TestItem()
        item.id = uuid.uuid4()
        item.a = a
        item.b = b
        item.c = c
        items.append(item)

    return ItemPool(items)


# ============================================================
# Example 1: Unidimensional Model
# ============================================================
def demo_unidimensional():
    print("\n=== Unidimensional Model Demo ===")

    # Create an item pool for Math
    math_pool = create_dummy_pool("Math")

    # Initialize unidimensional model
    math_model = UnidimensionalModel(
        skill="Math",
        mastery_threshold=0.5,
        item_pool=math_pool,
        initial_theta=0.0,
        ability_estimator=BayesModal,
        estimator_args={"prior": NormalPrior(0, 1), "optimization_interval": (-4, 4)},
        item_selector=maximum_information_criterion
    )

    print(f"Initial theta for Math: {math_model.get_theta():.2f}")

    # Simulate answering 6 questions
    # Mastery should be reached at some point. 
    # Only 5 questions in the ItemPool, so the last item will be None
    for i in range(6):
        item = math_model.get_next_item()
        if math_model.mastery_reached:
                    print("Mastery reached.")
        if item is None:
            print("No more items left in the Math pool.")
            break

        # always correct, to show mastery being reached
        response = 1
        math_model.record_response(response, item)

        print(f"Q{i+1}: a={item.a:.2f}, b={item.b:.2f}, response={response}, updated theta={math_model.get_theta():.2f}")

    print(f"Final estimated Math theta: {math_model.get_theta():.2f}")


# ============================================================
# Example 2: Multidimensional Model
# ============================================================
def demo_multidimensional():
    print("\n=== Multidimensional Model Demo ===")

    # Initialize multidimensional model for a single student/test
    multi_model = MultidimensionalModel(student_id=1, test_id=101)

    # Add two unidimensional models: Math and Reading
    multi_model.add_model("Math", 1.0, create_dummy_pool("Math"))
    multi_model.add_model("Reading", 1.0, create_dummy_pool("Reading"))

    print("Initial thetas:")
    for skill in multi_model.models:
        print(f" - {skill}: {multi_model.get_theta(skill):.2f}")

    # Simulate 6 rounds of adaptive question selection
    for round_num in range(8):
        next_item = multi_model.get_next_item()
        if next_item is None:
            print("\nNo more items available across all skills.")
            break

        # find which skill it belongs to
        skill = None
        for s, model in multi_model.models.items():
            if next_item in model.adaptive_test.item_pool.test_items:
                skill = s
                break
        skill = skill or "Unknown"

        # simulate response (simple heuristic)
        theta = multi_model.get_theta(skill)
        response = random.randint(0, 1)

        # record and update
        multi_model.record_response(skill, response, next_item)

        print(f"Round {round_num + 1}: {skill} | item a={next_item.a:.2f} | item b={next_item.b:.2f} | resp={response} | new theta={multi_model.get_theta(skill):.2f}")

    print("\nFinal thetas:")
    for skill in multi_model.models:
        print(f" - {skill}: {multi_model.get_theta(skill):.2f}")


# ============================================================
# Run both demos
# ============================================================
if __name__ == "__main__":
    demo_unidimensional()
    demo_multidimensional()
