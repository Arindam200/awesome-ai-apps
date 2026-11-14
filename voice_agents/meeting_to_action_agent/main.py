import os
import sys
import json
from openai import OpenAI

# Configuration - works with OpenAI, Ollama, or vLLM
API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1") # Defaults to Ollama
API_KEY = os.getenv("OPENAI_API_KEY", "not-needed")
MODEL_NAME = os.getenv("MODEL_NAME", "llama3")

client = OpenAI(base_url=API_BASE, api_key=API_KEY)

def process_transcript(transcript_text: str) -> dict:
    """Processes a meeting transcript and extracts structured action items."""
    
    system_prompt = """
    You are an enterprise AI meeting assistant. 
    Extract operational outputs from the provided meeting transcript.
    
    You must extract:
    1. Action Items
    2. Owners (if not explicitly stated, you MUST use "Uncertain")
    3. Deadlines (if not explicitly stated, you MUST use "Uncertain")
    4. Risks
    5. Blockers
    6. Follow-ups
    7. Open Questions
    
    Do NOT guess or invent owners or dates. If the transcript does not explicitly say who owns a task or when it is due, label it "Uncertain".
    
    Output strict JSON format with the following schema:
    {
        "action_items": [{"task": "string", "owner": "string", "deadline": "string"}],
        "risks": ["string"],
        "blockers": ["string"],
        "follow_ups": ["string"],
        "open_questions": ["string"]
    }
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here is the transcript:\n\n{transcript_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        result = json.loads(response.choices[0].message.content)
        
        # Ensure required keys exist
        for key in ["action_items", "risks", "blockers", "follow_ups", "open_questions"]:
            if key not in result:
                result[key] = []
                
        # Handle missing/null owners or deadlines
        for item in result.get("action_items", []):
            if not item.get("owner") or item.get("owner") == "null":
                item["owner"] = "Uncertain"
            if not item.get("deadline") or item.get("deadline") == "null":
                item["deadline"] = "Uncertain"
                
        return result
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return {}

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    transcript_path = os.path.join(script_dir, "sample_transcript.txt")
    output_path = os.path.join(script_dir, "output.json")

    print(f"Reading transcript from {transcript_path}...")
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = f.read()

    print(f"Processing with model: {MODEL_NAME}...")
    result = process_transcript(transcript)

    if result:
        print(f"Writing structured output to {output_path}...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)
        print("✅ Success! Check output.json")
    else:
        print("❌ Failed to process transcript.")
        sys.exit(1)

if __name__ == "__main__":
    main()