"""
Example script demonstrating MTGA Deck Builder usage
Run this to see the analyzer in action without the UI!
"""

import os
from dotenv import load_dotenv
from deck_analyzer import MTGADeckAnalyzer

# Load environment variables
load_dotenv()

# Example deck list
EXAMPLE_DECK = """
Deck
4 Llanowar Elves (M19) 314
4 Pelt Collector (GRN) 141
4 Growth-Chamber Guardian (RNA) 128
4 Steel Leaf Champion (M19) 305
4 Thorn Lieutenant (M19) 367
3 Nullhide Ferox (GRN) 138
2 Questing Beast (ELD) 171
3 Ghalta, Primal Hunger (RIX) 130
2 The Great Henge (ELD) 161
4 Stomping Ground (RNA) 259
20 Forest (ANA) 60
4 Castle Garenbrig (ELD) 240
2 Shifting Ceratops (M20) 194

Sideboard
3 Veil of Summer (M20) 198
2 Shifting Ceratops (M20) 194
3 Kraul Harpooner (GRN) 136
2 Thrashing Brontodon (RIX) 148
3 Nissa, Who Shakes the World (WAR) 169
2 Return to Nature (ELD) 173
"""


def main():
    print("🎴 MTGA Deck Builder - Example Script")
    print("=" * 60)

    # Initialize analyzer
    try:
        analyzer = MTGADeckAnalyzer()
        print("✅ Analyzer initialized successfully!")
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("💡 Make sure to set ANTHROPIC_API_KEY in your .env file")
        return

    # Example 1: Analyze a deck
    print("\n📊 Example 1: Analyzing a Mono-Green Aggro deck...")
    print("-" * 60)

    try:
        result = analyzer.analyze_deck(
            EXAMPLE_DECK,
            format_type="Standard",
            strategy="Aggro",
            budget="Competitive"
        )

        print(f"\n🎯 Deck Analysis:")
        print(f"Total Cards: {result['stats']['total_cards']}")
        print(f"Sideboard Cards: {result['stats']['sideboard_cards']}")
        print(f"\n{result['analysis']}")

    except Exception as e:
        print(f"❌ Error during analysis: {e}")

    # Example 2: Generate a deck idea
    print("\n" + "=" * 60)
    print("✨ Example 2: Generating a Dragon Tribal deck...")
    print("-" * 60)

    try:
        deck = analyzer.generate_deck_idea(
            theme="Dragon tribal with ramp",
            format_type="Standard",
            playstyle="Midrange"
        )

        print(f"\n🐉 Generated Deck:\n")
        print(deck)

    except Exception as e:
        print(f"❌ Error generating deck: {e}")

    # Example 3: Get improvement suggestions
    print("\n" + "=" * 60)
    print("🔧 Example 3: Improving the deck...")
    print("-" * 60)

    try:
        improvements = analyzer.suggest_improvements(
            EXAMPLE_DECK,
            goals="Better against control decks and improve card draw",
            format_type="Standard"
        )

        print(f"\n💡 Improvement Suggestions:\n")
        print(improvements)

    except Exception as e:
        print(f"❌ Error getting suggestions: {e}")

    # Example 4: Matchup analysis
    print("\n" + "=" * 60)
    print("⚔️ Example 4: Matchup analysis vs Mono Red Aggro...")
    print("-" * 60)

    try:
        matchup = analyzer.analyze_matchup(
            EXAMPLE_DECK,
            opponent_archetype="Mono Red Aggro"
        )

        print(f"\n⚔️ Matchup Analysis:\n")
        print(matchup)

    except Exception as e:
        print(f"❌ Error analyzing matchup: {e}")

    print("\n" + "=" * 60)
    print("✅ Examples complete! Ready to build your own decks!")
    print("🚀 Run 'streamlit run app.py' for the full interactive experience!")
    print("=" * 60)


if __name__ == "__main__":
    main()
