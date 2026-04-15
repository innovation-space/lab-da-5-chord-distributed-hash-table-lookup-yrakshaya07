Chord DHT Simulator
===================
Discrete-Event Simulation of the Chord Peer-to-Peer Lookup Protocol
Built with SimPy and Streamlit


OVERVIEW
--------
The Chord protocol organises distributed nodes in a logical ring and
routes key lookups in O(log N) hops using finger tables. This simulator
provides a complete, interactive environment to:

- Build an N-node Chord ring with configurable bit-width m (ring has 2^m slots)
- Inspect every node's finger table and successor/predecessor pointers
- Animate hop-by-hop lookups on the ring topology
- Run a full SimPy discrete-event simulation with scheduled lookups,
  node joins, and node departures, each hop incurring randomised network latency
- Plot a scalability chart that empirically confirms the O(log N) guarantee


FILE STRUCTURE
--------------
chord_sim/
    chord.py          Core Chord ring arithmetic (finger tables, lookup, join, leave)
    simulation.py     SimPy DES engine (ChordSimulator, scalability_experiment)
    app.py            Streamlit front-end with five tabs
    requirements.txt  Python dependencies
    README.md         This file


SETUP AND INSTALLATION
-----------------------

Prerequisites
    Python 3.11 or later (3.12 recommended)
    pip package manager

Step 1 — Create a virtual environment (recommended)

    python -m venv .venv

    Windows:
        .venv\Scripts\activate

    macOS or Linux:
        source .venv/bin/activate

Step 2 — Install dependencies

    pip install -r requirements.txt

    Dependencies:

    Package       Purpose
    ----------    ----------------------------
    streamlit     Web user interface
    simpy         Discrete-event simulation engine
    plotly        Interactive ring topology and charts
    pandas        Tabular data display

Step 3 — Run the application

    streamlit run app.py

    The browser will open at http://localhost:8501


HOW TO USE — TAB BY TAB
------------------------

Sidebar — Ring Configuration

    Control              What it does
    -------              ------------
    Bit width m          Sets ring size to 2^m. For example, m=6 gives 64 slots.
    Initial node count   Number of nodes to randomly place in the ring
    Random seed          Makes the ring layout reproducible across runs
    Build Ring           Constructs the ring and computes all finger tables
    Join                 Add a specific node ID to the live ring
    Leave                Remove a selected node from the live ring

Always click Build Ring after adjusting the sliders before using any tab.


Tab 1 — Ring Topology

    Displays all nodes on a circular ring. After running a lookup, the
    diagram highlights the path:

    Green node    : lookup start node
    Orange nodes  : intermediate hop nodes
    Red node      : responsible node (lookup destination)
    Yellow diamond: the key being looked up

    A table below lists successor, predecessor, and key count for every node.


Tab 2 — Finger Tables

    Select any node from the dropdown. The display shows:

    - The finger table with columns i, start value, and responsible node
    - Metrics: successor, predecessor, and number of stored keys
    - A ring diagram with all finger pointer arrows drawn for the selected node

    This lets you visually confirm that finger[i] points approximately
    2^i positions ahead on the ring, with reach doubling for each entry.


Tab 3 — Lookup Animation

    1. Enter a key (integer in the range 0 to 2^m minus 1)
    2. Choose a starting node
    3. Enable Animate hops for a step-by-step replay with 0.5 second delays
    4. Click Run Lookup

    The ring diagram highlights each hop in order. Below the diagram you
    will see the number of hops taken, the responsible node, and the
    theoretical ceiling of log base 2 of N for comparison.


Tab 4 — SimPy Simulation

    Run a complete discrete-event simulation.

    Setting                  Description
    -------                  -----------
    Number of random lookups Lookups spread uniformly over simulated time
    Mean hop latency (ms)    Each hop delays by Exponential(mean) milliseconds
    Simulation seed          Reproducible randomness
    Node IDs to JOIN         Comma-separated list of IDs that join mid-simulation
    JOIN times (ms)          Simulated clock times for each join event
    Node IDs to LEAVE        IDs that leave mid-simulation
    LEAVE times (ms)         Clock times for each departure event

    Example churn scenario input:
        Node IDs to JOIN:   10, 45
        JOIN times:         50, 120
        Node IDs to LEAVE:  17, 47
        LEAVE times:        80, 150

    After running, the tab displays:
    - Summary metrics: lookups simulated, average hops, max hops, average latency
    - Hop count histogram
    - Latency scatter plot over simulated time
    - Full event log table
    - Topology event log showing join and leave times


Tab 5 — Scalability O(log N)

    Runs a Monte Carlo experiment across many ring sizes. For each value of N:
    1. A new ring is constructed with N randomly placed nodes
    2. A configurable number of random lookups are measured for hop count
    3. The mean is plotted alongside the theoretical half-log-N curve

    This empirically confirms Chord's O(log N) routing guarantee.


PROTOCOL BACKGROUND
-------------------

Chord Ring

    Nodes and keys are assigned IDs in the range [0, 2^m) using a consistent
    hash function. Nodes are arranged in a logical ring in ascending ID order.

    Key responsibility rule:
        A key k is owned by the first node with ID greater than or equal to k,
        wrapping around the ring if necessary. This node is called the successor
        of k.

Finger Table

    Each node n maintains m finger table entries:

        finger[i].start     = (n + 2^i) mod 2^m
        finger[i].successor = first node with ID >= finger[i].start

    This exponential spacing allows lookups to skip roughly half the remaining
    distance to the target with each hop.

Lookup Algorithm

    find_successor(id):
        if id is in the range (n, successor]:
            return successor
        else:
            n_prime = closest_preceding_finger(id)
            return n_prime.find_successor(id)

    closest_preceding_finger scans the finger table from the largest entry
    to the smallest and returns the first finger that falls strictly between
    the current node and the target key.

    Complexity: O(log N) hops with high probability.

Node Join

    When a new node n joins:
    1. It locates its correct position using its hashed ID
    2. It takes ownership of keys in the range (predecessor, n]
    3. All finger tables are recomputed

Node Departure

    When node n leaves:
    1. Its keys are transferred to its successor
    2. All finger tables are recomputed


SIMPY SIMULATION DESIGN
------------------------

    ChordSimulator
        simpy.Environment          Discrete-event clock
        ChordRing                  Ring state, mutated by join and leave events
        _lookup_proc(key, at)      SimPy process: waits until time at, then
                                   routes the lookup and applies per-hop delays
        _join_proc(node_id, at)    SimPy process: waits until time at, then
                                   calls ring.add_node
        _leave_proc(node_id, at)   SimPy process: waits until time at, then
                                   calls ring.remove_node

    Every hop incurs an independent Exponential(1/mean) delay. This makes
    the total lookup latency a sum of exponentials, which follows an
    Erlang-k distribution for k hops.


QUICK TEST FROM THE COMMAND LINE
---------------------------------

    from chord import ChordRing

    ring = ChordRing(m=6)
    for nid in [1, 8, 14, 17, 47, 61]:
        ring.add_node(nid)

    result = ring.lookup(key=20, start_node_id=1)
    print(result)
    # Expected: {'hops': [1, 17, 47], 'responsible': 47, 'latency': 2}


TROUBLESHOOTING
---------------

    Problem                         Fix
    -------                         ---
    ModuleNotFoundError: simpy      Run: pip install simpy
    Port 8501 in use                Run: streamlit run app.py --server.port 8502
    Ring shows 0 nodes              Click Build Ring in the sidebar first
    Lookup hops exceed log N        Normal for very small rings (N less than 4)
    Browser does not open           Navigate manually to http://localhost:8501




REFERENCES
----------

    Stoica, I., Morris, R., Karger, D., Kaashoek, M. F., and Balakrishnan, H.
    Chord: A Scalable Peer-to-peer Lookup Service for Internet Applications.
    ACM SIGCOMM Computer Communication Review, 31(4), 149-160, 2001.

    SimPy Documentation: https://simpy.readthedocs.io
    Streamlit Documentation: https://docs.streamlit.io


Built with SimPy 4, Streamlit, Plotly, Python 3.11 or later.
