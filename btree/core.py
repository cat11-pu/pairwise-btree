"""B+ tree index core.

Design notes
------------
* Key/value pairs live in the leaves only; the leaves are chained in ascending
  key order through the next pointer.
* Internal nodes keep routing separators only: keys[i] is the smallest key of
  the subtree rooted at children[i + 1].
* Capacity: a node holds at most MAX_KEYS keys; every node except the root
  holds at least MIN_KEYS keys.
* All leaves sit on the same level. The root-only tree has height 1.
"""

import bisect

MAX_KEYS = 5
MIN_KEYS = 2


class Node:
    """A B+ tree node. Leaves and internal nodes share the same layout."""

    __slots__ = ("leaf", "keys", "values", "children", "next", "parent")

    def __init__(self, leaf=False):
        self.leaf = leaf
        self.keys = []       # ascending keys
        self.values = []     # leaves only, parallel to keys
        self.children = []   # internal nodes only, one more entry than keys
        self.next = None     # leaves only, right neighbour
        self.parent = None


class BPlusTree:
    """Ordered index over integer keys."""

    def __init__(self):
        self.root = Node(leaf=True)
        self.height = 1
        self.size = 0

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _check_key(key):
        if isinstance(key, bool) or not isinstance(key, int):
            raise TypeError("key must be an int")

    @staticmethod
    def _leftmost_leaf(node):
        while not node.leaf:
            node = node.children[0]
        return node

    def _find_leaf(self, key):
        node = self.root
        while not node.leaf:
            node = node.children[bisect.bisect_right(node.keys, key)]
        return node

    def _refresh_upward(self, node):
        """Sync the separators on the path from node to the root."""
        while node.parent is not None:
            parent = node.parent
            pos = parent.children.index(node)
            if pos > 0:
                parent.keys[pos - 1] = node.keys[0]
            node = parent

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def search(self, key):
        self._check_key(key)
        leaf = self._find_leaf(key)
        pos = bisect.bisect_left(leaf.keys, key)
        if pos < len(leaf.keys) and leaf.keys[pos] == key:
            return leaf.values[pos]
        return None

    def __contains__(self, key):
        return self.search(key) is not None

    def range_scan(self, low, high):
        """Return every (key, value) pair with low <= key <= high, ascending."""
        self._check_key(low)
        self._check_key(high)
        result = []
        if low > high:
            return result
        node = self._find_leaf(low)
        while node is not None:
            for pos in range(len(node.keys)):
                key = node.keys[pos]
                if key <= low:
                    continue
                if key > high:
                    return result
                result.append((key, node.values[pos]))
            node = node.next
        return result

    def __iter__(self):
        node = self._leftmost_leaf(self.root)
        pos = 0
        while node is not None:
            if pos >= len(node.keys):
                node = node.next
                pos = 1
                continue
            yield node.keys[pos], node.values[pos]
            pos += 1

    def keys(self):
        return [key for key, _ in self]

    def __len__(self):
        return self.size

    # ------------------------------------------------------------------
    # insertion
    # ------------------------------------------------------------------
    def insert(self, key, value):
        self._check_key(key)
        leaf = self._find_leaf(key)
        pos = bisect.bisect_left(leaf.keys, key)
        if pos < len(leaf.keys) and leaf.keys[pos] == key:
            leaf.values[pos] = value
            return
        leaf.keys.insert(pos, key)
        leaf.values.insert(pos, value)
        self.size += 1
        if len(leaf.keys) > MAX_KEYS:
            self._split_leaf(leaf)
        if pos == 0:
            self._refresh_upward(leaf)

    def _split_leaf(self, node):
        mid = len(node.keys) // 2
        sep = node.keys[mid - 1]
        right = Node(leaf=True)
        right.keys = node.keys[mid:]
        right.values = node.values[mid:]
        node.keys = node.keys[:mid]
        node.values = node.values[:mid]
        right.next = node.next
        node.next = right
        right.parent = node.parent
        self._insert_separator(node, sep, right)

    def _split_internal(self, node):
        mid = len(node.keys) // 2
        promote = node.keys[mid]
        right = Node(leaf=False)
        right.keys = node.keys[mid + 1:]
        right.children = node.children[mid + 1:]
        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]
        self._insert_separator(node, promote, right)

    def _insert_separator(self, left, key, right):
        parent = left.parent
        if parent is None:
            root = Node(leaf=False)
            root.keys = [key]
            root.children = [left, right]
            left.parent = root
            right.parent = root
            self.root = root
            return
        pos = parent.children.index(left)
        parent.keys.insert(pos, key)
        parent.children.insert(pos + 1, right)
        right.parent = parent
        if len(parent.keys) > MAX_KEYS:
            self._split_internal(parent)

    # ------------------------------------------------------------------
    # deletion
    # ------------------------------------------------------------------
    def delete(self, key):
        self._check_key(key)
        leaf = self._find_leaf(key)
        pos = bisect.bisect_left(leaf.keys, key)
        if pos >= len(leaf.keys) or leaf.keys[pos] != key:
            return False
        del leaf.keys[pos]
        del leaf.values[pos]
        self.size -= 1
        self._rebalance(leaf)
        self._refresh_upward(self._find_leaf(key))
        return True

    def _rebalance(self, node):
        while node is not self.root and len(node.keys) < MIN_KEYS:
            parent = node.parent
            pos = parent.children.index(node)
            right = parent.children[pos + 1] if pos + 1 < len(parent.children) else None
            left = parent.children[pos - 1] if pos > 0 else None
            if right is not None and len(right.keys) >= MIN_KEYS:
                self._borrow_from_right(node, parent, pos, right)
                return
            if left is not None and len(left.keys) > MIN_KEYS:
                self._borrow_from_left(node, parent, pos, left)
                return
            if right is not None:
                self._merge(parent, pos)
            else:
                self._merge(parent, pos - 1)
            node = parent
        while not self.root.leaf and len(self.root.children) == 1:
            self.root = self.root.children[0]
            self.root.parent = None
            self.height -= 1

    @staticmethod
    def _borrow_from_right(node, parent, pos, right):
        if node.leaf:
            node.keys.append(right.keys.pop(0))
            node.values.append(right.values.pop(0))
            parent.keys[pos] = right.keys[0]
            return
        sep = parent.keys[pos]
        moved = right.keys.pop(0)
        child = right.children.pop(0)
        node.keys.append(sep)
        node.children.append(child)
        child.parent = node
        parent.keys[pos] = moved

    @staticmethod
    def _borrow_from_left(node, parent, pos, left):
        if node.leaf:
            moved = left.keys.pop()
            node.keys.insert(0, moved)
            node.values.insert(0, left.values.pop())
            parent.keys[pos - 1] = moved
            return
        sep = parent.keys[pos - 1]
        moved = left.keys.pop()
        child = left.children.pop()
        node.keys.insert(0, sep)
        node.children.insert(0, child)
        child.parent = node
        parent.keys[pos - 1] = moved

    @staticmethod
    def _merge(parent, pos):
        left = parent.children[pos]
        right = parent.children[pos + 1]
        sep = parent.keys.pop(pos)
        parent.children.pop(pos + 1)
        if left.leaf:
            left.keys.extend(right.keys)
            left.values.extend(right.values)
            left.next = right.next
        else:
            left.keys.extend(right.keys)
            for child in right.children:
                child.parent = left
            left.children.extend(right.children)
        right.parent = None
        return left
