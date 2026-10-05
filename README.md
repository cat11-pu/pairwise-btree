# pairwise-btree

A small ordered index over integer keys, built with the Python standard library
only. `btree/core.py` contains the B+ tree kernel: key/value pairs are stored in
the leaves, the leaves are chained in ascending key order, internal nodes keep
routing separators, and the tree exposes search, insert, delete, range scan and
in-order iteration.

## Layout

    btree/__init__.py
    btree/core.py          B+ tree kernel
    tests/__init__.py
    tests/test_core.py     9 unittest cases

## Requirements

Python 3.8 or newer, nothing else. No third-party packages and no network access
are needed to build or test this project.

## Running the tests

From the project root:

    python3 -m unittest discover -s tests -v

On Windows with the default installation:

    py -3 -m unittest discover -s tests -v

A single case can be run with:

    python3 -m unittest tests.test_core.BPlusTreeTest.test_02_insert_and_search_in_ascending_order -v

## Usage

    from btree.core import BPlusTree

    tree = BPlusTree()
    tree.insert(3, "three")
    tree.insert(7, "seven")
    tree.search(3)          # "three"
    tree.range_scan(1, 10)  # [(3, "three"), (7, "seven")]
    tree.delete(3)
    list(tree)              # in-order (key, value) pairs

Keys must be `int`; any other key type raises `TypeError`. Node capacity is
fixed at 5 keys per node, with 2 keys as the minimum for every node except the
root. `len(tree)` reports the number of stored keys and `tree.height` reports
the height of the tree, with a single-node tree having height 1.
