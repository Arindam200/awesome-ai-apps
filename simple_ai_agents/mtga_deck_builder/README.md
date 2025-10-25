# 🎴 MTGA Deck Builder - AI-Powered Magic: The Gathering Arena Deck Assistant

**Finally, an AI agent that's ALL about having FUN!**

Build, analyze, and optimize your Magic: The Gathering Arena decks with the power of Claude AI. Whether you're grinding the ladder, brewing spicy jank, or just want to crush your friends at the kitchen table, this deck builder has got your back!

![MTGA Deck Builder](https://img.shields.io/badge/Magic-The%20Gathering-orange?style=for-the-badge)
![Powered by Claude](https://img.shields.io/badge/Powered%20by-Claude%20AI-blue?style=for-the-badge)
![Fun Level](https://img.shields.io/badge/Fun%20Level-MAXIMUM-green?style=for-the-badge)

## ✨ Features

### 🎯 What Makes This Special?

- **📊 Deck Analysis**: Upload your deck and get comprehensive strategic analysis
- **✨ Deck Generation**: Describe what you want, get a complete deck list
- **⚔️ Matchup Analysis**: Detailed sideboarding guides and play patterns
- **🔧 Deck Improvement**: Specific suggestions to level up your brew
- **📈 Visual Stats**: Mana curves, card distribution, and more
- **🎮 Fun Interface**: Colorful, emoji-filled, and actually enjoyable to use!

### 🎲 Supported Features

- **All Major Formats**: Standard, Historic, Explorer, Modern, Pioneer, Legacy, Vintage, Commander, and more!
- **Multiple Playstyles**: Aggro, Midrange, Control, Combo, Tempo, Ramp
- **Budget Options**: From ultra-budget to no-wildcard-limit brews
- **Smart Analysis**: Mana curve, color distribution, synergy detection
- **Sideboard Help**: Matchup-specific sideboarding guides

## 🚀 Quick Start

### Installation

1. **Clone the repository**:
   ```bash
   cd awesome-ai-apps/simple_ai_agents/mtga_deck_builder
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your API key**:
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

4. **Run the app**:
   ```bash
   streamlit run app.py
   ```

5. **Open your browser** and start brewing! 🎉

## 📖 Usage Examples

### Example 1: Analyze Your Deck

Paste your MTGA deck list:

```
Deck
4 Llanowar Elves
4 Steel Leaf Champion
4 Pelt Collector
3 Questing Beast
2 The Great Henge
20 Forest
4 Castle Garenbrig

Sideboard
3 Veil of Summer
2 Shifting Ceratops
```

Click "Analyze This Deck!" and get:
- Strategy assessment
- Strengths and weaknesses
- Mana curve analysis
- Specific improvement suggestions
- Gameplay tips

### Example 2: Generate a New Deck

**Theme**: "Zombie tribal with sacrifice synergies"
**Format**: Standard
**Playstyle**: Midrange

Claude will generate:
- Complete 60-card deck
- 15-card sideboard
- Strategy guide
- Key combos
- Mulligan tips

### Example 3: Matchup Analysis

**Your Deck**: Paste your list
**Opponent**: "Mono Red Aggro"

Get:
- Win percentage estimate
- Key cards in the matchup
- Sideboarding guide (in/out)
- Play sequencing tips
- Common mistakes to avoid

### Example 4: Improve Your Deck

**Current Deck**: Your list
**Goal**: "Better against control decks"

Receive:
- Specific cards to add
- Cards to cut with explanations
- Mana base tweaks
- Alternative options
- Strategic adjustments

## 🎮 Interface Tour

### Main Modes

1. **📊 Analyze Existing Deck**
   - Upload your current deck
   - Get comprehensive analysis
   - See visual statistics

2. **✨ Generate New Deck**
   - Describe your dream deck
   - Get a complete list instantly
   - Ready to copy into MTGA

3. **⚔️ Matchup Analysis**
   - Choose your opponent
   - Get sideboarding guides
   - Learn play patterns

4. **🔧 Improve My Deck**
   - State your goals
   - Get actionable suggestions
   - Level up your brew

### Sidebar Options

- **Format Selection**: Pick your format
- **Playstyle**: Choose your archetype
- **Budget**: Set wildcard constraints
- **Pro Tips**: Context-aware help

## 🎯 Example Decks to Try

### Mono Green Stompy (Standard)

```
Deck
4 Llanowar Elves (M19) 314
4 Pelt Collector (GRN) 141
4 Growth-Chamber Guardian (RNA) 128
4 Steel Leaf Champion (M19) 305
3 Nullhide Ferox (GRN) 138
2 Questing Beast (ELD) 171
3 Ghalta, Primal Hunger (RIX) 130
2 The Great Henge (ELD) 161
20 Forest (ANA) 60
4 Castle Garenbrig (ELD) 240

Sideboard
3 Veil of Summer (M20) 198
2 Shifting Ceratops (M20) 194
3 Kraul Harpooner (GRN) 136
2 Thrashing Brontodon (RIX) 148
3 Return to Nature (ELD) 173
2 Vivien Reid (M19) 208
```

### Izzet Phoenix (Historic)

```
Deck
4 Arclight Phoenix (GRN) 91
4 Sprite Dragon (IKO) 211
4 Lightning Axe (SOI) 170
4 Chart a Course (XLN) 48
4 Opt (XLN) 65
4 Shock (M19) 156
4 Wild Slash (FRF) 118
20 Island (ANA) 62
4 Steam Vents (GRN) 257
4 Spirebluff Canal (KLR) 286

Sideboard
3 Mystical Dispute (ELD) 58
3 Abrade (AKR) 136
2 Negate (M20) 69
```

## 🎨 Customization

### Adding Card Database Integration

Currently uses pattern matching for card types. To add real card data:

```python
# In deck_parser.py, integrate with Scryfall API
import requests

def get_card_info(card_name):
    response = requests.get(f"https://api.scryfall.com/cards/named?exact={card_name}")
    return response.json()
```

### Custom Themes

Edit the CSS in `app.py` to change colors:

```python
st.markdown("""
<style>
    .fun-box {
        background: linear-gradient(135deg, YOUR_COLOR_1, YOUR_COLOR_2);
    }
</style>
""", unsafe_allow_html=True)
```

## 🔧 Advanced Features

### Command-Line Analysis

Use the analyzer without the UI:

```python
from deck_analyzer import MTGADeckAnalyzer

analyzer = MTGADeckAnalyzer(api_key="your_key")

decklist = """
4 Lightning Bolt
20 Mountain
"""

result = analyzer.analyze_deck(decklist, format_type="Modern")
print(result['analysis'])
```

### Batch Analysis

Analyze multiple decks:

```python
decks = [deck1, deck2, deck3]
for deck in decks:
    analysis = analyzer.analyze_deck(deck)
    print(analysis)
```

## 🎯 Tips for Best Results

1. **Be Specific**: The more detail you provide, the better the suggestions
2. **Use MTGA Format**: Copy directly from Arena for best parsing
3. **Include Sideboard**: Get comprehensive matchup advice
4. **Try Different Prompts**: Experiment with different improvement goals
5. **Have Fun**: Don't be afraid to brew spicy jank!

## 🎮 Pro Tips

### For New Players
- Start with "Generate New Deck" mode
- Try mono-colored decks first
- Use budget options to save wildcards
- Focus on one format at a time

### For Experienced Players
- Use matchup analysis for tournament prep
- Get sideboarding guides for your local meta
- Optimize mana bases with improvement mode
- Test brew ideas before crafting cards

### For Brewers
- Use generate mode for inspiration
- Combine multiple themes
- Ask for "spicy" or "unconventional" builds
- Request budget alternatives for expensive cards

## 🐛 Troubleshooting

### Common Issues

**"ANTHROPIC_API_KEY is required"**
- Make sure you've created a `.env` file
- Add your API key: `ANTHROPIC_API_KEY=sk-ant-...`

**"Deck parsing failed"**
- Check your deck list format
- Use MTGA export format
- Ensure quantity is first: `4 Lightning Bolt`

**"Analysis too slow"**
- Large deck lists take longer
- Check your internet connection
- API calls can take 5-10 seconds

**Mana curve seems wrong**
- Currently uses estimation
- For accurate curves, integrate Scryfall API
- Or manually verify important curves

## 🚀 Future Enhancements

Ideas for expansion:

- [ ] Scryfall API integration for accurate card data
- [ ] Meta analysis (what's winning tournaments)
- [ ] Price tracking for paper/MTGO
- [ ] Deck comparison tool
- [ ] Historical version tracking
- [ ] Export to other formats (TappedOut, etc.)
- [ ] Multiple deck management
- [ ] Tournament sideboard guides
- [ ] Goldfish simulator integration

## 🤝 Contributing

Want to make this even more fun? Contributions welcome!

- Add card database integration
- Improve parsing logic
- Add new visualization types
- Create preset deck templates
- Improve UI/UX

## 📝 License

Part of the awesome-ai-apps repository under MIT License.

## 🎉 Acknowledgments

- **Anthropic** for Claude AI
- **Wizards of the Coast** for Magic: The Gathering
- **MTG Arena** for the awesome digital platform
- **The MTG Community** for endless deck brewing inspiration

## 💡 Fun Fact

Did you know? The first Magic: The Gathering card game was released in 1993, and now we're using AI to build decks. Richard Garfield would be proud! 🎴

---

## 🎮 Ready to Build?

```bash
streamlit run app.py
```

**Remember**: The best deck is the one YOU enjoy playing! Now go brew something spicy! 🌶️

---

<div align="center">

Made with ❤️ and ☕ for the MTG Arena community

**Happy Brewing! May your topdecks be perfect!** 🎴✨

</div>
