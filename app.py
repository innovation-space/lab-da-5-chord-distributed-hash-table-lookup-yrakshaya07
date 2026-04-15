"""
app.py – Streamlit front-end for the Chord DHT Simulation.

Run with:
    streamlit run app.py
"""

import math
import random
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from chord import ChordRing, sha1_id
from simulation import ChordSimulator, scalability_experiment

# ══════════════════════════════════════════════
# Page config
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="Chord DHT Simulator",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════
# Custom CSS
# ══════════════════════════════════════════════
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Space+Grotesk:wght@300;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
}
code, pre, .stCode { font-family: 'JetBrains Mono', monospace; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f0f1a 0%, #1a1a2e 100%);
    border-right: 1px solid #2d2d4e;
}
section[data-testid="stSidebar"] * { color: #c9d1f5 !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #7b8cff !important; }

/* Main area */
.main .block-container { padding-top: 1.5rem; }

/* Metric cards */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border: 1px solid #2d2d4e;
    border-radius: 12px;
    padding: 1rem 1.5rem;
}
div[data-testid="metric-container"] label { color: #7b8cff !important; font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #e8eaff !important; font-family: 'JetBrains Mono'; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #12122a; border-radius: 8px; padding: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 6px; color: #7b8cff; font-weight: 500; }
.stTabs [aria-selected="true"] { background: #2d2d6e !important; color: #c9d1f5 !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(90deg, #3d3d9e, #5555cc);
    color: white; border: none; border-radius: 8px;
    font-family: 'Space Grotesk'; font-weight: 700;
    transition: all 0.2s;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 20px rgba(100,100,255,0.4); }

/* Hop badge */
.hop-badge {
    display: inline-block; background: #2d2d6e;
    border: 1px solid #5555cc; border-radius: 6px;
    padding: 2px 10px; margin: 2px; font-family: 'JetBrains Mono';
    font-size: 0.85rem; color: #c9d1f5;
}
.hop-badge.start  { background: #1a4a1a; border-color: #4aff4a; color: #4aff4a; }
.hop-badge.end    { background: #4a1a1a; border-color: #ff6b6b; color: #ff6b6b; }

h1, h2, h3 { color: #c9d1f5 !important; }
.stDataFrame { background: #1a1a2e; }
</style>
""",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════
# Session state initialisation
# ══════════════════════════════════════════════
def init_state():
    if "ring" not in st.session_state:
        st.session_state.ring = None
    if "m" not in st.session_state:
        st.session_state.m = 6
    if "lookup_result" not in st.session_state:
        st.session_state.lookup_result = None
    if "sim_result" not in st.session_state:
        st.session_state.sim_result = None

init_state()

# ══════════════════════════════════════════════
# Sidebar – ring configuration
# ══════════════════════════════════════════════
with st.sidebar:
    st.title("⚙️ Chord Config")
    st.markdown("---")

    m = st.slider("Bit width m (ring = 2^m)", 3, 8, 6, key="m_slider")
    st.caption(f"Ring has **{2**m}** slots  |  max **{2**m}** nodes")

    st.markdown("### 🟢 Node Setup")
    node_count = st.slider("Initial node count", 2, min(2**m, 40), min(8, 2**m // 2))
    seed = st.number_input("Random seed", value=42, step=1)

    if st.button("🔄 Build Ring", use_container_width=True):
        random.seed(int(seed))
        ring = ChordRing(m=m)
        node_ids = random.sample(range(2**m), node_count)
        for nid in node_ids:
            ring.add_node(nid)
        st.session_state.ring = ring
        st.session_state.m = m
        st.session_state.lookup_result = None
        st.success(f"Ring built with {node_count} nodes!")

    st.markdown("---")
    st.markdown("### ➕ Join / ➖ Leave")
    col1, col2 = st.columns(2)
    with col1:
        join_id = st.number_input("Node ID to join", 0, 2**m - 1, value=0, key="join_id")
        if st.button("Join", use_container_width=True):
            if st.session_state.ring:
                st.session_state.ring.add_node(int(join_id))
                st.success(f"Node {join_id} joined!")
            else:
                st.warning("Build a ring first.")
    with col2:
        if st.session_state.ring and st.session_state.ring.nodes:
            leave_id = st.selectbox("Leave", sorted(st.session_state.ring.nodes.keys()))
            if st.button("Leave", use_container_width=True):
                st.session_state.ring.remove_node(int(leave_id))
                st.info(f"Node {leave_id} left.")
        else:
            st.selectbox("Leave", [], disabled=True)
            st.button("Leave", disabled=True, use_container_width=True)

    st.markdown("---")
    st.caption("Chord DHT Simulator • SimPy + Streamlit")

# ══════════════════════════════════════════════
# Helper: ring topology figure
# ══════════════════════════════════════════════

def ring_figure(ring: ChordRing, highlight_hops=None, lookup_key=None):
    """Draw the Chord ring as a Plotly polar scatter + lines."""
    m = ring.m
    ring_size = 2 ** m
    sorted_ids = sorted(ring.nodes.keys())
    N = len(sorted_ids)

    angles = {nid: (nid / ring_size) * 2 * math.pi for nid in sorted_ids}

    def polar(nid, r=1.0):
        a = angles[nid]
        return r * math.cos(a), r * math.sin(a)

    fig = go.Figure()

    # ── Background ring circle ──
    theta_bg = [i / 360 * 2 * math.pi for i in range(361)]
    fig.add_trace(go.Scatter(
        x=[math.cos(t) for t in theta_bg],
        y=[math.sin(t) for t in theta_bg],
        mode="lines",
        line=dict(color="#2d2d4e", width=2),
        hoverinfo="skip", showlegend=False,
    ))

    # ── Successor arcs ──
    for i, nid in enumerate(sorted_ids):
        succ_id = sorted_ids[(i + 1) % N]
        x0, y0 = polar(nid)
        x1, y1 = polar(succ_id)
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            mode="lines",
            line=dict(color="#3d3d6e", width=1.5, dash="dot"),
            hoverinfo="skip", showlegend=False,
        ))

    # ── Lookup path ──
    if highlight_hops and len(highlight_hops) > 1:
        for i in range(len(highlight_hops) - 1):
            a, b = highlight_hops[i], highlight_hops[i + 1]
            if a in angles and b in angles:
                x0, y0 = polar(a, r=0.95)
                x1, y1 = polar(b, r=0.95)
                fig.add_trace(go.Scatter(
                    x=[x0, x1], y=[y0, y1],
                    mode="lines+markers",
                    line=dict(color="#ff9900", width=3),
                    marker=dict(symbol="arrow", size=12, color="#ff9900",
                                angleref="previous"),
                    hoverinfo="skip", showlegend=False,
                ))

    # ── Nodes ──
    colors, sizes, texts, hovers = [], [], [], []
    hop_set = set(highlight_hops) if highlight_hops else set()
    for nid in sorted_ids:
        if highlight_hops and nid == highlight_hops[0]:
            colors.append("#4aff4a"); sizes.append(22)
        elif highlight_hops and nid == highlight_hops[-1]:
            colors.append("#ff6b6b"); sizes.append(22)
        elif nid in hop_set:
            colors.append("#ff9900"); sizes.append(18)
        else:
            colors.append("#7b8cff"); sizes.append(14)
        texts.append(str(nid))
        node = ring.nodes[nid]
        succ = node.successor.node_id if node.successor else "–"
        pred = node.predecessor.node_id if node.predecessor else "–"
        hovers.append(f"Node {nid}<br>Succ: {succ}<br>Pred: {pred}")

    xs = [polar(nid)[0] for nid in sorted_ids]
    ys = [polar(nid)[1] for nid in sorted_ids]
    fig.add_trace(go.Scatter(
        x=xs, y=ys,
        mode="markers+text",
        marker=dict(color=colors, size=sizes,
                    line=dict(color="#1a1a2e", width=2)),
        text=texts, textposition="top center",
        textfont=dict(color="#e8eaff", size=11, family="JetBrains Mono"),
        hovertext=hovers, hoverinfo="text",
        showlegend=False,
    ))

    # ── Key marker ──
    if lookup_key is not None:
        angle_key = (lookup_key / ring_size) * 2 * math.pi
        xk = 1.12 * math.cos(angle_key)
        yk = 1.12 * math.sin(angle_key)
        fig.add_trace(go.Scatter(
            x=[xk], y=[yk], mode="markers+text",
            marker=dict(symbol="diamond", size=14, color="#ffff00",
                        line=dict(color="#ff9900", width=2)),
            text=[f"k={lookup_key}"], textposition="top center",
            textfont=dict(color="#ffff00", size=10),
            hovertext=[f"Key {lookup_key}"], hoverinfo="text",
            showlegend=False,
        ))

    fig.update_layout(
        paper_bgcolor="#0f0f1a",
        plot_bgcolor="#0f0f1a",
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(visible=False, range=[-1.4, 1.4]),
        yaxis=dict(visible=False, range=[-1.4, 1.4], scaleanchor="x"),
        height=500,
    )
    return fig


# ══════════════════════════════════════════════
# Main content
# ══════════════════════════════════════════════

st.markdown("# 🔗 Chord DHT Simulator")
st.caption("Discrete-event simulation of the Chord Peer-to-Peer Lookup Protocol · SimPy + Streamlit")

if not st.session_state.ring:
    st.info("👈 Configure and build a ring from the sidebar to get started.")
    st.stop()

ring: ChordRing = st.session_state.ring
m = ring.m
ring_size = 2 ** m
sorted_ids = sorted(ring.nodes.keys())

# ── Top metrics ──
c1, c2, c3, c4 = st.columns(4)
c1.metric("Nodes in Ring", len(ring.nodes))
c2.metric("Ring Size (2^m)", ring_size)
c3.metric("Bit Width (m)", m)
theory_hops = math.log2(len(ring.nodes)) / 2 if len(ring.nodes) > 1 else 0
c4.metric("Theoretical Avg Hops", f"≈ {theory_hops:.2f}")

st.markdown("---")

# ══════════════════════════════════════════════
# Tabs
# ══════════════════════════════════════════════
tab_ring, tab_ft, tab_lookup, tab_sim, tab_scale = st.tabs([
    "🌐 Ring Topology",
    "📋 Finger Tables",
    "🔍 Lookup Animation",
    "⚡ SimPy Simulation",
    "📈 Scalability O(log N)",
])

# ─────────────────────────────────────────────
# Tab 1: Ring Topology
# ─────────────────────────────────────────────
with tab_ring:
    st.subheader("Ring Topology")
    lr = st.session_state.lookup_result
    hops = lr["hops"] if lr else None
    key_disp = lr["key"] if lr else None
    st.plotly_chart(ring_figure(ring, highlight_hops=hops, lookup_key=key_disp),
                    use_container_width=True, key="ring_topology_main")
    if hops:
        st.markdown("**Last lookup path:**  " +
                    "".join(f'<span class="hop-badge {"start" if i==0 else "end" if i==len(hops)-1 else ""}">'
                            f'{"▶ " if i==0 else "★ " if i==len(hops)-1 else "→ "}{h}</span>'
                            for i, h in enumerate(hops)),
                    unsafe_allow_html=True)

    st.markdown("#### Node Details")
    rows = []
    for nid in sorted_ids:
        n = ring.nodes[nid]
        rows.append({
            "Node ID": nid,
            "Successor": n.successor.node_id if n.successor else "–",
            "Predecessor": n.predecessor.node_id if n.predecessor else "–",
            "Keys stored": len(n.data),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# Tab 2: Finger Tables
# ─────────────────────────────────────────────
with tab_ft:
    st.subheader("Finger Table Explorer")
    selected_node = st.selectbox("Select a node", sorted_ids, key="ft_node")
    node = ring.nodes[selected_node]

    ft_rows = []
    for i, fe in enumerate(node.finger_table):
        ft_rows.append({
            "i": i,
            "start  (n + 2^i) mod 2^m": fe.start,
            "successor (node responsible)": fe.node_id,
        })

    col_ft, col_info = st.columns([2, 1])
    with col_ft:
        st.dataframe(pd.DataFrame(ft_rows), use_container_width=True, hide_index=True)
    with col_info:
        st.metric("Node", selected_node)
        st.metric("Successor", node.successor.node_id if node.successor else "–")
        st.metric("Predecessor", node.predecessor.node_id if node.predecessor else "–")
        st.metric("Keys stored", len(node.data))
        if node.data:
            st.write("**Keys:**", list(node.data.keys()))

    # Finger table visualised on ring
    st.markdown("#### Finger pointers on ring")
    fig_ft = ring_figure(ring)
    angles = {nid: (nid / ring_size) * 2 * math.pi for nid in sorted_ids}

    def polar(nid, r=1.0):
        a = (nid / ring_size) * 2 * math.pi
        return r * math.cos(a), r * math.sin(a)

    for fe in node.finger_table:
        if fe.node_id in angles:
            x0, y0 = polar(selected_node, r=0.85)
            x1, y1 = polar(fe.node_id, r=0.85)
            fig_ft.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(color="rgba(255,153,0,0.35)", width=1.5),
                hoverinfo="skip", showlegend=False,
            ))
    st.plotly_chart(fig_ft, use_container_width=True, key="finger_table_ring")

# ─────────────────────────────────────────────
# Tab 3: Lookup Animation
# ─────────────────────────────────────────────
with tab_lookup:
    st.subheader("Hop-by-Hop Lookup")
    col_l, col_r = st.columns([1, 2])
    with col_l:
        lookup_key = st.number_input("Key to look up", 0, ring_size - 1, value=ring_size // 3,
                                     key="lookup_key_input")
        start_node = st.selectbox("Starting node", sorted_ids, key="lookup_start")
        animate = st.checkbox("Animate hops (0.5 s delay)", value=True)
        run_lookup = st.button("🔍 Run Lookup", use_container_width=True)

    if run_lookup:
        result = ring.lookup(int(lookup_key), start_node_id=int(start_node))
        result["key"] = int(lookup_key)
        st.session_state.lookup_result = result

    lr = st.session_state.lookup_result
    if lr:
        hops = lr["hops"]
        responsible = lr["responsible"]
        latency = lr["latency"]

        with col_r:
            if animate and run_lookup:
                placeholder = st.empty()
                for step in range(1, len(hops) + 1):
                    with placeholder.container():
                        st.plotly_chart(
                            ring_figure(ring, highlight_hops=hops[:step],
                                        lookup_key=lr["key"]),
                            use_container_width=True, key=f"lookup_anim_{step}")
                    time.sleep(0.5)
            else:
                st.plotly_chart(
                    ring_figure(ring, highlight_hops=hops, lookup_key=lr["key"]),
                    use_container_width=True, key="lookup_static")

        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("Hops taken", latency)
        m2.metric("Responsible node", str(responsible))
        m3.metric("⌈log₂ N⌉", math.ceil(math.log2(max(len(ring.nodes), 2))))

        st.markdown("**Hop sequence:**")
        hop_html = ""
        for i, h in enumerate(hops):
            cls = "start" if i == 0 else "end" if i == len(hops) - 1 else ""
            prefix = "▶ " if i == 0 else "★ " if i == len(hops) - 1 else f"→ "
            hop_html += f'<span class="hop-badge {cls}">{prefix}{h}</span>'
        st.markdown(hop_html, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Tab 4: SimPy Simulation
# ─────────────────────────────────────────────
with tab_sim:
    st.subheader("SimPy Discrete-Event Simulation")
    st.markdown("""
Run a full discrete-event simulation with **scheduled lookups**, **node joins**, and **node departures**.
Each hop incurs a randomly drawn network latency.
""")
    cs1, cs2 = st.columns(2)
    with cs1:
        num_lookups = st.slider("Number of random lookups", 10, 300, 50)
        hop_lat = st.slider("Mean hop latency (ms)", 1, 50, 5)
        sim_seed = st.number_input("Simulation seed", value=7, step=1, key="sim_seed")
    with cs2:
        join_nodes = st.text_input("Node IDs to JOIN (comma separated)", "")
        join_times = st.text_input("JOIN times (ms, comma separated)", "")
        leave_nodes = st.text_input("Node IDs to LEAVE (comma separated)", "")
        leave_times = st.text_input("LEAVE times (ms, comma separated)", "")

    run_sim = st.button("⚡ Run SimPy Simulation", use_container_width=True)
    if run_sim:
        sim = ChordSimulator(
            m=ring.m,
            initial_nodes=list(ring.nodes.keys()),
            hop_latency_ms=float(hop_lat),
            seed=int(sim_seed),
        )
        random.seed(int(sim_seed))
        spread = max(100.0, num_lookups * 2.0)
        node_ids = list(ring.nodes.keys())
        for _ in range(num_lookups):
            key = random.randint(0, ring_size - 1)
            start = random.choice(node_ids)
            at = random.uniform(0, spread * 0.8)
            sim.schedule_lookup(key, start_node_id=start, at=at)

        # Parse join/leave schedules
        def parse_list(s):
            try:
                return [int(x.strip()) for x in s.split(",") if x.strip()]
            except Exception:
                return []

        jn = parse_list(join_nodes)
        jt = parse_list(join_times)
        ln = parse_list(leave_nodes)
        lt_ = parse_list(leave_times)

        for nid, t in zip(jn, jt):
            sim.schedule_join(nid % ring_size, at=float(t))
        for nid, t in zip(ln, lt_):
            sim.schedule_leave(nid % ring_size, at=float(t))

        sim.run(until=spread)
        result = sim.result
        st.session_state.sim_result = result

    if st.session_state.sim_result:
        result = st.session_state.sim_result
        events = result.lookup_events
        if not events:
            st.warning("No lookup events recorded.")
        else:
            df = pd.DataFrame([{
                "Key": e.key,
                "Start Node": e.start_node,
                "Responsible Node": e.responsible,
                "Hops": e.wall_hops,
                "Latency (ms)": round(e.latency_ms, 2),
                "Sim Time": round(e.sim_time, 2),
            } for e in events])

            ma1, ma2, ma3, ma4 = st.columns(4)
            ma1.metric("Lookups simulated", len(events))
            ma2.metric("Avg hops", f"{df['Hops'].mean():.2f}")
            ma3.metric("Max hops", int(df['Hops'].max()))
            ma4.metric("Avg latency (ms)", f"{df['Latency (ms)'].mean():.1f}")

            col_hist, col_ts = st.columns(2)
            with col_hist:
                fig_h = px.histogram(df, x="Hops", nbins=ring.m + 2,
                                     title="Hop Count Distribution",
                                     color_discrete_sequence=["#7b8cff"])
                fig_h.update_layout(paper_bgcolor="#0f0f1a", plot_bgcolor="#0f0f1a",
                                    font_color="#c9d1f5")
                st.plotly_chart(fig_h, use_container_width=True, key="sim_hop_hist")
            with col_ts:
                fig_ts = px.scatter(df, x="Sim Time", y="Latency (ms)",
                                    color="Hops", title="Latency over Sim Time",
                                    color_continuous_scale="Plasma")
                fig_ts.update_layout(paper_bgcolor="#0f0f1a", plot_bgcolor="#0f0f1a",
                                     font_color="#c9d1f5")
                st.plotly_chart(fig_ts, use_container_width=True, key="sim_latency_scatter")

            st.markdown("#### Event Log (first 100)")
            st.dataframe(df.head(100), use_container_width=True, hide_index=True)

            # Topology events
            if result.topology_events:
                st.markdown("#### Topology Events")
                tdf = pd.DataFrame([{
                    "Type": e.kind.upper(),
                    "Node ID": e.node_id,
                    "Sim Time (ms)": round(e.sim_time, 2),
                } for e in result.topology_events])
                st.dataframe(tdf, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# Tab 5: Scalability
# ─────────────────────────────────────────────
with tab_scale:
    st.subheader("Scalability: O(log N) Lookup Hops")
    st.markdown("""
Chord guarantees that lookups complete in **O(log N)** hops.
This tab empirically verifies that claim across varying ring sizes.
""")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        m_scale = st.slider("Bit width m for experiment", 4, 10, 8, key="scale_m")
    with sc2:
        samples = st.slider("Monte-Carlo samples per ring", 50, 500, 200)
    with sc3:
        scale_seed = st.number_input("Seed", value=0, step=1, key="scale_seed")

    run_scale = st.button("📈 Run Scalability Experiment", use_container_width=True)
    if run_scale:
        node_counts = [2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256]
        node_counts = [n for n in node_counts if n <= 2 ** m_scale]
        with st.spinner("Running experiment across ring sizes…"):
            scale_data = scalability_experiment(
                node_counts, m=m_scale,
                samples_per_ring=samples,
                seed=int(scale_seed),
            )
        df_scale = pd.DataFrame(scale_data)

        fig_scale = go.Figure()
        fig_scale.add_trace(go.Scatter(
            x=df_scale["N"], y=df_scale["avg_hops"],
            mode="lines+markers", name="Measured avg hops",
            line=dict(color="#7b8cff", width=3),
            marker=dict(size=8, color="#7b8cff"),
        ))
        fig_scale.add_trace(go.Scatter(
            x=df_scale["N"], y=df_scale["log2N"] / 2,
            mode="lines", name="½·log₂(N)  (theory)",
            line=dict(color="#ff9900", width=2, dash="dash"),
        ))
        fig_scale.update_layout(
            title="Average Lookup Hops vs. Ring Size",
            xaxis_title="Number of Nodes (N)",
            yaxis_title="Average Hops",
            paper_bgcolor="#0f0f1a",
            plot_bgcolor="#0f0f1a",
            font_color="#c9d1f5",
            legend=dict(bgcolor="#1a1a2e"),
            height=450,
        )
        st.plotly_chart(fig_scale, use_container_width=True, key="scale_logn_chart")
        st.dataframe(df_scale.rename(columns={
            "N": "Nodes", "avg_hops": "Avg Hops", "log2N": "log₂(N)"
        }).round(3), use_container_width=True, hide_index=True)