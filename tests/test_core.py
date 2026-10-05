"""Unit tests for btree.core."""

import random
import unittest

from btree.core import BPlusTree

MAX_KEYS = 5
MIN_KEYS = 2


class BPlusTreeTest(unittest.TestCase):
    """Public behaviour and structural invariants of the B+ tree index."""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def build(self, keys):
        tree = BPlusTree()
        for key in keys:
            tree.insert(key, "v%d" % key)
        return tree

    def leaf_chain(self, tree):
        """Collect the leaves by walking the next pointers."""
        node = tree.root
        while not node.leaf:
            node = node.children[0]
        leaves = []
        seen = set()
        while node is not None:
            self.assertNotIn(id(node), seen, "leaf chain must not cycle")
            seen.add(id(node))
            leaves.append(node)
            node = node.next
        return leaves

    def leaf_pairs(self, tree):
        pairs = []
        for leaf in self.leaf_chain(tree):
            pairs.extend(zip(leaf.keys, leaf.values))
        return pairs

    def measured_height(self, tree):
        node = tree.root
        depth = 1
        while not node.leaf:
            self.assertTrue(node.children, "internal node needs a child")
            node = node.children[0]
            depth += 1
        return depth

    def subtree_min(self, node):
        while not node.leaf:
            self.assertTrue(node.children, "internal node needs a child")
            node = node.children[0]
        self.assertTrue(node.keys, "leaf must not be empty")
        return node.keys[0]

    def subtree_max(self, node):
        while not node.leaf:
            self.assertTrue(node.children, "internal node needs a child")
            node = node.children[-1]
        self.assertTrue(node.keys, "leaf must not be empty")
        return node.keys[-1]

    def check_structure(self, tree, exact_separators=True):
        leaves = []
        stack = [(tree.root, 1)]
        while stack:
            node, depth = stack.pop()
            self.assertEqual(sorted(node.keys), node.keys, "keys inside a node must ascend")
            self.assertEqual(len(set(node.keys)), len(node.keys), "a node must not repeat a key")
            if node is not tree.root:
                self.assertGreaterEqual(len(node.keys), MIN_KEYS, "node below the key floor")
                self.assertLessEqual(len(node.keys), MAX_KEYS, "node above the key ceiling")
            if node.leaf:
                self.assertEqual(len(node.values), len(node.keys), "leaf keys and values must match")
                leaves.append((node, depth))
                continue
            self.assertEqual(len(node.children), len(node.keys) + 1, "internal node needs len(keys) + 1 children")
            for i, child in enumerate(node.children):
                self.assertIs(child.parent, node, "child parent pointer must point at its parent")
                if i > 0:
                    self.assertLessEqual(self.subtree_max(node.children[i - 1]), node.keys[i - 1], "left subtree key above the separator")
                    self.assertLessEqual(node.keys[i - 1], self.subtree_min(child), "separator above the right subtree key")
                    if exact_separators:
                        self.assertEqual(node.keys[i - 1], self.subtree_min(child), "separator must equal the smallest key of the right subtree")
                stack.append((child, depth + 1))
        self.assertEqual(len({depth for _, depth in leaves}), 1, "all leaves must sit on one level")
        chain = self.leaf_chain(tree)
        self.assertEqual(len(chain), len(leaves), "the leaf chain must cover every leaf")
        chain_keys = [key for leaf in chain for key in leaf.keys]
        self.assertEqual(chain_keys, sorted(key for leaf, _ in leaves for key in leaf.keys), "the leaf chain must follow the tree order")
        self.assertEqual(len(set(chain_keys)), len(chain_keys), "the tree must not repeat a key")
        self.assertEqual(len(tree), len(chain_keys), "len(tree) must equal the number of stored keys")

    # ------------------------------------------------------------------
    # cases
    # ------------------------------------------------------------------
    def test_01_empty_tree_and_key_type(self):
        tree = BPlusTree()
        self.assertEqual(len(tree), 0)
        self.assertIsNone(tree.search(1))
        self.assertEqual(list(tree), [])
        self.assertEqual(tree.keys(), [])
        self.assertEqual(tree.range_scan(0, 10), [])
        self.assertFalse(tree.delete(1))
        self.assertEqual(tree.height, 1)
        self.assertTrue(tree.root.leaf)
        for bad in ("7", 2.5, None, True, [1]):
            with self.assertRaises(TypeError):
                tree.insert(bad, "x")
            with self.assertRaises(TypeError):
                tree.search(bad)
            with self.assertRaises(TypeError):
                tree.delete(bad)
            with self.assertRaises(TypeError):
                tree.range_scan(bad, 3)
            with self.assertRaises(TypeError):
                tree.range_scan(0, bad)
        self.assertEqual(len(tree), 0)
        self.assertEqual(list(tree), [])
        # a tiny tree: a single leaf, then the first split
        small = BPlusTree()
        for key in range(1, 9):
            small.insert(key, "s%d" % key)
        self.assertEqual(len(small), 8)
        self.assertEqual([small.search(key) for key in range(1, 9)], ["s%d" % key for key in range(1, 9)])
        self.assertIsNone(small.search(0))
        self.assertEqual([key for key, _ in self.leaf_pairs(small)], list(range(1, 9)))

    def test_02_insert_and_search_in_ascending_order(self):
        tree = BPlusTree()
        for key in range(1, 201):
            tree.insert(key, "v%d" % key)
        self.assertEqual(len(tree), 200)
        for key in range(1, 201):
            self.assertEqual(tree.search(key), "v%d" % key)
        for key in (0, -1, 201, 999):
            self.assertIsNone(tree.search(key))
        self.assertEqual([key for key, _ in self.leaf_pairs(tree)], list(range(1, 201)))
        self.check_structure(tree)

    def test_03_insert_and_search_in_shuffled_order(self):
        keys = list(range(1, 401))
        random.Random(20240929).shuffle(keys)
        tree = self.build(keys)
        self.assertEqual(len(tree), 400)
        for key in keys:
            self.assertEqual(tree.search(key), "v%d" % key)
        self.assertEqual([key for key, _ in self.leaf_pairs(tree)], sorted(keys))
        self.check_structure(tree)

    def test_04_duplicate_key_updates_value(self):
        keys = [12, 5, 27, 3, 9, 18, 5, 31, 1, 40, 27, 22, 7, 15, 33, 2]
        tree = self.build(keys)
        distinct = sorted(set(keys))
        self.assertEqual(len(tree), len(distinct))
        for key in distinct:
            tree.insert(key, "new%d" % key)
        self.assertEqual(len(tree), len(distinct))
        for key in distinct:
            self.assertEqual(tree.search(key), "new%d" % key)
        self.assertEqual([key for key, _ in self.leaf_pairs(tree)], distinct)
        self.check_structure(tree)

    def test_05_iteration_matches_sorted_keys(self):
        keys = list(range(0, 300, 2))
        random.Random(7).shuffle(keys)
        tree = self.build(keys)
        expected = [(key, "v%d" % key) for key in sorted(keys)]
        self.assertEqual(list(tree), expected)
        self.assertEqual(tree.keys(), sorted(keys))
        self.assertEqual([key for key, _ in tree], sorted(keys))

    def test_06_range_scan_boundaries(self):
        tree = BPlusTree()
        for key in range(0, 120):
            tree.insert(key, "n%d" % key)
        self.assertEqual(tree.range_scan(10, 20), [(k, "n%d" % k) for k in range(10, 21)])
        self.assertEqual(tree.range_scan(0, 0), [(0, "n0")])
        self.assertEqual(tree.range_scan(119, 119), [(119, "n119")])
        self.assertEqual(tree.range_scan(115, 200), [(k, "n%d" % k) for k in range(115, 120)])
        self.assertEqual(tree.range_scan(-10, 3), [(k, "n%d" % k) for k in range(0, 4)])
        self.assertEqual(tree.range_scan(50, 49), [])
        self.assertEqual(tree.range_scan(120, 130), [])
        self.assertEqual(tree.range_scan(20, 20), [(20, "n20")])
        self.assertEqual(tree.range_scan(3, 7), [(k, "n%d" % k) for k in range(3, 8)])

    def test_07_delete_keeps_remaining_keys_searchable(self):
        keys = list(range(1, 141))
        random.Random(20250115).shuffle(keys)
        tree = self.build(keys)
        victims = sorted(random.Random(99).sample(keys, 70))
        for key in victims:
            self.assertTrue(tree.delete(key), "delete of a stored key must report success")
        survivors = sorted(set(keys) - set(victims))
        self.assertEqual(len(tree), len(survivors))
        for key in survivors:
            self.assertEqual(tree.search(key), "v%d" % key)
        for key in victims:
            self.assertIsNone(tree.search(key))
            self.assertFalse(tree.delete(key))
        self.assertEqual([key for key, _ in self.leaf_pairs(tree)], survivors)
        self.check_structure(tree, exact_separators=False)

    def test_08_invariants_hold_after_many_deletes(self):
        keys = list(range(1, 501))
        random.Random(31337).shuffle(keys)
        tree = self.build(keys)
        self.check_structure(tree)
        order = list(range(1, 501))
        random.Random(4242).shuffle(order)
        for key in order[:330]:
            self.assertTrue(tree.delete(key), "delete of a stored key must report success")
        survivors = sorted(set(range(1, 501)) - set(order[:330]))
        self.check_structure(tree)
        self.assertEqual([key for key, _ in self.leaf_pairs(tree)], survivors)
        self.assertEqual(len(tree), len(survivors))
        for key in survivors:
            self.assertEqual(tree.search(key), "v%d" % key)

    def test_09_height_matches_depth(self):
        tree = BPlusTree()
        for key in range(1, MAX_KEYS + 1):
            tree.insert(key, "v%d" % key)
        self.assertEqual(tree.height, 1)
        self.assertTrue(tree.root.leaf)
        tree.insert(MAX_KEYS + 1, "v%d" % (MAX_KEYS + 1))
        self.assertFalse(tree.root.leaf, "after a root split the root must be internal")
        self.assertEqual(tree.height, 2)
        self.assertEqual(tree.height, self.measured_height(tree))
        for key in range(1, 101):
            tree.insert(key, "v%d" % key)
        self.assertEqual(tree.height, self.measured_height(tree))
        for key in range(100, 1, -1):
            tree.delete(key)
        self.assertEqual(tree.height, 1)
        self.assertTrue(tree.root.leaf, "with one key left the root must be a leaf")
        self.assertEqual(tree.height, self.measured_height(tree))
        self.assertEqual(self.leaf_pairs(tree), [(1, "v1")])


if __name__ == "__main__":
    unittest.main()
