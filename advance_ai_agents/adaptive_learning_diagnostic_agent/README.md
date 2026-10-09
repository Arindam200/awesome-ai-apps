 # Adaptive Learning Diagnostic Agent

A multi-agent system that diagnoses step-level misconceptions in student reasoning.

## What It Does
- Parses student reasoning step by step
- Matches against a library of known misconceptions
- Tracks persistence across topics
- Generates targeted follow-up questions

## How to Run
1. Install dependencies: `pip install -r requirements.txt`
2. Run: `python main.py`

## Example
Input: `["i starts at 0", "0 < 5 is true", "i becomes 1", "print 0"]`
Output: `Detected misconception: pre_increment_confusion`

## Tech Stack
- Python
- sentence-transformers
- (Optional) LangGraph for full agent orchestration

## Future Work
- Add more misconceptions
- Integrate with a web UI
- Add persistence tracking across sessions
