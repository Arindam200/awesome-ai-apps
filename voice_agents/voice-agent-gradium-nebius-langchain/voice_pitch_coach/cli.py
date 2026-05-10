from __future__ import annotations

import argparse
from pathlib import Path

from .async_utils import run_async
from .coach import NebiusPitchCoach
from .gradium_audio import GradiumAudio
from .settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a recorded pitch with Gradium + Nebius.")
    parser.add_argument("audio", type=Path, help="Path to a WAV recording.")
    parser.add_argument("--scenario", default="startup pitch")
    parser.add_argument("--audience", default="early-stage investors")
    parser.add_argument("--goal", default="make the idea clear and earn a follow-up meeting")
    parser.add_argument("--previous-question", default="")
    parser.add_argument("--voice-output", type=Path, default=Path("outputs/coach-feedback.wav"))
    args = parser.parse_args()

    settings = load_settings()
    audio = GradiumAudio(
        api_key=settings.gradium_api_key,
        base_url=settings.gradium_base_url,
        voice_id=settings.gradium_voice_id,
    )
    coach = NebiusPitchCoach(api_key=settings.nebius_api_key, model=settings.nebius_model)

    transcript = run_async(audio.transcribe_wav(args.audio.read_bytes()))
    result = coach.analyze(
        transcript=transcript,
        scenario=args.scenario,
        audience=args.audience,
        goal=args.goal,
        previous_question=args.previous_question,
    )
    run_async(audio.speak_to_file(result.spoken_feedback + " " + result.next_question, args.voice_output))

    print("\nTranscript")
    print(transcript)
    print("\nScore")
    print(f"{result.overall_score}/100")
    print("\nFeedback")
    print(result.spoken_feedback)
    print("\nSuggested rewrite")
    print(result.suggested_rewrite)
    print("\nNext question")
    print(result.next_question)
    print(f"\nVoice feedback written to {args.voice_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
