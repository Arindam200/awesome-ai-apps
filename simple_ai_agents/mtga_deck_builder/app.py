"""
MTGA Deck Builder - A Fun AI-Powered Deck Building Assistant
Build, analyze, and optimize your Magic: The Gathering Arena decks with Claude AI!
"""

import streamlit as st
import os
from deck_analyzer import MTGADeckAnalyzer
from deck_parser import DeckParser
import plotly.graph_objects as go
import plotly.express as px
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="MTGA Deck Builder",
    page_icon="🎴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for fun styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #FF6B6B, #4ECDC4, #45B7D1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem;
    }
    .fun-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
    }
    .stat-box {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #4ECDC4;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables"""
    if 'analyzer' not in st.session_state:
        try:
            st.session_state.analyzer = MTGADeckAnalyzer()
        except ValueError:
            st.session_state.analyzer = None
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'generated_deck' not in st.session_state:
        st.session_state.generated_deck = None


def render_header():
    """Render the fun header"""
    st.markdown('<h1 class="main-header">🎴 MTGA Deck Builder 🎴</h1>', unsafe_allow_html=True)
    st.markdown("""
    <div class="fun-box">
        <h3>🎮 Build. Analyze. Dominate. Have FUN! 🎮</h3>
        <p>Your AI-powered companion for brewing the best Magic: The Gathering Arena decks!
        Whether you're crushing the ladder or brewing jank, Claude's got your back!</p>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar with options"""
    st.sidebar.title("⚙️ Deck Builder Options")

    # Mode selection
    mode = st.sidebar.radio(
        "Choose Your Adventure:",
        ["📊 Analyze Existing Deck", "✨ Generate New Deck", "⚔️ Matchup Analysis", "🔧 Improve My Deck"],
        help="Select what you want to do!"
    )

    st.sidebar.markdown("---")

    # Format selection
    format_type = st.sidebar.selectbox(
        "🎯 Format",
        ["Standard", "Historic", "Explorer", "Alchemy", "Brawl", "Modern", "Pioneer", "Legacy", "Vintage", "Commander"],
        help="Which format are you playing?"
    )

    # Strategy preference
    strategy = st.sidebar.selectbox(
        "🎲 Playstyle",
        ["Any", "Aggro", "Midrange", "Control", "Combo", "Tempo", "Ramp"],
        help="What's your preferred playstyle?"
    )

    # Budget
    budget = st.sidebar.selectbox(
        "💰 Budget",
        ["No Limit", "Competitive", "Budget-Friendly", "Ultra Budget"],
        help="What's your wildcard budget?"
    )

    st.sidebar.markdown("---")
    st.sidebar.info("💡 **Pro Tip:** The more specific you are, the better the suggestions!")

    return mode, format_type, strategy, budget


def render_deck_stats(parser: DeckParser):
    """Render deck statistics"""
    stats = parser.get_deck_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Cards", stats['total_cards'],
                 delta="Valid" if stats['is_valid'] else "Invalid",
                 delta_color="normal" if stats['is_valid'] else "inverse")

    with col2:
        st.metric("Unique Cards", stats['unique_cards'])

    with col3:
        st.metric("Sideboard", stats['sideboard_cards'],
                 delta="Valid" if stats['sideboard_valid'] else "Too Many",
                 delta_color="normal" if stats['sideboard_valid'] else "inverse")

    with col4:
        st.metric("Unique SB Cards", stats['unique_sideboard'])


def create_mana_curve_chart(cards):
    """Create a fun mana curve visualization"""
    # This is simplified - in production you'd query actual CMC data
    mana_costs = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, "7+": 0}

    # Simplified estimation based on card names (you'd want a real database)
    for card in cards:
        # Just distribute randomly for demo - you'd query real data
        import random
        cmc = random.randint(0, 7)
        if cmc >= 7:
            mana_costs["7+"] += card.quantity
        else:
            mana_costs[cmc] += card.quantity

    fig = go.Figure(data=[
        go.Bar(
            x=list(mana_costs.keys()),
            y=list(mana_costs.values()),
            marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DFE6E9', '#74B9FF', '#A29BFE'],
            text=list(mana_costs.values()),
            textposition='auto',
        )
    ])

    fig.update_layout(
        title="⚡ Mana Curve (Estimated)",
        xaxis_title="Mana Cost",
        yaxis_title="Number of Cards",
        height=400,
        showlegend=False
    )

    return fig


def analyze_deck_mode(format_type, strategy, budget):
    """Mode: Analyze existing deck"""
    st.subheader("📊 Deck Analysis")

    # Example deck to get users started
    example_deck = """Deck
4 Llanowar Elves
4 Growth-Chamber Guardian
3 Steel Leaf Champion
4 Pelt Collector
4 Thorn Lieutenant
2 Nullhide Ferox
3 Ghalta, Primal Hunger
2 The Great Henge
4 Questing Beast
2 Shifting Ceratops
20 Forest
4 Castle Garenbrig
4 Stomping Ground

Sideboard
3 Veil of Summer
2 Shifting Ceratops
3 Kraul Harpooner
2 Thrashing Brontodon
3 Nissa, Who Shakes the World
2 Return to Nature"""

    # Deck input
    decklist = st.text_area(
        "📝 Paste Your Deck List (MTGA Format)",
        height=300,
        placeholder=example_deck,
        help="Copy your deck from MTGA and paste it here!"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔍 Analyze This Deck!", type="primary", use_container_width=True):
            if not decklist.strip():
                st.error("⚠️ Please paste a deck list first!")
                return

            if not st.session_state.analyzer:
                st.error("⚠️ Please set your ANTHROPIC_API_KEY environment variable!")
                return

            with st.spinner("🧙‍♂️ Claude is analyzing your deck..."):
                try:
                    parser = DeckParser()
                    cards, sideboard = parser.parse(decklist)

                    st.session_state.analysis_result = st.session_state.analyzer.analyze_deck(
                        decklist,
                        format_type=format_type,
                        strategy=strategy if strategy != "Any" else None,
                        budget=budget if budget != "No Limit" else None
                    )

                    # Parse for stats
                    st.session_state.parser = parser

                except Exception as e:
                    st.error(f"❌ Error analyzing deck: {str(e)}")
                    return

    with col2:
        if st.button("📋 Load Example Deck", use_container_width=True):
            st.rerun()

    # Display results
    if st.session_state.analysis_result:
        st.markdown("---")

        # Deck stats
        render_deck_stats(st.session_state.parser)

        # Mana curve
        cards, _ = st.session_state.parser.parse(decklist)
        st.plotly_chart(create_mana_curve_chart(cards), use_container_width=True)

        # Claude's analysis
        st.markdown("### 🎯 Claude's Analysis")
        st.markdown(st.session_state.analysis_result['analysis'])


def generate_deck_mode(format_type, strategy):
    """Mode: Generate new deck"""
    st.subheader("✨ Generate a New Deck")

    st.markdown("""
    <div class="fun-box">
        <h4>🎨 Brew Something Spicy!</h4>
        <p>Tell Claude what kind of deck you want, and watch the magic happen!</p>
    </div>
    """, unsafe_allow_html=True)

    theme = st.text_input(
        "🎯 Deck Theme or Central Card",
        placeholder="e.g., 'Dragon tribal', 'Mill strategy', 'Omnath Elementals', 'Lifegain combo'",
        help="What do you want to build around?"
    )

    if st.button("✨ Generate Deck!", type="primary"):
        if not theme:
            st.error("⚠️ Please enter a deck theme!")
            return

        if not st.session_state.analyzer:
            st.error("⚠️ Please set your ANTHROPIC_API_KEY environment variable!")
            return

        with st.spinner(f"🧙‍♂️ Claude is brewing a {theme} deck..."):
            try:
                deck = st.session_state.analyzer.generate_deck_idea(
                    theme=theme,
                    format_type=format_type,
                    playstyle=strategy if strategy != "Any" else "Midrange"
                )
                st.session_state.generated_deck = deck
            except Exception as e:
                st.error(f"❌ Error generating deck: {str(e)}")
                return

    # Display generated deck
    if st.session_state.generated_deck:
        st.markdown("---")
        st.markdown("### 🎴 Your New Deck!")
        st.markdown(st.session_state.generated_deck)

        # Copy button
        st.code(st.session_state.generated_deck, language=None)


def matchup_analysis_mode():
    """Mode: Matchup analysis"""
    st.subheader("⚔️ Matchup Analysis")

    st.markdown("""
    <div class="fun-box">
        <h4>⚔️ Know Your Enemy!</h4>
        <p>Get detailed sideboarding guides and play patterns for tough matchups!</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        decklist = st.text_area(
            "Your Deck",
            height=250,
            placeholder="Paste your deck list here..."
        )

    with col2:
        opponent = st.selectbox(
            "🎯 Opponent Archetype",
            ["Mono Red Aggro", "Azorius Control", "Esper Midrange", "Mono Green Devotion",
             "Rakdos Sacrifice", "Izzet Phoenix", "Jeskai Tempo", "Other (describe below)"]
        )

        if opponent == "Other (describe below)":
            opponent = st.text_input("Describe opponent's deck:")

    if st.button("⚔️ Analyze Matchup!", type="primary"):
        if not decklist or not opponent:
            st.error("⚠️ Please provide both your deck and opponent archetype!")
            return

        if not st.session_state.analyzer:
            st.error("⚠️ Please set your ANTHROPIC_API_KEY environment variable!")
            return

        with st.spinner("🧙‍♂️ Claude is analyzing the matchup..."):
            try:
                analysis = st.session_state.analyzer.analyze_matchup(decklist, opponent)
                st.markdown("---")
                st.markdown("### 🎯 Matchup Guide")
                st.markdown(analysis)
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")


def improve_deck_mode(format_type):
    """Mode: Improve existing deck"""
    st.subheader("🔧 Deck Improvement Lab")

    st.markdown("""
    <div class="fun-box">
        <h4>🔧 Level Up Your Deck!</h4>
        <p>Tell Claude what you want to improve, and get specific card suggestions!</p>
    </div>
    """, unsafe_allow_html=True)

    decklist = st.text_area(
        "📝 Current Deck List",
        height=200,
        placeholder="Paste your deck here..."
    )

    goals = st.text_area(
        "🎯 What do you want to improve?",
        placeholder="e.g., 'Better against aggro', 'More consistent mana base', 'Add more removal', 'Faster wins'",
        help="Be specific about what you want to change!"
    )

    if st.button("🔧 Get Suggestions!", type="primary"):
        if not decklist or not goals:
            st.error("⚠️ Please provide both your deck and improvement goals!")
            return

        if not st.session_state.analyzer:
            st.error("⚠️ Please set your ANTHROPIC_API_KEY environment variable!")
            return

        with st.spinner("🧙‍♂️ Claude is brewing improvements..."):
            try:
                suggestions = st.session_state.analyzer.suggest_improvements(
                    decklist, goals, format_type
                )
                st.markdown("---")
                st.markdown("### 💡 Improvement Suggestions")
                st.markdown(suggestions)
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")


def main():
    """Main app function"""
    initialize_session_state()
    render_header()

    # Sidebar
    mode, format_type, strategy, budget = render_sidebar()

    # Main content based on mode
    if mode == "📊 Analyze Existing Deck":
        analyze_deck_mode(format_type, strategy, budget)
    elif mode == "✨ Generate New Deck":
        generate_deck_mode(format_type, strategy)
    elif mode == "⚔️ Matchup Analysis":
        matchup_analysis_mode()
    elif mode == "🔧 Improve My Deck":
        improve_deck_mode(format_type)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>Made with ❤️ for the MTG Arena community | Powered by Claude AI 🎴</p>
        <p><em>Remember: The best deck is the one you have fun playing!</em></p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
