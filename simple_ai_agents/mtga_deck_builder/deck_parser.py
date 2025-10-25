"""
MTGA Deck Parser
Parses Magic: The Gathering Arena deck lists and extracts deck information
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import Counter


@dataclass
class Card:
    """Represents a single card in the deck"""
    name: str
    quantity: int
    set_code: str = ""
    collector_number: str = ""
    is_sideboard: bool = False


class DeckParser:
    """Parser for MTGA deck lists"""

    def __init__(self):
        self.cards = []
        self.sideboard = []
        self.deck_name = "My Deck"

    def parse(self, decklist: str) -> Tuple[List[Card], List[Card]]:
        """
        Parse an MTGA decklist

        Format examples:
        4 Lightning Bolt (M11) 146
        1 Llanowar Elves

        Or with deck name:
        Deck
        4 Lightning Bolt

        Sideboard
        3 Negate
        """
        lines = decklist.strip().split('\n')
        in_sideboard = False
        cards = []
        sideboard = []

        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Check for section headers
            if line.lower() in ['sideboard', 'sb']:
                in_sideboard = True
                continue
            elif line.lower() in ['deck', 'decklist', 'maindeck']:
                in_sideboard = False
                continue
            elif line.lower().startswith('deck name:'):
                self.deck_name = line.split(':', 1)[1].strip()
                continue

            # Parse card line
            card = self._parse_card_line(line, is_sideboard=in_sideboard)
            if card:
                if in_sideboard:
                    sideboard.append(card)
                else:
                    cards.append(card)

        self.cards = cards
        self.sideboard = sideboard
        return cards, sideboard

    def _parse_card_line(self, line: str, is_sideboard: bool = False) -> Card:
        """Parse a single card line"""
        # Pattern 1: "4 Lightning Bolt (M11) 146"
        pattern1 = r'^(\d+)\s+([^(]+?)(?:\s+\(([A-Z0-9]+)\)\s*(\d+[a-z]?))?$'

        # Pattern 2: Simple format "4 Lightning Bolt"
        pattern2 = r'^(\d+)\s+(.+)$'

        match = re.match(pattern1, line)
        if match:
            quantity = int(match.group(1))
            name = match.group(2).strip()
            set_code = match.group(3) or ""
            collector_number = match.group(4) or ""

            return Card(
                name=name,
                quantity=quantity,
                set_code=set_code,
                collector_number=collector_number,
                is_sideboard=is_sideboard
            )

        match = re.match(pattern2, line)
        if match:
            quantity = int(match.group(1))
            name = match.group(2).strip()

            return Card(
                name=name,
                quantity=quantity,
                is_sideboard=is_sideboard
            )

        return None

    def get_deck_stats(self) -> Dict:
        """Calculate deck statistics"""
        total_cards = sum(card.quantity for card in self.cards)
        sideboard_cards = sum(card.quantity for card in self.sideboard)

        # Count unique cards
        unique_cards = len(self.cards)
        unique_sideboard = len(self.sideboard)

        return {
            'total_cards': total_cards,
            'unique_cards': unique_cards,
            'sideboard_cards': sideboard_cards,
            'unique_sideboard': unique_sideboard,
            'is_valid': 60 <= total_cards <= 250,  # Most formats allow 60 minimum
            'sideboard_valid': sideboard_cards <= 15
        }

    def get_card_type_distribution(self) -> Dict[str, int]:
        """
        Estimate card type distribution based on common patterns
        This is a simplified version - in a real app you'd query a card database
        """
        creatures = 0
        instants = 0
        sorceries = 0
        enchantments = 0
        artifacts = 0
        planeswalkers = 0
        lands = 0

        # Simple keyword matching (this is approximate)
        for card in self.cards:
            name_lower = card.name.lower()

            # Common land patterns
            if any(land in name_lower for land in ['plains', 'island', 'swamp', 'mountain', 'forest',
                                                     'wastes', 'land', 'tower', 'sanctum', 'bazaar']):
                lands += card.quantity
            # Common planeswalker patterns
            elif any(pw in name_lower for pw in ['jace', 'liliana', 'chandra', 'gideon', 'nissa',
                                                   'teferi', 'ajani', 'garruk', 'sorin', 'vraska']):
                planeswalkers += card.quantity
            # This is very simplified - you'd want a real card database
            else:
                # Default to creature for now
                creatures += card.quantity

        return {
            'Creatures': creatures,
            'Instants': instants,
            'Sorceries': sorceries,
            'Enchantments': enchantments,
            'Artifacts': artifacts,
            'Planeswalkers': planeswalkers,
            'Lands': lands
        }

    def to_formatted_list(self) -> str:
        """Convert deck back to formatted string"""
        output = []

        if self.deck_name:
            output.append(f"Deck Name: {self.deck_name}\n")

        output.append("Deck")
        for card in self.cards:
            if card.set_code:
                output.append(f"{card.quantity} {card.name} ({card.set_code}) {card.collector_number}")
            else:
                output.append(f"{card.quantity} {card.name}")

        if self.sideboard:
            output.append("\nSideboard")
            for card in self.sideboard:
                if card.set_code:
                    output.append(f"{card.quantity} {card.name} ({card.set_code}) {card.collector_number}")
                else:
                    output.append(f"{card.quantity} {card.name}")

        return '\n'.join(output)
