"""
Tests for _build_item_pools (service/core.py)

Item pool tests confirm that _build_item_pools correctly filters,
groups, and maps DB items before they are handed to the IRT engine.
"""
from __future__ import annotations


class TestBuildItemPools:
    """
    Unit tests for service.core._build_item_pools.

    _build_item_pools iterates over raw DB items, filters out ineligible
    records, groups the rest into per-concept ItemPools, and returns two
    reverse-lookup dicts (TestItem -> item_id and TestItem -> skill). These
    tests exercise each filtering rule and the correctness of the output
    structures independently.
    """

    def test_groups_by_module(self, make_db_item):
        """
        Items sharing a moduleId should be grouped into the same pool. Passes
        two math items and one reading item and checks that the returned pools
        dict has the correct key set and that each pool contains the right
        number of TestItems.
        """
        from studycat_service.service.core import _build_item_pools

        items = [
            make_db_item("math",    item_id="m1"),
            make_db_item("math",    item_id="m2", b=1.0),
            make_db_item("reading", item_id="r1"),
        ]
        concepts, pools, ti2id, ti2skill = _build_item_pools(items)
        assert set(concepts) == {"math", "reading"}
        assert len(pools["math"].test_items) == 2
        assert len(pools["reading"].test_items) == 1

    def test_inactive_items_excluded(self, make_db_item):
        """
        Items with active=False must be silently skipped. Passes one active
        and one inactive math item and asserts that only the active item
        appears in the pool and in the testitem_to_itemid reverse map.
        """
        from studycat_service.service.core import _build_item_pools

        items = [
            make_db_item("math", active=True,  item_id="active"),
            make_db_item("math", active=False, item_id="inactive"),
        ]
        _, pools, ti2id, _ = _build_item_pools(items)
        assert len(pools["math"].test_items) == 1
        assert "active" in ti2id.values()
        assert "inactive" not in ti2id.values()

    def test_items_without_irt_params_excluded(self, make_db_item):
        """
        Items missing any IRT parameter (irtA, irtB, or irtC is None) cannot
        be turned into TestItems and must be skipped. Sets irtA=None on one
        item and confirms only the valid item ends up in the pool and the
        reverse map.
        """
        from studycat_service.service.core import _build_item_pools

        item_no_params = make_db_item("math", item_id="no_irt")
        item_no_params.irtA = None
        item_ok = make_db_item("math", item_id="ok")

        _, pools, ti2id, _ = _build_item_pools([item_no_params, item_ok])
        assert len(pools["math"].test_items) == 1
        assert "ok" in ti2id.values()

    def test_items_without_module_excluded(self, make_db_item):
        """
        Items with moduleId=None cannot be assigned to any concept pool and
        must be skipped entirely. Asserts that the returned pools dict is
        empty when the only input item has no moduleId.
        """
        from studycat_service.service.core import _build_item_pools

        item = make_db_item("math", item_id="no_module")
        item.moduleId = None
        _, pools, ti2id, _ = _build_item_pools([item])
        assert pools == {}

    def test_testitem_to_skill_mapping(self, make_db_item):
        """
        The ti2skill reverse map must associate every TestItem with the correct
        moduleId string. Passes one math and one reading item (with distinct
        b-parameters so they produce distinct TestItems) and asserts the set
        of values in ti2skill equals {"math", "reading"}.
        """
        from studycat_service.service.core import _build_item_pools

        items = [make_db_item("math"), make_db_item("reading", b=1.0)]
        _, _, _, ti2skill = _build_item_pools(items)
        assert set(ti2skill.values()) == {"math", "reading"}

    def test_concepts_are_sorted(self, make_db_item):
        """
        The first return value (concepts list) must be lexicographically sorted
        regardless of input order. Deterministic ordering matters because the
        MultidimensionalModel iterates concepts in this order when seeding
        thetas and when choosing the next item. Passes concepts in reverse
        alphabetical order and asserts the output matches sorted().
        """
        from studycat_service.service.core import _build_item_pools

        items = [
            make_db_item("zebra"),
            make_db_item("alpha"),
            make_db_item("middle"),
        ]
        concepts, _, _, _ = _build_item_pools(items)
        assert concepts == sorted(concepts)
