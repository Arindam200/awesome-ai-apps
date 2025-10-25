"""
Claude-Powered MTGA Deck Analyzer
Uses Claude AI to provide strategic deck building advice
"""

import os
from typing import Dict, List
import anthropic
from deck_parser import DeckParser, Card


class MTGADeckAnalyzer:
    """AI-powered deck analyzer using Claude"""

    def __init__(self, api_key: str = None):
        """Initialize the analyzer with Anthropic API key"""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.parser = DeckParser()

    def analyze_deck(self, decklist: str, format_type: str = "Standard",
                     strategy: str = None, budget: str = None) -> Dict:
        """
        Analyze a deck and provide strategic recommendations

        Args:
            decklist: MTGA format deck list
            format_type: Magic format (Standard, Modern, Historic, etc.)
            strategy: Desired deck strategy (Aggro, Control, Midrange, Combo)
            budget: Budget constraint (Budget, Mid-range, No Limit)

        Returns:
            Dictionary with analysis and recommendations
        """
        # Parse the deck
        cards, sideboard = self.parser.parse(decklist)
        stats = self.parser.get_deck_stats()

        # Build analysis prompt
        prompt = self._build_analysis_prompt(cards, sideboard, stats, format_type, strategy, budget)

        # Get Claude's analysis
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=3000,
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        analysis = response.content[0].text

        return {
            'analysis': analysis,
            'stats': stats,
            'card_count': len(cards),
            'sideboard_count': len(sideboard),
            'format': format_type
        }

    def suggest_improvements(self, decklist: str, goals: str, format_type: str = "Standard") -> str:
        """
        Suggest specific improvements to a deck

        Args:
            decklist: Current deck list
            goals: What the player wants to improve
            format_type: Magic format

        Returns:
            Improvement suggestions
        """
        cards, sideboard = self.parser.parse(decklist)

        prompt = f"""You are an expert Magic: The Gathering deck builder and strategist.

You have a {format_type} deck and the player wants to: {goals}

Current Deck:
{decklist}

Provide specific, actionable suggestions including:
1. Cards to add (with quantities)
2. Cards to remove (with explanations)
3. Mana base adjustments
4. Sideboard improvements
5. Strategic tips for piloting the deck

Be enthusiastic and encouraging! Make deck building fun!
Format your response with clear sections and use emojis where appropriate."""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2500,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    def generate_deck_idea(self, theme: str, format_type: str = "Standard",
                          playstyle: str = "Aggro") -> str:
        """
        Generate a completely new deck idea based on a theme

        Args:
            theme: Deck theme or central card/mechanic
            format_type: Magic format
            playstyle: Deck archetype

        Returns:
            Complete deck list with explanation
        """
        prompt = f"""You are a creative Magic: The Gathering deck builder!

Create a fun and competitive {playstyle} deck for {format_type} format based on this theme: {theme}

Include:
1. A cool deck name
2. Complete 60-card main deck (in MTGA format: quantity, card name)
3. 15-card sideboard
4. Brief strategy guide
5. Key combos and synergies
6. Mulligan tips

Make it exciting! Use emojis and enthusiasm. Remember this is for fun, not just winning!

Format the deck list like this:
Deck
4 Card Name
3 Another Card
...

Sideboard
2 Sideboard Card
..."""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=3500,
            temperature=0.9,  # Higher temp for creativity
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    def analyze_matchup(self, decklist: str, opponent_archetype: str) -> str:
        """
        Analyze matchup against a specific opponent archetype

        Args:
            decklist: Your deck
            opponent_archetype: Opponent's deck type

        Returns:
            Matchup analysis and sideboarding guide
        """
        prompt = f"""You are a Magic: The Gathering pro player analyzing a matchup!

Your deck:
{decklist}

Opponent: {opponent_archetype}

Provide:
1. Matchup overview (favorable/unfavorable and why)
2. Key cards in the matchup
3. Sideboarding guide (what to bring in, what to take out)
4. Play patterns and sequencing tips
5. Common mistakes to avoid

Be specific and practical! This should help the player win more games."""

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    def _build_analysis_prompt(self, cards: List[Card], sideboard: List[Card],
                               stats: Dict, format_type: str, strategy: str, budget: str) -> str:
        """Build the analysis prompt for Claude"""

        card_list = "\n".join([f"{card.quantity} {card.name}" for card in cards])
        sideboard_list = "\n".join([f"{card.quantity} {card.name}" for card in sideboard]) if sideboard else "No sideboard"

        budget_text = f"\nBudget constraint: {budget}" if budget else ""
        strategy_text = f"\nDesired strategy: {strategy}" if strategy else ""

        prompt = f"""You are a legendary Magic: The Gathering deck builder and strategist with decades of experience!
You're known for being encouraging, creative, and helping players have FUN while also being competitive.

Analyze this {format_type} deck:

DECK ({stats['total_cards']} cards):
{card_list}

SIDEBOARD ({stats['sideboard_cards']} cards):
{sideboard_list}
{strategy_text}{budget_text}

Provide a comprehensive analysis covering:

1. 🎯 DECK IDENTITY & STRATEGY
   - What archetype is this? (Aggro/Midrange/Control/Combo)
   - What's the game plan?
   - Win conditions

2. ⚡ STRENGTHS
   - What does this deck do well?
   - Key synergies and combos
   - Powerful plays

3. 🎲 WEAKNESSES
   - What are the vulnerabilities?
   - Bad matchups
   - Potential issues

4. 🔧 MANA BASE ANALYSIS
   - Color distribution
   - Mana curve evaluation
   - Suggested adjustments

5. 💡 IMPROVEMENT SUGGESTIONS
   - Cards to consider adding
   - Cards that might be underperforming
   - Sideboard recommendations

6. 🎮 GAMEPLAY TIPS
   - Mulligan strategy
   - Key decision points
   - How to pilot the deck

Be enthusiastic and use emojis! Make deck building fun while being informative and strategic."""

        return prompt
