#!/usr/bin/env python3
"""
Interactive CLI for InterviewManager + Interview_functions.

Mirrors the /api/generate-response path (InterviewManager.receive_input) without
Flask, DB, auth, or TTS — so you can manually walk the full interview flow.

Usage (from repo root or backend/):

  cd backend
  set RUNTIME_CONFIG_ALLOW_ENV=true
  set LLM_PROVIDER=ollama
  set OLLAMA_MODEL=llama3
  python scripts/cli_interview_manager.py

Commands during the interview:
  END_INTERVIEW   Force wrap-up evaluation (same as the app end button)
  /status         Show current stage flags
  /help           Show commands
  quit / exit     Leave without evaluation
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
INTERVIEW_DIR = BACKEND_DIR / "INTERVIEW"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(INTERVIEW_DIR) not in sys.path:
    sys.path.insert(0, str(INTERVIEW_DIR))

# Laptop config: allow backend/.env before importing interview modules.
os.environ.setdefault("RUNTIME_CONFIG_ALLOW_ENV", "true")

from common.runtime_config import load_runtime_config, optional_env  # noqa: E402
from common.llm.factory import provider_name as llm_provider_name  # noqa: E402

load_runtime_config()

from INTERVIEW.Interview_manager import InterviewManager  # noqa: E402


CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


DEFAULT_CONFIG: dict[str, Any] = {
    "job_title": "Backend Software Engineer",
    "job_description": (
        "Build and operate scalable HTTP APIs in Python. Work with PostgreSQL, "
        "Redis, AWS, JWT auth, and CI/CD. 3+ years backend experience preferred."
    ),
    "interview_style": "conversational",
    "time_limit_minutes": 0,
    "icebreakers": [],
    "custom_questions": [
        "Tell me about a time you disagreed with a teammate on a technical decision. How did you handle it?",
    ],
    "coding_requirement": [],
    "core_questions": [
        {
            "question_text": (
                "Walk through a key backend initiative you owned — what did you "
                "build, and what measurable outcome did it create?"
            ),
            "requires_code": False,
            "difficulty_level": "easy",
        },
        {
            "question_text": (
                "Describe how you design a service that must handle traffic spikes. "
                "What bottlenecks do you watch for first?"
            ),
            "requires_code": False,
            "difficulty_level": "medium",
        },
        {
            "question_text": (
                "Tell me about a production incident you helped resolve. What was "
                "the root cause, and what changed afterward?"
            ),
            "requires_code": False,
            "difficulty_level": "hard",
        },
    ],
}


def _print_banner(model: str, config: dict[str, Any]) -> None:
    provider = llm_provider_name()
    print(f"\n{BOLD}Interview Manager CLI{RESET}")
    print(f"{DIM}Provider: {provider} | Model: {model}{RESET}")
    print(f"{DIM}Role: {config.get('job_title', 'unknown')}{RESET}")
    print(f"{DIM}Core questions: {len(config.get('core_questions') or [])} | "
          f"Custom: {len(config.get('custom_questions') or [])}{RESET}")
    print(
        f"{DIM}Type answers normally. Commands: END_INTERVIEW, /status, /help, quit{RESET}\n"
    )


def _print_assistant(message: str, stage: str | None = None, extra: dict | None = None) -> None:
    stage_bit = f" [{stage}]" if stage else ""
    print(f"\n{CYAN}{BOLD}Interviewer{stage_bit}:{RESET}")
    print(message)
    if extra:
        flags = []
        if extra.get("requires_code"):
            flags.append(f"requires_code={extra.get('requires_code')}")
        if extra.get("code_language"):
            flags.append(f"code_language={extra.get('code_language')}")
        if extra.get("timeout_detected"):
            flags.append("timeout_detected")
        if flags:
            print(f"{DIM}({' | '.join(flags)}){RESET}")


def _print_status(manager: InterviewManager) -> None:
    print(f"\n{YELLOW}--- status ---{RESET}")
    print(f"stage={manager.stage}")
    print(
        f"intro_done={manager.intro_done} icebreaker_done={manager.icebreaker_done} "
        f"intro_followup_done={manager.intro_followup_done}"
    )
    print(
        f"resume_left={len(manager.core_questions or [])} "
        f"custom_left={len(manager.required_questions or [])} "
        f"candidate_qna_done={manager.candidate_qna_done}"
    )
    print(f"api_calls={manager.api_call_count} eval_entries={len(manager.evaluation_log or [])}")
    print(f"{YELLOW}--------------{RESET}\n")


def _print_help() -> None:
    print(
        f"""
{YELLOW}Commands{RESET}
  END_INTERVIEW   Run wrap-up evaluation and finish
  /status         Show stage flags and remaining questions
  /help           Show this help
  quit / exit     Leave without evaluation
"""
    )


def _print_final(manager: InterviewManager, response: dict[str, Any]) -> None:
    print(f"\n{GREEN}{BOLD}=== Interview complete ==={RESET}")
    summary = response.get("summary") or getattr(manager, "final_summary", None)
    strengths = response.get("key_strengths") or getattr(manager, "key_strengths", None)
    improvements = response.get("improvement_areas") or getattr(manager, "improvement_areas", None)
    rating = response.get("overall_rating")
    if rating is None:
        rating = getattr(manager, "overall_rating", None)

    if summary:
        print(f"\n{BOLD}Summary{RESET}\n{summary}")
    if strengths:
        print(f"\n{BOLD}Key strengths{RESET}\n{strengths}")
    if improvements:
        print(f"\n{BOLD}Improvement areas{RESET}\n{improvements}")
    if rating is not None:
        print(f"\n{BOLD}Overall rating:{RESET} {rating}")
    print(f"\n{DIM}Turns (API calls): {manager.api_call_count}{RESET}\n")


def _load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return json.loads(json.dumps(DEFAULT_CONFIG))
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        loaded = json.load(fh)
    if not isinstance(loaded, dict):
        raise ValueError("Config JSON must be an object")
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged.update(loaded)
    # Keep sample questions if the file omits them (common for interview_config.json).
    if not merged.get("core_questions"):
        merged["core_questions"] = list(DEFAULT_CONFIG["core_questions"])
    return merged


def _stream_token(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def run_interview(*, model: str, config: dict[str, Any], stream: bool) -> int:
    _print_banner(model, config)
    manager = InterviewManager.from_config(config, model=model)
    manager.time_limit_seconds = 0

    # Greeting was printed by InterviewManager; also show stage label once.
    if manager.conversation_history:
        _print_assistant(manager.conversation_history[-1]["content"], stage=manager.stage)

    turn = 0
    while True:
        try:
            user_input = input(f"\n{GREEN}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Exiting.{RESET}")
            return 0

        if not user_input:
            continue

        lowered = user_input.lower()
        if lowered in {"quit", "exit", "/quit", "/exit"}:
            print(f"{DIM}Left interview without evaluation.{RESET}")
            return 0
        if lowered in {"/help", "help"}:
            _print_help()
            continue
        if lowered in {"/status", "status"}:
            _print_status(manager)
            continue

        turn += 1
        on_token = _stream_token if stream else None
        if stream:
            print(f"\n{CYAN}{BOLD}Interviewer:{RESET} ", end="", flush=True)

        try:
            response = manager.receive_input(user_input, on_token=on_token)
        except Exception as exc:
            print(f"\n{YELLOW}Error on turn {turn}: {exc}{RESET}")
            traceback.print_exc()
            continue

        if not isinstance(response, dict):
            print(f"{YELLOW}Unexpected response type: {type(response)}{RESET}")
            continue

        message = (response.get("message") or "").strip()
        stage = response.get("stage")
        if stream:
            # Tokens already printed; still show stage line.
            print(f"\n{DIM}stage={stage}{RESET}")
        else:
            _print_assistant(message, stage=stage, extra=response)

        if response.get("interview_done") or response.get("timeout_detected"):
            _print_final(manager, response)
            return 0

        # After resume wraps with stage "done" but interview still active,
        # remind the user they can continue (candidate Q&A) or END_INTERVIEW.
        if stage == "done" and not response.get("interview_done"):
            print(
                f"{DIM}Tip: send another message to continue, or type END_INTERVIEW "
                f"for evaluation.{RESET}"
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual CLI walkthrough of InterviewManager stages."
    )
    parser.add_argument(
        "--config",
        help="Optional JSON config (job_title, core_questions, custom_questions, ...).",
    )
    parser.add_argument(
        "--model",
        default=optional_env("OLLAMA_MODEL", "llama3") or "llama3",
        help="Model name passed into InterviewManager (default: OLLAMA_MODEL or llama3).",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream interviewer tokens to the terminal when the LLM supports it.",
    )
    parser.add_argument(
        "--dump-default-config",
        action="store_true",
        help="Print the built-in sample config JSON and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dump_default_config:
        print(json.dumps(DEFAULT_CONFIG, indent=2))
        return 0

    config = _load_config(args.config)
    return run_interview(model=args.model, config=config, stream=args.stream)


if __name__ == "__main__":
    raise SystemExit(main())
