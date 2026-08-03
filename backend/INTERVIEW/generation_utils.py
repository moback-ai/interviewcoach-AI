"""Shared helpers for INTERVIEW generation pipelines (LLM, JSON, CSV)."""
from __future__ import annotations

import csv
import json
import os
import re
import threading
from contextlib import contextmanager


_token_tls = threading.local()


def _estimate_tokens(text: str) -> int:
    """Rough token estimate when the provider does not return usage metrics."""
    text = text or ""
    if not text:
        return 0
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        # ~4 chars/token heuristic
        return max(1, (len(text) + 3) // 4)


def _usage_from_response(response, prompt_text: str = "") -> tuple[int, int, bool]:
    """
    Return (input_tokens, output_tokens, estimated).
    Prefers provider usage; falls back to estimating from prompt/response text.
    """
    if not isinstance(response, dict):
        content = ""
        return _estimate_tokens(prompt_text), _estimate_tokens(content), True

    usage = response.get("usage")
    if isinstance(usage, dict):
        inp = (
            usage.get("input_tokens")
            if usage.get("input_tokens") is not None
            else usage.get("inputTokens")
        )
        out = (
            usage.get("output_tokens")
            if usage.get("output_tokens") is not None
            else usage.get("outputTokens")
        )
        if inp is None:
            inp = usage.get("prompt_tokens")
        if out is None:
            out = usage.get("completion_tokens")
        if inp is not None or out is not None:
            return int(inp or 0), int(out or 0), False

    # Ollama sometimes puts counts at the top level
    if response.get("prompt_eval_count") is not None or response.get("eval_count") is not None:
        return int(response.get("prompt_eval_count") or 0), int(response.get("eval_count") or 0), False

    content = ((response.get("message") or {}).get("content") or "")
    return _estimate_tokens(prompt_text), _estimate_tokens(content), True


class TokenUsageTracker:
    """Accumulates input/output tokens across LLM calls in one generation run."""

    def __init__(self, label: str = "question_generation"):
        self.label = label
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0
        self.estimated_calls = 0
        self.provider = ""
        self.model = ""

    def record(self, response, prompt_text: str = ""):
        inp, out, estimated = _usage_from_response(response, prompt_text)
        self.input_tokens += inp
        self.output_tokens += out
        self.calls += 1
        if estimated:
            self.estimated_calls += 1
        if isinstance(response, dict):
            self.provider = response.get("provider") or self.provider
            self.model = response.get("model") or self.model

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "llm_calls": self.calls,
            "estimated_calls": self.estimated_calls,
            "provider": self.provider,
            "model": self.model,
        }

    def log(self, extra: str = ""):
        estimated_note = (
            f" (includes {self.estimated_calls} estimated call(s))"
            if self.estimated_calls
            else ""
        )
        extra_part = f" | {extra}" if extra else ""
        print(
            f"[INFO] Token usage [{self.label}]: "
            f"input={self.input_tokens} output={self.output_tokens} "
            f"total={self.total_tokens} calls={self.calls}"
            f"{estimated_note}"
            f"{extra_part}"
            + (f" provider={self.provider}" if self.provider else "")
            + (f" model={self.model}" if self.model else "")
        )


@contextmanager
def track_token_usage(label: str = "question_generation"):
    """Context manager that records tokens for all try_ollama_chat calls inside."""
    previous = getattr(_token_tls, "tracker", None)
    tracker = TokenUsageTracker(label=label)
    _token_tls.tracker = tracker
    try:
        yield tracker
    finally:
        _token_tls.tracker = previous


def resolve_ollama_model_name(model=None):
    from common.runtime_config import optional_env as runtime_optional_env

    configured_model = (
        runtime_optional_env("OLLAMA_MODEL")
        or runtime_optional_env("BEDROCK_CHAT_MODEL", "llama3.2:3b")
    )

    configured_model = (configured_model or "llama3.2:3b").strip()
    requested_model = (model or "").strip()
    if not requested_model or requested_model == "llama3":
        return configured_model
    return requested_model


def clean_json_like_text(raw_text):
    # Remove JS-style comments
    raw_text = re.sub(r'//.*', '', raw_text)

    # Remove trailing commas before closing braces/brackets
    raw_text = re.sub(r',\s*([\]}])', r'\1', raw_text)

    return raw_text.strip()


def _strip_markdown_json_fence(text: str) -> str:
    """Remove optional ``` / ```json wrappers so json.loads can succeed."""
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_ollama_resume_json_response(content: str):
    """
    Parse model output into a dict. Returns None if content is not valid JSON
    (after fence strip and clean_json_like_text fallback).
    """
    candidates = (_strip_markdown_json_fence(content), content.strip())
    seen = set()
    for raw in candidates:
        if raw in seen:
            continue
        seen.add(raw)
        try:
            return json.loads(raw)
        except Exception:
            pass
        try:
            cleaned = clean_json_like_text(raw)
            match = re.search(r"(\{[\s\S]*\})", cleaned)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass
    return None


def extract_json_array(text):
    # Try regex first
    match = re.search(r"\[\s*{.*?}\s*]", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    # Fallback method: find first [ and last ]
    start = text.find("[")
    end = text.rfind("]") + 1
    if start != -1 and end != -1:
        json_chunk = text[start:end]
        return json.loads(json_chunk)

    return []


def _parse_llm_json_object(raw):
    """Parse a JSON object from LLM text (fences, trailing commas, embedded object)."""
    return parse_ollama_resume_json_response(raw or "")


def save_json_output(data, output_path):
    with open(output_path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"[DONE] Parsed resume saved to: {output_path}")


def try_ollama_chat(prompt, model="llama3", max_retries=3, max_tokens=None, temperature=None):
    from common.llm.factory import chat as llm_chat

    resolved_model = resolve_ollama_model_name(model)
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(max_retries):
        try:
            kwargs = {"model": resolved_model, "messages": messages}
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            if temperature is not None:
                kwargs["temperature"] = temperature
            response = llm_chat(**kwargs)
            tracker = getattr(_token_tls, "tracker", None)
            if tracker is not None:
                tracker.record(response, prompt_text=prompt)
            return response
        except Exception as e:
            print(f"[WARNING] LLM attempt {attempt+1} failed for model '{resolved_model}': {e}")
    raise RuntimeError("LLM API failed after multiple attempts.")


def save_questions_to_csv(questions_by_level, output_path):
    with open(output_path, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question_id", "question", "level", "strength", "answer", "requires_code"])
        qid_counter = 1
        
        # Save questions by level (coding questions are already merged into beginner/medium/hard)
        for level in ["beginner", "medium", "hard"]:
            for q in questions_by_level.get(level, []):
                requires_code = q.get('requires_code', False)
                writer.writerow([f"q{qid_counter}", q["question"], level, "", "", "true" if requires_code else "false"])
                qid_counter += 1
            
    print(f"[DEBUG] Saving questions. "
          f"Beginner: {len(questions_by_level.get('beginner', []))}, "
          f"Medium: {len(questions_by_level.get('medium', []))}, "
          f"Hard: {len(questions_by_level.get('hard', []))}")
    print(f"[DONE] Questions saved to: {output_path}")


class ResumeParseError(Exception):
    pass

def read_questions_from_csv(csv_file_path):
    """
    Read questions from CSV file and return them in the format expected by the frontend
    This is a simple wrapper to read the existing CSV output
    """
    questions = []
    
    try:
        if not os.path.exists(csv_file_path):
            print(f"[ERROR] CSV file not found: {csv_file_path}")
            return []
            
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                raw_level = (row.get('level') or '').strip().lower()
                raw_strength = (row.get('strength') or '').strip().lower()

                # Map CSV values to database constraint values
                level_mapping = {
                    'beginner': 'easy',
                    'easy': 'easy',
                    'basic': 'easy',
                    'medium': 'medium', 
                    'intermediate': 'medium',
                    'mid': 'medium',
                    'hard': 'hard',
                    'expert': 'hard',
                    'advanced': 'hard'
                    # Removed 'coding' mapping - coding questions are now categorized by weight
                }
                
                strength_mapping = {
                    'weak': 'beginner',
                    'beginner': 'beginner',
                    'easy': 'beginner',
                    'medium': 'intermediate',
                    'intermediate': 'intermediate',
                    'mid': 'intermediate',
                    'strong': 'expert',
                    'expert': 'expert',
                    'hard': 'expert',
                    'advanced': 'expert'
                }
                
                # Get the mapped values, with fallbacks
                difficulty_category = level_mapping.get(raw_level, 'medium')
                difficulty_experience = strength_mapping.get(raw_strength, 'beginner')
                
                # Get requires_code from CSV (default to False if not present)
                requires_code = row.get('requires_code', 'false').lower() == 'true'
                answer_source = (row.get('answer_source') or '').strip().lower() or "unknown"
                
                # Debug logging
                print(f"[DEBUG] Mapping CSV values: level='{row.get('level', '')}' -> difficulty_category='{difficulty_category}', strength='{row.get('strength', '')}' -> difficulty_experience='{difficulty_experience}', requires_code={requires_code}")
                
                question_data = {
                    "question_text": row['question'],
                    "difficulty_category": difficulty_category,  # easy, medium, hard
                    "difficulty_experience": difficulty_experience,  # beginner, intermediate, expert
                    "requires_code": requires_code  # Add requires_code field
                }
                
                # Include answer if available
                if 'answer' in row and row['answer']:
                    question_data["expected_answer"] = row['answer']
                    question_data["answer_source"] = answer_source
                if row.get('follow_up_question'):
                    question_data["follow_up_question"] = row['follow_up_question']
                
                questions.append(question_data)
        
        return questions
    except Exception as e:
        print(f"[ERROR] Failed to read questions from CSV: {e}")
        return []

