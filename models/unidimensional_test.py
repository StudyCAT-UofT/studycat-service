from unidimensional import UnidimensionalModel
from adaptivetesting.models import TestItem, ItemPool

item1 = TestItem()
item1.id = 1
item1.a = 2
item1.b = 3
item1.c = 0.25

item2 = TestItem()
item2.id = 2
item2.a = 1.2
item2.b = 2
item2.c = 0.25

item3 = TestItem()
item3.id = 3
item3.a = 0.4
item3.b = -1
item3.c = 0.25

items = [item1, item2, item3]

item_pool = ItemPool(test_items=items.copy())

model = UnidimensionalModel("chem", item_pool)

print(model.get_theta())

next_question = model.get_next_item()

model.record_response(1, next_question)

print(model.get_theta())

