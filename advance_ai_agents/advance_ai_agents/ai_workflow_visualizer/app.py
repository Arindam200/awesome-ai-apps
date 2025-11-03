from dotenv import load_dotenv
load_dotenv()
import streamlit as st
from parser import parse_logs
from graph_builder import build_graph
from nebius_client import summarize_workflow
import time
from datetime import datetime

st.set_page_config(page_title="AI Workflow Visualizer", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
    
    .main {
        background: linear-gradient(135deg, #0a0e27 0%, #16213e 50%, #0a0e27 100%);
        background-size: 400% 400%;
        animation: bgShift 15s ease infinite;
    }
    
    @keyframes bgShift {
        0%, 100% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
    }
    
    h1 {
        font-family: 'Orbitron', sans-serif !important;
        color: #00ff88;
        text-align: center;
        font-size: 3.5rem !important;
        text-shadow: 0 0 20px #00ff88, 0 0 40px #00ff88, 0 0 60px #00ff88;
        animation: glow 2s ease-in-out infinite alternate;
        margin-bottom: 0.5rem;
        font-weight: 900 !important;
    }
    
    @keyframes glow {
        from { text-shadow: 0 0 20px #00ff88, 0 0 40px #00ff88; }
        to { text-shadow: 0 0 30px #00ff88, 0 0 60px #00ff88, 0 0 80px #00ff88; }
    }
    
    .status-badge {
        display: inline-block;
        background: linear-gradient(90deg, #ff006e, #8338ec);
        color: white;
        padding: 8px 20px;
        border-radius: 20px;
        font-weight: bold;
        animation: pulse 1.5s ease-in-out infinite;
        margin: 10px;
        box-shadow: 0 0 20px rgba(255, 0, 110, 0.6);
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); box-shadow: 0 0 20px rgba(255, 0, 110, 0.5); }
        50% { transform: scale(1.05); box-shadow: 0 0 40px rgba(255, 0, 110, 0.8); }
    }
    
    .metric-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        color: white;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
        transition: transform 0.3s;
    }
    
    .metric-box:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 48px rgba(102, 126, 234, 0.6);
    }
    
    .metric-box h2 {
        margin: 10px 0 5px 0;
        font-size: 2rem;
        font-weight: bold;
    }
    
    .metric-box p {
        margin: 0;
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    .metric-box h3 {
        font-size: 2rem;
        margin: 5px 0;
    }
    
    .perf-metric-box {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 18px;
        border-radius: 15px;
        text-align: center;
        color: white;
        box-shadow: 0 8px 32px rgba(240, 147, 251, 0.4);
        margin-bottom: 10px;
        transition: transform 0.3s;
    }
    
    .perf-metric-box:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 40px rgba(240, 147, 251, 0.6);
    }
    
    .perf-metric-box h4 {
        margin: 0 0 8px 0;
        font-size: 0.85rem;
        opacity: 0.9;
        font-weight: 600;
    }
    
    .perf-metric-box h3 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: bold;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }
    
    .live-indicator {
        width: 15px;
        height: 15px;
        background: #00ff88;
        border-radius: 50%;
        display: inline-block;
        animation: blink 1s infinite;
        margin-right: 8px;
        box-shadow: 0 0 10px #00ff88;
    }
    
    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }
    
    .section-header {
        font-family: 'Orbitron', sans-serif;
        color: #00ff88;
        font-size: 1.5rem;
        font-weight: 700;
        margin: 2rem 0 1rem 0;
        text-shadow: 0 0 10px rgba(0, 255, 136, 0.5);
    }
    
    .stSlider > div > div > div {
        background: linear-gradient(90deg, #ff006e, #8338ec, #3a86ff) !important;
    }
    
    .analysis-box {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #00ff88;
        box-shadow: 0 8px 32px rgba(0, 255, 136, 0.3);
    }
    
    .analysis-box p {
        color: white;
        font-size: 1.1rem;
        line-height: 1.8;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🧠 AI WORKFLOW VISUALIZER</h1>", unsafe_allow_html=True)
st.markdown("<center><span class='live-indicator'></span><span class='status-badge'>🔴 LIVE</span><span class='status-badge'>⚡ REAL-TIME</span><span class='status-badge'>🤖 AI-POWERED</span></center>", unsafe_allow_html=True)

st.markdown("---")


if 'total_workflows' not in st.session_state:
    st.session_state.total_workflows = 0
if 'total_tokens' not in st.session_state:
    st.session_state.total_tokens = 0
if 'avg_latency' not in st.session_state:
    st.session_state.avg_latency = 0
if 'latency_history' not in st.session_state:
    st.session_state.latency_history = []

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown("<div class='metric-box'><h3>🎯</h3><p>Status</p><h2>ACTIVE</h2></div>", unsafe_allow_html=True)
with col2:
    agents_count = st.empty()
with col3:
    edges_count = st.empty()
with col4:
    st.markdown("<div class='metric-box'><h3>🤖</h3><p>AI Model</p><h2>Llama 3.1</h2></div>", unsafe_allow_html=True)
with col5:
    timestamp = st.empty()

st.markdown("---")


st.markdown("<div class='section-header'>📊 PERFORMANCE METRICS</div>", unsafe_allow_html=True)
perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)

with perf_col1:
    latency_display = st.empty()
with perf_col2:
    tokens_display = st.empty()
with perf_col3:
    workflows_display = st.empty()
with perf_col4:
    throughput_display = st.empty()

st.markdown("---")
refresh_rate = st.slider("⏱️ Refresh Rate (seconds)", 2, 15, 5)
st.markdown("---")
graph_placeholder = st.empty()
summary_placeholder = st.empty()
enable_realtime = st.checkbox("🔥 Enable Real-Time Visualization", value=True)

def update_performance_metrics(latency, tokens):
    """Update performance metrics in session state."""
    st.session_state.total_workflows += 1
    st.session_state.total_tokens += tokens
    st.session_state.latency_history.append(latency)
    

    if len(st.session_state.latency_history) > 10:
        st.session_state.latency_history.pop(0)
    
    st.session_state.avg_latency = sum(st.session_state.latency_history) / len(st.session_state.latency_history)

def display_performance_metrics():
    """Display current performance metrics."""
    with latency_display:
        st.markdown(f"<div class='perf-metric-box'><h4>⚡ Avg Latency</h4><h3>{st.session_state.avg_latency:.2f}s</h3></div>", unsafe_allow_html=True)
    
    with tokens_display:
        st.markdown(f"<div class='perf-metric-box'><h4>🔤 Total Tokens</h4><h3>{st.session_state.total_tokens:,}</h3></div>", unsafe_allow_html=True)
    
    with workflows_display:
        st.markdown(f"<div class='perf-metric-box'><h4>📈 Workflows</h4><h3>{st.session_state.total_workflows}</h3></div>", unsafe_allow_html=True)
    
    throughput = (1 / st.session_state.avg_latency) if st.session_state.avg_latency > 0 else 0
    with throughput_display:
        st.markdown(f"<div class='perf-metric-box'><h4>🚀 Throughput</h4><h3>{throughput:.2f}/s</h3></div>", unsafe_allow_html=True)

if enable_realtime:
    st.success(f"🚀 **REAL-TIME MODE ACTIVATED** - Generating new workflows every {refresh_rate} seconds")
    
    iteration = 0
    while True:
        iteration += 1
        try:
            parse_start = time.time()
            nodes, edges, log_text = parse_logs()
            parse_time = time.time() - parse_start
            
            with agents_count:
                st.markdown(f"<div class='metric-box'><h3>⚡</h3><p>Agents</p><h2>{len(nodes)}</h2></div>", unsafe_allow_html=True)
            with edges_count:
                st.markdown(f"<div class='metric-box'><h3>🔗</h3><p>Connections</p><h2>{len(edges)}</h2></div>", unsafe_allow_html=True)
            with timestamp:
                current_time = datetime.now().strftime("%H:%M:%S")
                st.markdown(f"<div class='metric-box'><h3>⏰</h3><p>Updated</p><h2>{current_time}</h2></div>", unsafe_allow_html=True)
            
            with graph_placeholder.container():
                fig = build_graph(nodes, edges)
                st.plotly_chart(fig, use_container_width=True, key=f"graph_{iteration}")
            
            with summary_placeholder.container():
                st.markdown("<div class='section-header'>🧠 AI ANALYSIS (LIVE)</div>", unsafe_allow_html=True)
                with st.spinner("🤖 Nebius AI is analyzing..."):
                    ai_start = time.time()
                    result = summarize_workflow(log_text)
                    

                    if isinstance(result, tuple):
                        summary, token_count = result
                    else:
                        summary = result
                        token_count = 0  
                    
                    ai_latency = time.time() - ai_start
                    total_latency = parse_time + ai_latency
                    update_performance_metrics(total_latency, token_count)
                    display_performance_metrics()
                
                st.markdown(f"""
                <div class='analysis-box'>
                    <p>{summary}</p>
                </div>
                """, unsafe_allow_html=True)
            
            st.info(f"🔄 Workflow #{iteration} - Next generation in {refresh_rate} seconds... (Parse: {parse_time:.3f}s | AI: {ai_latency:.3f}s)")
            
        except Exception as e:
            st.error(f"❌ Error: {e}")
            import traceback
            st.code(traceback.format_exc())
        
        time.sleep(refresh_rate)
else:
    if st.button("🎬 Generate Workflow", type="primary"):
        try:
            parse_start = time.time()
            nodes, edges, log_text = parse_logs()
            parse_time = time.time() - parse_start
            
            with agents_count:
                st.markdown(f"<div class='metric-box'><h3>⚡</h3><p>Agents</p><h2>{len(nodes)}</h2></div>", unsafe_allow_html=True)
            with edges_count:
                st.markdown(f"<div class='metric-box'><h3>🔗</h3><p>Connections</p><h2>{len(edges)}</h2></div>", unsafe_allow_html=True)
            with timestamp:
                current_time = datetime.now().strftime("%H:%M:%S")
                st.markdown(f"<div class='metric-box'><h3>⏰</h3><p>Updated</p><h2>{current_time}</h2></div>", unsafe_allow_html=True)
            
            fig = build_graph(nodes, edges)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("<div class='section-header'>🧠 AI ANALYSIS</div>", unsafe_allow_html=True)
            with st.spinner("🤖 Nebius AI is analyzing..."):
                ai_start = time.time()
                result = summarize_workflow(log_text)

                if isinstance(result, tuple):
                    summary, token_count = result
                else:
                    summary = result
                    token_count = 0  
                
                ai_latency = time.time() - ai_start
                
                
                total_latency = parse_time + ai_latency
                update_performance_metrics(total_latency, token_count)
                display_performance_metrics()
            
            st.markdown(f"""
            <div class='analysis-box'>
                <p>{summary}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.success(f"✅ Workflow generated successfully! (Parse: {parse_time:.3f}s | AI: {ai_latency:.3f}s)")
        except Exception as e:
            st.error(f"❌ Error: {e}")
            import traceback
            st.code(traceback.format_exc())