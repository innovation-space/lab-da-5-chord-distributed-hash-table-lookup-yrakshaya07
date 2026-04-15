"""
simulation.py – SimPy discrete-event simulation of Chord lookups.

Each lookup is modelled as a chain of message-passing events. Every hop
incurs a network latency drawn from a configurable distribution.
Node joins and departures are also schedulable events.
"""

import random
import simpy
import math
from dataclasses import dataclass, field
from typing import Optional
from chord import ChordRing, sha1_id


# ──────────────────────────────────────────────
# Result containers
# ──────────────────────────────────────────────

@dataclass
class LookupEvent:
    key: int
    start_node: int
    hops: list
    responsible: Optional[int]
    sim_time: float          # SimPy clock time at completion
    wall_hops: int           # number of hops (logical)
    latency_ms: float        # simulated latency in ms


@dataclass
class TopologyEvent:
    kind: str                # "join" | "leave"
    node_id: int
    sim_time: float


@dataclass
class SimulationResult:
    lookup_events: list[LookupEvent] = field(default_factory=list)
    topology_events: list[TopologyEvent] = field(default_factory=list)
    ring_snapshots: dict[float, list[int]] = field(default_factory=dict)  # time→node_ids


# ──────────────────────────────────────────────
# Simulator
# ──────────────────────────────────────────────

class ChordSimulator:
    """
    Wraps a ChordRing and drives it with SimPy events.

    Parameters
    ----------
    m               : Chord bit-width (ring size = 2^m)
    initial_nodes   : list of node IDs to pre-populate
    hop_latency_ms  : mean per-hop network delay (exponential distribution)
    seed            : random seed
    """

    def __init__(
        self,
        m: int = 6,
        initial_nodes: Optional[list] = None,
        hop_latency_ms: float = 5.0,
        seed: int = 42,
    ):
        self.m = m
        self.hop_latency_ms = hop_latency_ms
        random.seed(seed)

        self.ring = ChordRing(m=m)
        self.result = SimulationResult()
        self._env = simpy.Environment()

        # Build initial ring
        if initial_nodes:
            for nid in initial_nodes:
                self.ring.add_node(nid % (2 ** m))
        self._snapshot(0.0)

    # ── public API ────────────────────────────

    def schedule_lookup(self, key: int, start_node_id: Optional[int] = None, at: float = 0.0):
        self._env.process(self._lookup_proc(key, start_node_id, at))

    def schedule_join(self, node_id: int, at: float):
        self._env.process(self._join_proc(node_id, at))

    def schedule_leave(self, node_id: int, at: float):
        self._env.process(self._leave_proc(node_id, at))

    def run(self, until: float = 500.0):
        self._env.run(until=until)

    # ── SimPy processes ───────────────────────

    def _lookup_proc(self, key: int, start_node_id: Optional[int], at: float):
        yield self._env.timeout(at)
        if not self.ring.nodes:
            return
        result = self.ring.lookup(key, start_node_id=start_node_id)
        hops = result["hops"]
        n_hops = result["latency"]

        # Simulate per-hop latency (exponential jitter)
        total_latency = sum(
            random.expovariate(1.0 / self.hop_latency_ms)
            for _ in range(max(n_hops, 1))
        )
        yield self._env.timeout(total_latency)

        self.result.lookup_events.append(LookupEvent(
            key=key,
            start_node=hops[0] if hops else -1,
            hops=hops,
            responsible=result["responsible"],
            sim_time=self._env.now,
            wall_hops=n_hops,
            latency_ms=total_latency,
        ))

    def _join_proc(self, node_id: int, at: float):
        yield self._env.timeout(at)
        nid = node_id % (2 ** self.m)
        self.ring.add_node(nid)
        self.result.topology_events.append(TopologyEvent("join", nid, self._env.now))
        self._snapshot(self._env.now)

    def _leave_proc(self, node_id: int, at: float):
        yield self._env.timeout(at)
        nid = node_id % (2 ** self.m)
        ok = self.ring.remove_node(nid)
        if ok:
            self.result.topology_events.append(TopologyEvent("leave", nid, self._env.now))
            self._snapshot(self._env.now)

    def _snapshot(self, t: float):
        self.result.ring_snapshots[t] = sorted(self.ring.nodes.keys())


# ──────────────────────────────────────────────
# Convenience: scalability experiment
# ──────────────────────────────────────────────

def scalability_experiment(
    node_counts: list[int],
    m: int = 8,
    samples_per_ring: int = 300,
    hop_latency_ms: float = 5.0,
    seed: int = 0,
) -> list[dict]:
    """
    For each node count N, build a ring and measure average lookup hops.
    Returns list of {"N": int, "avg_hops": float, "log2N": float}.
    """
    results = []
    for N in node_counts:
        random.seed(seed)
        ring = ChordRing(m=m)
        # Distribute nodes evenly (or randomly)
        node_ids = sorted(random.sample(range(2 ** m), min(N, 2 ** m)))
        for nid in node_ids:
            ring.add_node(nid)
        avg = ring.avg_lookup_hops(num_samples=samples_per_ring)
        results.append({
            "N": len(ring.nodes),
            "avg_hops": avg,
            "log2N": math.log2(len(ring.nodes)) if len(ring.nodes) > 1 else 0,
        })
    return results
