#!/usr/bin/env python3
"""Manual check that this machine can reach the configured Bedrock model.

Makes 2-3 tiny, billable model calls. Never prints credentials.

    cd backend
    aws sso login --profile <profile>          # or rely on the EC2 instance role
    AWS_PROFILE=<profile> RUNTIME_CONFIG_ALLOW_ENV=true \
      BEDROCK_CHAT_MODEL=in.openai.gpt-5.6-terra python scripts/bedrock_smoke_test.py [--coach]

Exit code 0 = all checks passed.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_ROOT)
os.environ.setdefault("RUNTIME_CONFIG_ALLOW_ENV", "true")

from common.llm.bedrock import (  # noqa: E402
    BedrockError,
    BedrockLLMProvider,
    _region,
    redact,
    resolve_chat_model,
)
from common.runtime_config import optional_env  # noqa: E402

COACH_SYSTEM = (
    "You are an experienced technical interviewer. Evaluate the candidate's answer. "
    "Reply with: a score from 1 to 10, what was correct, what was missing, a short model "
    "answer, and one follow-up question. Do not invent things the candidate did not say."
)


def step(label: str) -> None:
    print(f"\n▶ {label}")


def ok(msg: str) -> None:
    print(f"  ✔ {msg}")


def warn(msg: str) -> None:
    print(f"  ! {msg}")


def fail(msg: str) -> None:
    print(f"  ✘ {msg}")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coach", action="store_true",
                        help="also run one sample answer evaluation")
    args = parser.parse_args()

    import boto3

    step("Configuration")
    region = _region()
    try:
        model_id = resolve_chat_model()
    except BedrockError as exc:
        fail(str(exc))
    ok(f"region={region}")
    ok(f"model={model_id}")
    ok(f"reasoning_effort={optional_env('LLM_REASONING_EFFORT') or '(model default)'}")

    step("AWS credentials (standard credential chain)")
    try:
        ident = boto3.client("sts", region_name=region).get_caller_identity()
        principal = ident["Arn"].split(":")[-1].split("/")[0]
        ok(f"authenticated as a {principal} in account ****{ident['Account'][-4:]}")
    except Exception as exc:  # noqa: BLE001
        fail(f"no usable AWS credentials: {redact(str(exc))}")

    step("Inference profile lookup (optional; needs bedrock:GetInferenceProfile)")
    try:
        profile = boto3.client("bedrock", region_name=region).get_inference_profile(
            inferenceProfileIdentifier=model_id)
        regions = sorted({m["modelArn"].split(":")[3] or "global"
                          for m in profile.get("models", [])})
        ok(f"status={profile.get('status')} type={profile.get('type')}")
        ok(f"routes to: {', '.join(regions)}")
    except Exception as exc:  # noqa: BLE001
        warn(f"skipped ({type(exc).__name__}) — fine if model is a bare model ID or "
             "the role lacks GetInferenceProfile")

    provider = BedrockLLMProvider()
    messages = [{"role": "user", "content": "Reply with the single word OK."}]

    step("Converse (non-streaming)")
    try:
        started = time.time()
        res = provider.chat(model=model_id, messages=messages, max_tokens=256)
        if not res["message"]["content"]:
            warn(f"empty reply (stop_reason={res['stop_reason']}): reasoning likely used the "
                 "token budget — lower LLM_REASONING_EFFORT")
        ok(f"reply={res['message']['content'][:40]!r} stop={res['stop_reason']} "
           f"latency={int((time.time() - started) * 1000)}ms usage={res['usage']}")
    except BedrockError as exc:
        fail(f"[{exc.code}] {exc}")

    step("ConverseStream (streaming)")
    try:
        chunks = list(provider.chat_stream(model=model_id, messages=messages, max_tokens=256))
        ok(f"{len(chunks)} chunk(s): {''.join(chunks)[:40]!r}")
    except BedrockError as exc:
        fail(f"[{exc.code}] {exc}")

    if args.coach:
        step("Sample answer evaluation")
        res = provider.chat(
            model=model_id,
            max_tokens=600,
            messages=[
                {"role": "system", "content": COACH_SYSTEM},
                {"role": "user", "content": (
                    "Question: What is the difference between a process and a thread?\n"
                    "Candidate answer: A process has its own memory, threads share memory "
                    "inside a process so they are lighter but need locks.")},
            ],
        )
        print("\n" + res["message"]["content"])

    print("\nAll Bedrock checks passed.")


if __name__ == "__main__":
    main()
