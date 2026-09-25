"""Command-line entry point.

    python main.py --sample early_sepsis
    python main.py --file my_patient.json
    python main.py --sample early_sepsis --offline
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from early_warning import SAMPLES, generate, load_patient, run_agent
from early_warning.report import render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clinical early-warning agent (educational, synthetic data).")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--sample", choices=sorted(SAMPLES), default="early_sepsis", help="a built-in synthetic patient")
    source.add_argument("--file", help="a patient JSON file (see README for the format)")
    parser.add_argument("--offline", action="store_true", help="skip Gemini; use the tools and a template explanation")
    parser.add_argument("--model", help="Gemini model (default: GEMINI_MODEL or gemini-2.5-flash)")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args(argv)

    load_dotenv()
    patient = load_patient(args.file) if args.file else generate(args.sample)
    result = run_agent(patient, model=args.model, offline=args.offline)
    if args.json:
        print(json.dumps({"assessment": result.assessment, "explanation": result.explanation, "source": result.source,
                          "model": result.model, "note": result.note, "trace": result.trace}, indent=2, default=str))
    else:
        print(render(result, patient.label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
