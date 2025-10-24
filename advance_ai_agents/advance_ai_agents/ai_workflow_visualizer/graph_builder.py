import networkx as nx
import plotly.graph_objects as go
import random

def build_graph(nodes, edges):
    """Generate a glowing, animated Plotly network graph."""
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)
    pos = nx.spring_layout(G, seed=42, k=1.8)

    # Vibrant dynamic colors
    neon_colors = ['#FF3CAC', '#784BA0', '#2B86C5', '#00F5A0', '#FF9A8B', '#8EC5FC', '#F9F586']

    edge_traces = []
    for i, edge in enumerate(G.edges()):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        mid_x = (x0 + x1) / 2 + random.uniform(-0.05, 0.05)
        mid_y = (y0 + y1) / 2 + random.uniform(-0.05, 0.05)
        edge_traces.append(
            go.Scatter(
                x=[x0, mid_x, x1],
                y=[y0, mid_y, y1],
                mode='lines',
                line=dict(width=4, color=random.choice(neon_colors), shape='spline'),
                hoverinfo='none',
                opacity=0.8
            )
        )
    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode='markers+text',
        text=list(G.nodes()),
        textposition='bottom center',
        textfont=dict(size=16, color='#FFFFFF', family='Poppins, sans-serif'),
        marker=dict(
            size=45,
            color=[random.choice(neon_colors) for _ in G.nodes()],
            line=dict(width=3, color='white'),
            symbol='circle'
        ),
        hoverinfo='text'
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title=dict(
            text="💡 Live AI Agent Workflow",
            font=dict(size=30, color='#FFFFFF', family='Poppins, sans-serif'),
            x=0.5
        ),
        showlegend=False,
        hovermode='closest',
        paper_bgcolor='#0a0e27',
        plot_bgcolor='#0a0e27',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=650,
        margin=dict(t=80, b=40, l=20, r=20)
    )
    return fig
