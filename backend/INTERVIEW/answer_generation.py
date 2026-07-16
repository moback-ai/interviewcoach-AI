"""Sample answer generation for interview questions."""
from __future__ import annotations

import csv
import json
import os
import tempfile

from INTERVIEW.generation_utils import (
    read_questions_from_csv,
    resolve_ollama_model_name,
    try_ollama_chat,
)
from INTERVIEW.Resumeparser import (
    build_structured_data_from_skills,
    extract_text_from_resume,
    parse_resume_structured,
)


def _is_weak_generated_answer(answer_text):
    text = (answer_text or "").strip().lower()
    if len(text.split()) < 18:
        return True
    weak_phrases = [
        "i don't know",
        "not sure",
        "cannot say",
        "no experience",
        "n/a",
        "as an ai",
        "placeholder",
    ]
    return any(phrase in text for phrase in weak_phrases)


def _generate_follow_up_for_question(original_question, context_answer, model="llama3"):
    prompt = f"""
You are an expert interviewer. The model answer below is too weak or vague for training purposes.

Original question: "{original_question}"
Weak answer: "{context_answer}"

Write ONE specific follow-up question the interviewer should ask if the candidate gives a weak answer.
Return only the follow-up question text.
"""
    try:
        response = try_ollama_chat(prompt.strip(), model=model)
        follow_up = response["message"]["content"].strip().strip('"')
        return follow_up or "Could you walk me through a concrete example with more technical detail?"
    except Exception as exc:
        print(f"[WARN] Follow-up generation failed: {exc}")
        return "Could you elaborate with a specific example from your experience?"


def generate_answers_for_existing_questions(structured_resume, job_title, job_description, questions_csv_path, output_path, model="llama3"):
    if not os.path.exists(questions_csv_path):
        raise FileNotFoundError(f"[ERROR] CSV not found: {questions_csv_path}")
    resolved_model = resolve_ollama_model_name(model)
    stats = {
        "requested": True,
        "model": resolved_model,
        "generated_count": 0,
        "fallback_count": 0,
        "fallback_examples": [],
    }

    def fallback_answer(question, strength):
        labels = {
            "weak": "easy",
            "medium": "intermediate",
            "strong": "expert",
        }
        level = labels.get(strength, strength)
        if strength == "weak":
            return (
                f"A good {level} answer should explain the core idea behind this question in simple terms, "
                f"then connect it to one relevant example from the candidate's experience: {question}"
            )
        if strength == "medium":
            return (
                f"A good {level} answer should describe a practical approach, the main steps taken, "
                f"the tools or concepts involved, and one measurable outcome related to: {question}"
            )
        return (
            f"A good {level} answer should go deeper into tradeoffs, edge cases, design choices, "
            f"risk handling, and how success would be measured for: {question}"
        )

    # FIX: Use the correct output path instead of overwriting the input file
    with open(questions_csv_path, "r", encoding="utf-8") as infile, open(output_path, "w", newline='', encoding="utf-8") as outfile:
        reader = csv.DictReader(infile)
        writer = csv.writer(outfile)
        writer.writerow(["question_id", "question", "level", "strength", "answer", "requires_code", "answer_source", "follow_up_question"])

        for row in reader:
            if row.get("strength"):  # Skip rows that already have answers
                continue
            print(f"[DEBUG] Generating answers for {row['question_id']} [{row['level']}]: {row['question'][:80]}...")        
            
            # Get requires_code from input row (default to False if not present)
            requires_code = row.get('requires_code', 'false').lower() == 'true'
            follow_up_question = ""
            
            for strength in ["weak", "medium", "strong"]:  # These map to beginner, intermediate, expert in read_questions_from_csv
                prompt = f"""
You are an expert interviewer.

Write a {strength} answer to this interview question:

Job Title: {job_title}
Level: {row['level']}
Question: "{row['question']}"

Resume:
{json.dumps(structured_resume, indent=2)}

Job Description:
{job_description}

Only respond with the answer text, no formatting.
"""
                try:
                    response = try_ollama_chat(prompt.strip(), model=resolved_model)
                    answer = response["message"]["content"].strip().replace('"', "'")
                    if not answer:
                        raise ValueError("Empty answer generated")
                    row_follow_up = ""
                    if strength == "weak" and _is_weak_generated_answer(answer):
                        row_follow_up = _generate_follow_up_for_question(row["question"], answer, model=model)
                        if not follow_up_question:
                            follow_up_question = row_follow_up
                    writer.writerow([
                        row["question_id"],
                        row["question"],
                        row["level"],
                        strength,
                        answer,
                        "true" if requires_code else "false",
                        "ai",
                        row_follow_up,
                    ])
                    stats["generated_count"] += 1
                    print(f"[DEBUG] ↳ {strength.capitalize()} answer generated.")
                except Exception as e:
                    print(f"[ERROR] Failed generating answer for {row['question_id']} [{strength}]: {e}")
                    answer = fallback_answer(row["question"], strength)
                    row_follow_up = ""
                    if strength == "weak":
                        row_follow_up = _generate_follow_up_for_question(row["question"], answer, model=model)
                        if not follow_up_question:
                            follow_up_question = row_follow_up
                    writer.writerow([
                        row["question_id"],
                        row["question"],
                        row["level"],
                        strength,
                        answer,
                        "true" if requires_code else "false",
                        "fallback",
                        row_follow_up,
                    ])
                    stats["fallback_count"] += 1
                    if len(stats["fallback_examples"]) < 10:
                        stats["fallback_examples"].append({
                            "question_id": row["question_id"],
                            "strength": strength,
                            "error": str(e),
                        })
                    print(f"[WARN] ↳ Wrote fallback {strength} answer for {row['question_id']}")

    print(f"[DONE] Answers written to: {output_path}")
    return stats


def run_generate_answers_for_question_set(
    resume_path,
    job_title,
    job_description,
    question_rows,
    model="llama3",
    skills_list=None,
):
    """
    Generate sample answers (weak/medium/strong) for existing questions only.
    question_rows: list of dicts from DB (question_text, difficulty_level, requires_code, ...).
    """
    resolved_model = resolve_ollama_model_name(model)
    if skills_list:
        structured_data = build_structured_data_from_skills(skills_list)
        if not structured_data or not structured_data.get("skills"):
            return {"success": False, "error": "skills_list is required for skills-based profiles"}
    else:
        if not resume_path or not os.path.exists(resume_path):
            return {"success": False, "error": "Resume file not found for answer generation"}
        resume_text = extract_text_from_resume(resume_path)
        from common.document_validation import validate_resume_text
        is_valid_resume, resume_validation_error = validate_resume_text(resume_text)
        if not is_valid_resume:
            return {"success": False, "error": resume_validation_error}
        structured_data = parse_resume_structured(resume_text)

    def _csv_level(raw_level):
        level = (raw_level or "medium").strip().lower()
        if level in ("easy", "beginner", "basic"):
            return "beginner"
        if level in ("hard", "expert", "advanced"):
            return "hard"
        return "medium"

    seen = set()
    csv_rows = []
    qid = 1
    for row in question_rows or []:
        q_text = (row.get("question_text") or row.get("question") or "").strip()
        if not q_text:
            continue
        csv_level = _csv_level(row.get("difficulty_level") or row.get("difficulty_category"))
        key = (csv_level, q_text.lower())
        if key in seen:
            continue
        seen.add(key)
        requires_code = row.get("requires_code", False)
        if isinstance(requires_code, str):
            requires_code = requires_code.lower() == "true"
        csv_rows.append({
            "question_id": f"q{qid}",
            "question": q_text,
            "level": csv_level,
            "requires_code": requires_code,
        })
        qid += 1

    if not csv_rows:
        return {"success": False, "error": "No questions found to generate answers for"}

    temp_dir = tempfile.mkdtemp(prefix="answer_gen_")
    questions_path = os.path.join(temp_dir, "questions.csv")
    qa_path = os.path.join(temp_dir, "interview_output.csv")

    with open(questions_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question_id", "question", "level", "strength", "answer", "requires_code"])
        for r in csv_rows:
            writer.writerow([
                r["question_id"],
                r["question"],
                r["level"],
                "",
                "",
                "true" if r["requires_code"] else "false",
            ])

    answer_generation = generate_answers_for_existing_questions(
        structured_data,
        job_title,
        job_description,
        questions_path,
        qa_path,
        model=resolved_model,
    )
    questions = read_questions_from_csv(qa_path)
    return {
        "success": True,
        "questions": questions,
        "questions_count": len(questions),
        "answer_generation": answer_generation,
        "ollama_model": resolved_model,
    }

