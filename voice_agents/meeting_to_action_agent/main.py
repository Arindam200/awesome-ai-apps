import os
import sys
import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


# Configuration - defaults to Nebius Token Factory
API_BASE = os.getenv("NEBIUS_API_BASE", "https://api.tokenfactory.nebius.com/v1/")
API_KEY = os.getenv("NEBIUS_API_KEY", "not-needed")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen3-30B-A3B-Instruct-2507")


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


def transcribe_audio(audio_path: str) -> str:
    """Transcribes audio using faster-whisper."""
    try:
        from faster_whisper import WhisperModel
        print(f"Loading Whisper model and transcribing {audio_path}...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        return text
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Meeting-to-Action Voice Agent")
    parser.add_argument("--transcript", type=str, default="sample_transcript.txt", help="Path to transcript file")
    parser.add_argument("--audio", type=str, help="Path to audio file (optional)")
    args = parser.parse_args()


    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "output.json")


    if args.audio:
        transcript = transcribe_audio(args.audio)
        print(f"Transcription complete. {len(transcript)} characters.")
    else:
        transcript_path = args.transcript
        if not os.path.isabs(transcript_path):
            transcript_path = os.path.join(script_dir, transcript_path)


        print(f"Reading transcript from {transcript_path}...")
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript = f.read()
        except FileNotFoundError:
            print(f"❌ Error: Transcript file not found at {transcript_path}")
            sys.exit(1)


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
