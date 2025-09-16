import streamlit as st
import time
import os
from agno.agent import Agent
from agno.models.google import Gemini
from ..agents.problem_analyzer import leetcode_team
from ..agents.sub_optimized_agent import suboptimal_agent, sub_agent
from ..agents.code_verify import code_runner, code_verify_agent
from ..agents.optimal_agent import optimal_code_agent, optimal_agent_enhanced
from ..agents.notes import Notes_team
from ..utils.code_editor import code_editor

class DSAAssistantApp:
    """Main DSA Assistant Application"""
    
    def __init__(self):
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """Initialize session state variables"""
        # DSA Assistant states
        if 'basic_done' not in st.session_state:
            st.session_state.basic_done = False
        if 'sub_optimal_done' not in st.session_state:
            st.session_state.sub_optimal_done = False
        if 'optimal_done' not in st.session_state:
            st.session_state.optimal_done = False
        
        # Notes Mentor states
        if 'notes_input_code' not in st.session_state:
            st.session_state.notes_input_code = ""
        if 'notes_lang' not in st.session_state:
            st.session_state.notes_lang = "python"
        if 'notes_theme' not in st.session_state:
            st.session_state.notes_theme = "default"
        if 'notes_generated' not in st.session_state:
            st.session_state.notes_generated = False
        if 'generated_notes' not in st.session_state:
            st.session_state.generated_notes = ""
    
    def _apply_custom_css(self):
        """Apply custom CSS styling"""
        st.markdown("""
        <style>
            .main-header {
                background: linear-gradient(90deg, #667eea 0%, #764ba2 0%);
                padding: 2.5rem;
                border-radius: 12px;
                color: white;
                text-align: center;
                margin-bottom: 2rem;
                box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
            }
            
            .step-card {
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 0%);
                padding: 2rem;
                border-radius: 12px;
                border-left: 6px solid #4f46e5;
                margin: 1.5rem 0;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                transition: transform 0.3s ease;
            }
            
            .step-card:hover {
                transform: translateY(-5px);
            }
            
            .content-card {
                background: black;
                padding: 1.5rem;
                border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                margin: 1rem 0;
                border: 1px solid #e0e0e0;
            }
            
            .stButton > button {
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 25px;
                padding: 0.5rem 2rem;
                font-weight: bold;
                transition: all 0.3s ease;
            }
            
            .stButton > button:hover {
                transform: scale(1.05);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }
            
            .progress-bar {
                background: #e5e7eb;
                border-radius: 10px;
                height: 10px;
                overflow: hidden;
                margin: 0.5rem 0;
            }
            
            .progress-fill {
                background: linear-gradient(90deg, #4f46e5, #7c3aed);
                height: 100%;
                transition: width 0.5s ease;
            }
            
            .notes-mentor-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem;
                border-radius: 12px;
                color: white;
                text-align: center;
                margin-bottom: 2rem;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }
        </style>
        """, unsafe_allow_html=True)
    
    def run(self):
        """Run the main application"""
        self._apply_custom_css()
        
        # Navigation
        tab1, tab2 = st.tabs(["🚀 DSA Assistant", "📚 Notes Mentor"])
        
        with tab1:
            self._run_dsa_assistant()
        
        with tab2:
            self._run_notes_mentor()
    
    def _run_dsa_assistant(self):
        """Run the DSA Assistant functionality"""
        # Header
        st.markdown("""
        <div class="main-header">
            <h1><img src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCAxMjAgMTIwIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxkZWZzPjxsaW5lYXJHcmFkaWVudCBpZD0ibG9nb0dyYWRpZW50IiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHkyPSIxMDAlIj48c3RvcCBvZmZzZXQ9IjAlIiBzdHlsZT0ic3RvcC1jb2xvcjojNjY3ZWVhO3N0b3Atb3BhY2l0eToxIiAvPjxzdG9wIG9mZnNldD0iMTAwJSIgc3R5bGU9InN0b3AtY29sb3I6Izc2NGJhMjtzdG9wLW9wYWNpdHk6MSIgLz48L2xpbmVhckdyYWRpZW50PjwvZGVmcz48Y2lyY2xlIGN4PSI2MCIgY3k9IjYwIiByPSI1NSIgZmlsbD0idXJsKCNsb2dvR3JhZGllbnQpIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMyIvPjxnIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iI2ZmZmZmZiIgc3Ryb2tlLXdpZHRoPSIyIj48Y2lyY2xlIGN4PSI2MCIgY3k9IjM1IiByPSI2Ii8+PGxpbmUgeDE9IjYwIiB5MT0iNDEiIHgyPSI0NSIgeTI9IjU1Ii8+PGNpcmNsZSBjeD0iNDUiIGN5PSI2MCIgcj0iNSIvPjxsaW5lIHgxPSI2MCIgeTE9IjQxIiB4Mj0iNzUiIHkyPSI1NSIvPjxjaXJjbGUgY3g9Ijc1IiBjeT0iNjAiIHI9IjUiLz48bGluZSB4MT0iNDUiIHkxPSI2NSIgeDI9IjM1IiB5Mj0iNzUiLz48Y2lyY2xlIGN4PSIzNSIgY3k9IjgwIiByPSI0Ii8+PGxpbmUgeDE9IjQ1IiB5MT0iNjUiIHgyPSI1NSIgeTI9Ijc1Ii8+PGNpcmNsZSBjeD0iNTUiIGN5PSI4MCIgcj0iNCIvPjxsaW5lIHgxPSI3NSIgeTE9IjY1IiB4Mj0iNjUiIHkyPSI3NSIvPjxjaXJjbGUgY3g9IjY1IiBjeT0iODAiIHI9IjQiLz48bGluZSB4MT0iNzUiIHkxPSI2NSIgeDI9Ijg1IiB5Mj0iNzUiLz48Y2lyY2xlIGN4PSI4NSIgY3k9IjgwIiByPSI0Ii8+PC9nPjxnIGZpbGw9Im5vbmUiIHN0cm9rZT0iI2ZmZmZmZiIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiPjxwYXRoIGQ9Ik0yNSA0NSBMMjAgNTAgTDI1IDU1Ii8+PHBhdGggZD0iTTk1IDQ1IEwxMDAgNTAgTDk1IDU1Ii8+PC9nPjxnIGZpbGw9IiNmZmQ3MDAiIHN0cm9rZT0iI2ZmZmZmZiIgc3Ryb2tlLXdpZHRoPSIxIj48cG9seWdvbiBwb2ludHM9IjYwLDE1IDYyLDIxIDY4LDIxIDYzLDI1IDY1LDMxIDYwLDI3IDU1LDMxIDU3LDI1IDUyLDIxIDU4LDIxIi8+PC9nPjwvc3ZnPg==" style="width: 40px; height: 40px; margin-right: 10px; vertical-align: middle;"> AlgoMentor DSA</h1>
            <p>Your AI-powered companion for mastering Data Structures & Algorithms</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Sidebar
        with st.sidebar:
            progress = sum([
                st.session_state.basic_done,
                st.session_state.sub_optimal_done,
                st.session_state.optimal_done
            ]) / 3 * 100
            
            st.markdown("## 📊 Progress Tracker")
            st.markdown(f"<div class='progress-bar'><div class='progress-fill' style='width: {progress}%'></div></div>", unsafe_allow_html=True)
            st.markdown(f"**Progress**: {int(progress)}%")
            st.markdown(f"✅ Basic Approach: {'Done' if st.session_state.basic_done else 'Pending'}")
            st.markdown(f"✅ Sub-Optimal: {'Done' if st.session_state.sub_optimal_done else 'Pending'}")
            st.markdown(f"✅ Optimal Solution: {'Done' if st.session_state.optimal_done else 'Pending'}")
            
            st.divider()
            st.markdown("## 💡 Tips")
            st.info("Start with a clear problem statement for best results.")
            st.warning("Each step builds on the previous one.")
        
        # Main content
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 📝 Problem Statement")
            query = st.text_area(
                "Enter your DSA problem here:",
                height=150,
                placeholder="Paste your LeetCode problem or describe the algorithm challenge..."
            )
        
        with col2:
            st.markdown("### 🎯 Quick Actions")
            if st.button("🧹 Clear All", use_container_width=True):
                st.session_state.basic_done = False
                st.session_state.sub_optimal_done = False
                st.session_state.optimal_done = False
                st.rerun()
        
        if query:
            self._handle_dsa_workflow(query)
        else:
            self._render_welcome_section()
    
    def _handle_dsa_workflow(self, query: str):
        """Handle the DSA problem-solving workflow"""
        # Basic Approach Section
        st.markdown("""
        <div class="step-card">
            <h2>🎯 Step 1: Basic Approach</h2>
            <p>Let's start with the fundamental brute-force solution</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔓 Unlock Basic Approach", type="primary", use_container_width=True):
            with st.spinner("Analyzing problem and generating basic approach..."):
                basic_approach = leetcode_team.run(query).content
                st.session_state.basic_approach = basic_approach
                st.session_state.basic_done = True
        
        if st.session_state.basic_done:
            self._render_basic_results()
            self._handle_sub_optimal_workflow()
    
    def _render_basic_results(self):
        """Render basic approach results"""
        basic_approach = st.session_state.basic_approach
        
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📋 Problem Analysis")
            st.info(basic_approach.problem_statement)
            st.markdown("#### 🧠 Approach")
            st.write(basic_approach.basic_approach)
        
        with col2:
            st.markdown("#### ⚡ Complexity")
            st.metric("Time complexity", basic_approach.basic_time_complexity)
            st.metric("Space complexity", basic_approach.basic_space_complexity)
        
        st.markdown("#### 🔢 Algorithm Steps")
        st.code(basic_approach.basic_algorithm, language="text")
        st.markdown("#### 💻 Brute Force Code")
        st.code(basic_approach.basic_code, language="python")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def _handle_sub_optimal_workflow(self):
        """Handle sub-optimal workflow"""
        st.markdown("""
        <div class="step-card">
            <h2>⚡ Step 2: Sub-Optimal Solution</h2>
            <p>Now let's optimize our approach for better performance</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔓 Unlock Sub-Optimal", type="primary", use_container_width=True):
            with st.spinner("Optimizing approach..."):
                basic_approach = st.session_state.basic_approach
                sub_optimal_app = suboptimal_agent.run(basic_approach).content
                
                query_data = {
                    "role": "user",
                    "content": f"sub_optimal_algorithm:{sub_optimal_app.suboptimal_approach},sub_optimal_approach:{sub_optimal_app.suboptimal_approach},problem_statement:{sub_optimal_app.problem_statement},basic_approach:{sub_optimal_app.basic_code}"
                }
                sub_optimal_codes = sub_agent.run(query_data).content
                
                # Test and verify code
                test_query = f"Code:\n{sub_optimal_codes.sub_optimal_code}\n\nTest Cases:\n{basic_approach.examples}"
                test_results = code_runner.run(test_query)
                format_query = f"Code: {sub_optimal_codes.sub_optimal_code}\nTest Results: {test_results.content}\nTest Cases: {basic_approach.examples}"
                sub_optimal_code_verified = code_verify_agent.run(format_query).content
                
                st.session_state.sub_optimal_verified = sub_optimal_code_verified
                st.session_state.sub_optimal_app = sub_optimal_app
                st.session_state.sub_optimal_done = True
        
        if st.session_state.sub_optimal_done:
            self._render_sub_optimal_results()
            self._handle_optimal_workflow()
    
    def _render_sub_optimal_results(self):
        """Render sub-optimal results"""
        sub_optimal_verified = st.session_state.sub_optimal_verified
        sub_optimal_app = st.session_state.sub_optimal_app
        
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🎯 Optimized Approach")
            st.success(sub_optimal_app.suboptimal_approach)
        
        with col2:
            st.markdown("#### ⚡ Improved Complexity")
            st.metric("Time complexity", sub_optimal_verified.time_complexity)
            st.metric("Space complexity", sub_optimal_verified.space_complexity)
        
        st.markdown("#### 🔢 Sub-Optimal Algorithm")
        st.code(sub_optimal_app.suboptimal_algorithm, language="text")
        st.markdown("#### 💻 Sub-Optimal Code")
        st.code(sub_optimal_verified.final_debuged_suboptimized_code, language="python")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def _handle_optimal_workflow(self):
        """Handle optimal workflow"""
        st.markdown("""
        <div class="step-card">
            <h2>🏆 Step 3: Optimal Solution</h2>
            <p>Finally, let's achieve the most efficient solution possible</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔓 Unlock Optimal Solution", type="primary", use_container_width=True):
            with st.spinner("Finding the most optimal solution..."):
                optimal_approaches = optimal_agent_enhanced.run(st.session_state.sub_optimal_verified).content
                optimal_ap_code = optimal_code_agent.run(optimal_approaches).content
                
                # Test optimal code
                basic_approach = st.session_state.basic_approach
                test_query = f"Code:\n{optimal_ap_code.optimal_code}\n\nTest Cases:\n{basic_approach.examples}"
                test_results = code_runner.run(test_query)
                format_query = f"Code: {optimal_ap_code.optimal_code}\nTest Results: {test_results.content}\nTest Cases: {basic_approach.examples}"
                optimal_code_verified = code_verify_agent.run(format_query).content
                
                st.session_state.optimal_verified = optimal_code_verified
                st.session_state.optimal_approaches = optimal_approaches
                st.session_state.optimal_done = True
        
        if st.session_state.optimal_done:
            self._render_optimal_results()
    
    def _render_optimal_results(self):
        """Render optimal results"""
        optimal_verified = st.session_state.optimal_verified
        optimal_approaches = st.session_state.optimal_approaches
        
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🏆 Optimal Approach")
            st.success(optimal_approaches.optimal_approach)
        
        with col2:
            st.markdown("#### ⚡ Best Complexity")
            st.metric("Time", optimal_verified.time_complexity)
            st.metric("Space", optimal_verified.space_complexity)
        
        st.markdown("#### 🔢 Optimal Algorithm")
        st.code(optimal_approaches.optimal_algorithm, language="text")
        st.markdown("#### 💻 Optimal Code")
        st.code(optimal_verified.final_debuged_suboptimized_code, language="python")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # st.balloons()
        st.success("🎉 Congratulations! You've mastered this problem with all optimization levels!")
    
    def _render_welcome_section(self):
        """Render welcome section"""
        st.markdown("### 👋 Welcome to DSA Assistant!")
        st.markdown("Enter a problem statement above to get started with your algorithmic journey.")
        
        st.markdown("#### 📚 Try these example problems:")
        examples = [
            "Two Sum: Given an array of integers and a target sum, return indices of two numbers that add up to target.",
            "Binary Search: Search for a target value in a sorted array.",
            "Fibonacci: Calculate the nth Fibonacci number.",
            "House Robber: Given an integer array nums representing the amount of money of each house, return the maximum amount of money you can rob tonight without alerting the police."
        ]
        
        for i, example in enumerate(examples, 1):
            if st.button(f"Example {i}: {example[:70]}...", key=f"ex_{i}", use_container_width=True):
                st.session_state.example_query = example
                st.rerun()
    
    def _run_notes_mentor(self):
        """Run the Notes Mentor functionality"""
        # Header
        st.markdown("""
        <div class="notes-mentor-header">
            <h1><img src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCAxMjAgMTIwIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxkZWZzPjxsaW5lYXJHcmFkaWVudCBpZD0ibG9nb0dyYWRpZW50IiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHkyPSIxMDAlIj48c3RvcCBvZmZzZXQ9IjAlIiBzdHlsZT0ic3RvcC1jb2xvcjojNjY3ZWVhO3N0b3Atb3BhY2l0eToxIiAvPjxzdG9wIG9mZnNldD0iMTAwJSIgc3R5bGU9InN0b3AtY29sb3I6Izc2NGJhMjtzdG9wLW9wYWNpdHk6MSIgLz48L2xpbmVhckdyYWRpZW50PjwvZGVmcz48Y2lyY2xlIGN4PSI2MCIgY3k9IjYwIiByPSI1NSIgZmlsbD0idXJsKCNsb2dvR3JhZGllbnQpIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMyIvPjxnIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iI2ZmZmZmZiIgc3Ryb2tlLXdpZHRoPSIyIj48Y2lyY2xlIGN4PSI2MCIgY3k9IjM1IiByPSI2Ii8+PGxpbmUgeDE9IjYwIiB5MT0iNDEiIHgyPSI0NSIgeTI9IjU1Ii8+PGNpcmNsZSBjeD0iNDUiIGN5PSI2MCIgcj0iNSIvPjxsaW5lIHgxPSI2MCIgeTE9IjQxIiB4Mj0iNzUiIHkyPSI1NSIvPjxjaXJjbGUgY3g9Ijc1IiBjeT0iNjAiIHI9IjUiLz48bGluZSB4MT0iNDUiIHkxPSI2NSIgeDI9IjM1IiB5Mj0iNzUiLz48Y2lyY2xlIGN4PSIzNSIgY3k9IjgwIiByPSI0Ii8+PGxpbmUgeDE9IjQ1IiB5MT0iNjUiIHgyPSI1NSIgeTI9Ijc1Ii8+PGNpcmNsZSBjeD0iNTUiIGN5PSI4MCIgcj0iNCIvPjxsaW5lIHgxPSI3NSIgeTE9IjY1IiB4Mj0iNjUiIHkyPSI3NSIvPjxjaXJjbGUgY3g9IjY1IiBjeT0iODAiIHI9IjQiLz48bGluZSB4MT0iNzUiIHkxPSI2NSIgeDI9Ijg1IiB5Mj0iNzUiLz48Y2lyY2xlIGN4PSI4NSIgY3k9IjgwIiByPSI0Ii8+PC9nPjxnIGZpbGw9Im5vbmUiIHN0cm9rZT0iI2ZmZmZmZiIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiPjxwYXRoIGQ9Ik0yNSA0NSBMMjAgNTAgTDI1IDU1Ii8+PHBhdGggZD0iTTk1IDQ1IEwxMDAgNTAgTDk1IDU1Ii8+PC9nPjxnIGZpbGw9IiNmZmQ3MDAiIHN0cm9rZT0iI2ZmZmZmZiIgc3Ryb2tlLXdpZHRoPSIxIj48cG9seWdvbiBwb2ludHM9IjYwLDE1IDYyLDIxIDY4LDIxIDYzLDI1IDY1LDMxIDYwLDI3IDU1LDMxIDU3LDI1IDUyLDIxIDU4LDIxIi8+PC9nPjwvc3ZnPg==" style="width: 40px; height: 40px; margin-right: 10px; vertical-align: middle;"> AlgoMentor Notes</h1>
            <p>Transform your code into comprehensive study notes!</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Sidebar for settings
        with st.sidebar:
            st.header("⚙️ Settings")
            
            # Language selection
            lang_options = ["python", "c_cpp", "java", "javascript", "c"]
            selected_lang = st.selectbox("Programming Language:", lang_options, 
                                       index=lang_options.index(st.session_state.notes_lang) if st.session_state.notes_lang in lang_options else 0,
                                       key="notes_lang_select")
            st.session_state.notes_lang = selected_lang
            
            # Theme selection
            theme_options = ["default", "dark", "light"]
            selected_theme = st.selectbox("Editor Theme:", theme_options, 
                                        index=theme_options.index(st.session_state.notes_theme) if st.session_state.notes_theme in theme_options else 0,
                                        key="notes_theme_select")
            st.session_state.notes_theme = selected_theme
            
            st.markdown("---")
            st.markdown("💡 **Tips:**\n- Paste your code and press Ctrl+Enter\n- Use clear variable names for better analysis\n- Include comments for complex logic")
        
        # Main content area
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### 📝 Code Input")
            response_dict = code_editor(
                st.session_state.notes_input_code, 
                lang=selected_lang, 
                key="code_input", 
                theme=selected_theme,
                focus=True
            )
            input_code = response_dict["text"]
            st.session_state.notes_input_code = input_code
            
            if input_code:
                st.markdown(f'<div style="color: gray; font-size: 0.8em;">Characters: {len(input_code)}</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown("### 🔍 Quick Preview")
            if input_code.strip():
                st.code(input_code[:200] + "..." if len(input_code) > 200 else input_code, language=selected_lang)
            else:
                st.info("Code preview will appear here...")
        
        # Action buttons
        col_btn1, col_btn2 = st.columns([1, 1])
        
        with col_btn1:
            generate_btn = st.button("🚀 Generate Notes", type="primary")
        
        with col_btn2:
            clear_btn = st.button("🗑️ Clear")
        
        if clear_btn:
            st.session_state.notes_input_code = ""
            st.session_state.notes_generated = False
            st.session_state.generated_notes = ""
            st.rerun()
        
        if generate_btn:
            if not input_code.strip():
                st.error("⚠️ Please enter some code before submitting.")
            else:
                self._generate_notes(input_code)
        
        # Display generated notes if available
        if st.session_state.notes_generated and st.session_state.generated_notes:
            st.markdown("---")
            st.markdown("### 📖 Generated Notes")
            st.markdown(st.session_state.generated_notes)
            
            # Download section
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    label="📥 Download Markdown",
                    data=st.session_state.generated_notes,
                    file_name=f"dsa_notes_{int(time.time())}.md",
                    mime="text/markdown"
                )
            with col_dl2:
                if st.button("🗑️ Clear Notes"):
                    st.session_state.notes_generated = False
                    st.session_state.generated_notes = ""
                    st.rerun()
    
    def _generate_notes(self, input_code: str):
        """Generate notes from input code"""
        try:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("🔄 Analyzing code structure...")
            progress_bar.progress(25)
            time.sleep(1)
            
            status_text.text("🧠 Generating comprehensive notes...")
            progress_bar.progress(50)
            
            resp = Notes_team.run(input_code, markdown=True).content
            progress_bar.progress(75)
            
            # api_key = os.getenv('GOOGLE_API_KEY')
            api_key = st.secrets['GOOGLE_API_KEY']
            if not api_key:
                st.error("🔑 Google API key not found. Please check your .env file.")
                return
            
            status_text.text("✨ Finalizing notes...")
            agent = Agent(markdown=True, model=Gemini(id="gemini-2.0-flash", api_key=api_key))
            final_resp = agent.run(resp)
            
            progress_bar.progress(100)
            status_text.text("✅ Notes generated successfully!")
            
            # Store generated notes
            st.session_state.generated_notes = final_resp.content
            st.session_state.notes_generated = True
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            st.info("💡 Try refreshing the page or checking your internet connection.")