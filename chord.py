"""
chord.py – Core Chord DHT data structures and lookup logic.
No SimPy dependency here; pure ring arithmetic so it can also be unit-tested.
"""

import hashlib
import math
from dataclasses import dataclass, field
from typing import Optional


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def sha1_id(value: str, m: int) -> int:
    """Return a Chord node/key ID in [0, 2^m)."""
    h = int(hashlib.sha1(value.encode()).hexdigest(), 16)
    return h % (2 ** m)


def in_range(x: int, start: int, end: int, m: int, inclusive_end: bool = True) -> bool:
    """
    True if x is in the half-open arc (start, end] on a ring of size 2^m.
    If inclusive_end=False the arc is (start, end).
    """
    ring = 2 ** m
    if start == end:
        return True          # degenerate single-node ring
    if start < end:
        if inclusive_end:
            return start < x <= end
        return start < x < end
    else:                    # wraps around
        if inclusive_end:
            return x > start or x <= end
        return x > start or x < end


# ──────────────────────────────────────────────
# Node
# ──────────────────────────────────────────────

@dataclass
class FingerEntry:
    start: int          # (node_id + 2^i) mod 2^m
    node_id: int        # ID of the node responsible for 'start'


@dataclass
class ChordNode:
    node_id: int
    m: int              # number of bits
    successor: Optional["ChordNode"] = field(default=None, repr=False)
    predecessor: Optional["ChordNode"] = field(default=None, repr=False)
    finger_table: list[FingerEntry] = field(default_factory=list, repr=False)
    data: dict = field(default_factory=dict, repr=False)   # key→value store

    def __post_init__(self):
        self.finger_table = []

    def __hash__(self):
        return hash(self.node_id)

    def __eq__(self, other):
        return isinstance(other, ChordNode) and self.node_id == other.node_id


# ──────────────────────────────────────────────
# Ring
# ──────────────────────────────────────────────

class ChordRing:
    """Maintains a consistent Chord ring of ChordNode objects."""

    def __init__(self, m: int = 6):
        self.m = m
        self.ring_size = 2 ** m
        self.nodes: dict[int, ChordNode] = {}   # node_id → ChordNode

    # ── node management ──────────────────────

    def add_node(self, node_id: int) -> ChordNode:
        if node_id in self.nodes:
            return self.nodes[node_id]
        node = ChordNode(node_id=node_id, m=self.m)
        self.nodes[node_id] = node
        self._rebuild()
        return node

    def remove_node(self, node_id: int) -> bool:
        if node_id not in self.nodes:
            return False
        # Migrate keys to successor
        leaving = self.nodes[node_id]
        if leaving.successor and leaving.successor is not leaving:
            leaving.successor.data.update(leaving.data)
        del self.nodes[node_id]
        self._rebuild()
        return True

    def _rebuild(self):
        """Recompute successor/predecessor/finger tables for every node."""
        if not self.nodes:
            return
        sorted_ids = sorted(self.nodes)
        n = len(sorted_ids)

        for idx, nid in enumerate(sorted_ids):
            node = self.nodes[nid]
            node.successor   = self.nodes[sorted_ids[(idx + 1) % n]]
            node.predecessor = self.nodes[sorted_ids[(idx - 1) % n]]

        for node in self.nodes.values():
            node.finger_table = []
            for i in range(self.m):
                start = (node.node_id + 2 ** i) % self.ring_size
                responsible = self._find_successor_id(start)
                node.finger_table.append(FingerEntry(start=start, node_id=responsible))

    def _find_successor_id(self, key: int) -> int:
        """Return the node_id responsible for key (O(log N) via sorted list)."""
        sorted_ids = sorted(self.nodes)
        for nid in sorted_ids:
            if nid >= key:
                return nid
        return sorted_ids[0]   # wrap-around

    # ── lookup with hop trace ─────────────────

    def lookup(self, key: int, start_node_id: Optional[int] = None) -> dict:
        """
        Simulate a Chord finger-table lookup.
        Returns a dict with:
          - hops: list of node_ids visited
          - responsible: node_id that owns the key
          - latency: number of hops
        """
        if not self.nodes:
            return {"hops": [], "responsible": None, "latency": 0}

        sorted_ids = sorted(self.nodes)
        if start_node_id is None or start_node_id not in self.nodes:
            start_node_id = sorted_ids[0]

        target = self._find_successor_id(key)
        hops = [start_node_id]
        current_id = start_node_id

        # If the starting node IS the responsible node
        if current_id == target:
            return {"hops": hops, "responsible": target, "latency": 0}

        visited = set([current_id])
        for _ in range(self.m + 2):           # safety cap
            current = self.nodes[current_id]
            # Check if successor owns the key
            succ_id = current.successor.node_id
            if in_range(key, current_id, succ_id, self.m, inclusive_end=True):
                hops.append(succ_id)
                return {"hops": hops, "responsible": succ_id, "latency": len(hops) - 1}

            # Find closest preceding finger
            next_id = self._closest_preceding_finger(current, key)
            if next_id == current_id or next_id in visited:
                # Fallback: jump to successor
                hops.append(succ_id)
                return {"hops": hops, "responsible": succ_id, "latency": len(hops) - 1}

            hops.append(next_id)
            visited.add(next_id)
            current_id = next_id

        return {"hops": hops, "responsible": target, "latency": len(hops) - 1}

    def _closest_preceding_finger(self, node: ChordNode, key: int) -> int:
        for entry in reversed(node.finger_table):
            fid = entry.node_id
            if in_range(fid, node.node_id, key, self.m, inclusive_end=False):
                return fid
        return node.node_id

    # ── key insertion ─────────────────────────

    def insert_key(self, key: int, value: str = "") -> int:
        """Insert key into the ring; returns the responsible node_id."""
        responsible_id = self._find_successor_id(key)
        self.nodes[responsible_id].data[key] = value
        return responsible_id

    # ── stats ─────────────────────────────────

    def avg_lookup_hops(self, num_samples: int = 200) -> float:
        """Monte-Carlo estimate of average lookup hops."""
        import random
        if len(self.nodes) < 2:
            return 0.0
        node_ids = list(self.nodes)
        total = 0
        for _ in range(num_samples):
            key = random.randint(0, self.ring_size - 1)
            src = random.choice(node_ids)
            result = self.lookup(key, start_node_id=src)
            total += result["latency"]
        return total / num_samples
