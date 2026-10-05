"""Resume text extraction and structured parsing only."""
from __future__ import annotations

import json
import os
import re

import PyPDF2
import docx

try:
    import textract
except ImportError:
    textract = None

from INTERVIEW.generation_utils import (
    ResumeParseError,
    parse_ollama_resume_json_response,
    try_ollama_chat,
)

ENABLE_LOGGING = True
# Retries per resume chunk when LLM returns invalid JSON or an unusable empty object.
RESUME_CHUNK_JSON_MAX_ATTEMPTS = 10

if ENABLE_LOGGING and not os.path.exists("logs"):
    os.makedirs("logs")


def extract_text_from_resume(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"[ERROR] File not found: {file_path}")
    
    print(f"[INFO] Extracting text from: {file_path}")
    
    try:
        file_ext = file_path.lower().split('.')[-1]
        
        if file_ext == 'pdf':
            # Use PyPDF2 for PDF files (more reliable on Windows)
            return extract_text_from_pdf(file_path)
        elif file_ext in ['docx', 'doc']:
            # Use python-docx for Word documents
            return extract_text_from_docx(file_path)
        elif file_ext == 'txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as handle:
                return handle.read().strip()
        else:
            # Fallback to textract for other file types
            return extract_text_from_textract(file_path)
            
    except Exception as e:
        raise RuntimeError(f"[ERROR] Failed to extract text: {e}")

def extract_text_from_pdf(file_path):
    """Extract text from PDF using PyPDF2"""
    try:
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"[WARNING] PyPDF2 failed: {e}")
        # Fallback to textract
        return extract_text_from_textract(file_path)

def extract_text_from_docx(file_path):
    """Extract text from DOCX using python-docx"""
    try:
        doc = docx.Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        print(f"[WARNING] python-docx failed: {e}")
        # Fallback to textract
        return extract_text_from_textract(file_path)

def extract_text_from_textract(file_path):
    """Fallback method using textract"""
    if textract is None:
        raise RuntimeError("[ERROR] Textract is not installed on this server.")
    try:
        text = textract.process(file_path).decode("utf-8", errors="ignore")
        return text
    except Exception as e:
        raise RuntimeError(f"[ERROR] Textract failed: {e}")

def split_resume_into_chunks(text, max_tokens=1500, overlap=200):
    try:
        import tiktoken
    except ImportError:
        raise ImportError("Please install tiktoken: pip install tiktoken")

    enc = tiktoken.get_encoding("cl100k_base")
  # You can use "gpt-3.5-turbo" if llama3 gives error
    tokens = enc.encode(text)
    print(f"[INFO] Resume token count: {len(tokens)}")

    chunks = []
    start = 0

    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk = enc.decode(tokens[start:end])
        chunks.append(chunk)
        start += max_tokens - overlap

    return chunks


def ask_ollama_for_structured_data_chunked(resume_text, model="llama3"):
    chunks = split_resume_into_chunks(resume_text)
    merged_result = {
        "full_name": "",
        "email": "",
        "phone": "",
        "location": "",
        "summary": "",
        "skills": [],
        "education": [],
        "work_experience": [],
        "projects": [],
        "certifications": [],
        "tools_and_technologies": {
        "Operating Systems": [],
        "Languages": [],
        "Databases": [],
        "Automation Tools": [],
        "Load Testing": [],
        "Version Control": [],
        "Bug Trackers": []
        },
        "links": {
        "linkedin": "",
        "github": ""
        }

    }
    print(f"[INFO] Total chunks to process: {len(chunks)}")
    for idx, chunk in enumerate(chunks):
        print(f"[INFO] Processing chunk {idx + 1}/{len(chunks)}...")
        prompt = f"""
        You are a strict but intelligent JSON resume parser. Extract **detailed** structured resume data for the following chunk.

        IMPORTANT:
        - Do NOT include explanations.
        - Do NOT return arrays or lists at the top level.
        - Do NOT wrap JSON in markdown (no ```json).
        - Respond with ONE and ONLY ONE valid JSON object.

        Use this format:
        {{
        "full_name": "",
        "email": "",
        "phone": "",
        "location": "",
        "summary": "",  // Write a strong summary if found
        "skills": [],  // Parse technical and soft skills
        "tools_and_technologies": {{
            "Operating Systems": [],
            "Languages": [],
            "Databases": [],
            "Automation Tools": [],
            "Load Testing": [],
            "Version Control": [],
            "Bug Trackers": []
        }},
        "education": [{{"institution": "", "degree": "", "year": "", "percentage": ""}}],
        "work_experience": [{{"title": "", "company": "", "location": "", "from": "", "to": "", "description": ""}}],
        "projects": [{{"name": "", "role": "", "tools": [], "description": ""}}],
        "certifications": [],
        "links": {{
            "linkedin": "",
            "github": ""
            }}
        }}

        Instructions:
        - Include **descriptions** for experience and projects if available.
        - Infer missing data like location or role **only if contextually obvious**.
        - Deduplicate repeated tool variants (e.g., Selenium WebDriver, Selenium).
        - Use consistent formatting for dates and names.

        Resume chunk:
        \"\"\"
        {chunk}
        \"\"\"
        """

        partial = None
        content = ""
        for parse_attempt in range(RESUME_CHUNK_JSON_MAX_ATTEMPTS):
            response = try_ollama_chat(prompt, model=model)
            content = response["message"]["content"]
            if ENABLE_LOGGING:
                chunk_log_path = f"logs/chunk_{idx+1}_attempt_{parse_attempt + 1}.json"
                with open(chunk_log_path, "w", encoding="utf-8") as f:
                    f.write(content)

            partial = parse_ollama_resume_json_response(content)
            if partial is None:
                print(
                    f"[WARNING] Chunk {idx + 1} invalid JSON "
                    f"(attempt {parse_attempt + 1}/{RESUME_CHUNK_JSON_MAX_ATTEMPTS}). Retrying..."
                )
                continue

            missing_fields = [key for key in partial if not partial.get(key) and key != "summary"]
            if len(missing_fields) == len(partial) - 1:
                print(
                    f"[WARNING] Chunk {idx + 1} returned mostly empty fields "
                    f"(attempt {parse_attempt + 1}/{RESUME_CHUNK_JSON_MAX_ATTEMPTS}). Retrying..."
                )
                partial = None
                continue
            if parse_attempt > 0:
                print(f"[INFO] Chunk {idx + 1} parsed successfully on attempt {parse_attempt + 1}.")
            break

        if partial is None:
            print(
                f"[ERROR] Chunk {idx + 1}: no valid JSON after {RESUME_CHUNK_JSON_MAX_ATTEMPTS} attempts. Skipping."
            )
            if ENABLE_LOGGING:
                with open("logs/failed_chunks.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n=== CHUNK {idx + 1} (exhausted retries) ===\n{content}\n")
            continue


        # Merge logic (combine lists, fill blanks)
        for key in merged_result:
            if isinstance(merged_result[key], list):
                merged_result[key].extend(item for item in partial.get(key, []) if item not in merged_result[key])
            elif not merged_result[key] and partial.get(key):
                merged_result[key] = partial[key]
            elif key == "summary" and partial.get(key):
                if partial[key] not in merged_result[key]:
                    merged_result[key] += " " + partial[key]
        # Merge links (GitHub/LinkedIn)
        if "links" in partial:
            # Handle case where links might be returned as a list instead of dict
            if isinstance(partial["links"], list):
                print(f"[WARNING] Chunk {idx+1} returned links as list instead of dict: {partial['links']}")
                # Try to extract links from the list if possible
                for link_item in partial["links"]:
                    if isinstance(link_item, str):
                        if "linkedin.com" in link_item.lower() and not merged_result["links"]["linkedin"]:
                            merged_result["links"]["linkedin"] = link_item
                        elif "github.com" in link_item.lower() and not merged_result["links"]["github"]:
                            merged_result["links"]["github"] = link_item
            elif isinstance(partial["links"], dict):
                # Normal case - links is a dictionary
                for platform in ["linkedin", "github"]:
                    if partial["links"].get(platform) and not merged_result["links"].get(platform):
                        merged_result["links"][platform] = partial["links"][platform]
            else:
                print(f"[WARNING] Chunk {idx+1} returned links as unexpected type: {type(partial['links'])}")

        # Special merging for nested tools_and_technologies
        # Normalize known mislabels to match the target schema
        tool_aliases = {
            "Bug Tracking tools": "Bug Trackers",
            "Load testing tools": "Load Testing",
            "Version control": "Version Control",
            "Operating System": "Operating Systems",
            "OS": "Operating Systems",
            "Automation Tool": "Automation Tools"
        }
        if "tools_and_technologies" in partial:
            for tech_key, tech_values in partial["tools_and_technologies"].items():
                normalized_key = tool_aliases.get(tech_key.strip(), tech_key.strip())
                if normalized_key not in merged_result["tools_and_technologies"]:
                    merged_result["tools_and_technologies"][normalized_key] = []
                merged_result["tools_and_technologies"][normalized_key].extend([
                    v for v in tech_values if v not in merged_result["tools_and_technologies"][normalized_key]
                ])

    # Deduplicate fields
    merged_result["skills"] = deduplicate_string_list(merged_result["skills"])
    # simple strings

    # Use custom deduplicator for lists of dictionaries
    for key in ["projects", "certifications", "education", "work_experience"]:
        merged_result[key] = deduplicate_dict_list(merged_result[key])
    # Move email/phone into contact object
    # Normalize title casing and whitespace for job titles and company names
    for exp in merged_result["work_experience"]:
        if "title" in exp and exp["title"]:
            exp["title"] = exp["title"].strip().title()
        if "company" in exp and exp["company"]:
            exp["company"] = exp["company"].strip()

    merged_result["contact"] = {
        "email": merged_result.pop("email", ""),
        "phone": merged_result.pop("phone", "")
    }

    # Rename full_name to name
    if "full_name" in merged_result:
        merged_result["name"] = ' '.join(w.capitalize() for w in merged_result.pop("full_name").split())

    if not merged_result["summary"]:
        summary_prompt = f"Summarize this resume in 2–3 sentences as if you're describing the candidate's professional profile:\n\n{chunks[0]}"
        summary_resp = try_ollama_chat(summary_prompt, model=model)
        merged_result["summary"] = summary_resp["message"]["content"].strip()
    merged_result["education"] = [e for e in merged_result["education"] if isinstance(e, dict) and any(e.values())]
    merged_result["projects"] = [p for p in merged_result["projects"] if isinstance(p, dict) and any(p.values())]

    # Deduplicate entries within each tools_and_technologies category
    for k in merged_result["tools_and_technologies"]:
        merged_result["tools_and_technologies"][k] = deduplicate_string_list(
            merged_result["tools_and_technologies"][k]
        )

    print("[DONE] Completed parsing all chunks.")
    # Fallback: Try regex detection if links are still missing
    if not merged_result["links"]["linkedin"]:
        match = re.search(r'https?://(www\.)?linkedin\.com/in/[a-zA-Z0-9\-_]+', resume_text)
        if match:
            merged_result["links"]["linkedin"] = match.group(0)

    if not merged_result["links"]["github"]:
        match = re.search(r'https?://(www\.)?github\.com/[a-zA-Z0-9\-_]+', resume_text)
        if match:
            merged_result["links"]["github"] = match.group(0)

    return merged_result


def deduplicate_dict_list(lst):
    seen = set()
    deduped = []
    for item in lst:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped


def deduplicate_string_list(lst):
    return sorted(list(set(item.strip() for item in lst if isinstance(item, str) and item.strip())))


def _resume_has_usable_sections(structured_data):
    if not isinstance(structured_data, dict):
        return False
    return bool(
        structured_data.get("work_experience")
        or structured_data.get("projects")
        or structured_data.get("education")
        or structured_data.get("skills")
        or structured_data.get("summary")
    )


def build_structured_resume_fallback(resume_text):
    """Non-LLM structured resume when Ollama parsing is empty or unavailable."""
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    name = lines[0][:80] if lines else "Candidate"
    if len(name.split()) > 5:
        name = "Candidate"

    skills = []
    skill_markers = ("skills", "technical skills", "core competencies")
    capture_skills = False
    for line in lines:
        lower = line.lower()
        if any(marker in lower for marker in skill_markers):
            capture_skills = True
            continue
        if capture_skills:
            if line.isupper() and len(line) < 40:
                break
            parts = re.split(r"[,;|•·]", line)
            for part in parts:
                token = part.strip(" -•·\t")
                if 2 <= len(token) <= 40:
                    skills.append(token)
            if len(skills) >= 8:
                break

    summary_lines = lines[1:6]
    summary = " ".join(summary_lines)[:600].strip()

    return {
        "name": name,
        "location": "",
        "summary": summary or resume_text[:500].strip(),
        "skills": deduplicate_string_list(skills)[:25],
        "education": [],
        "work_experience": [],
        "projects": [],
        "certifications": [],
        "tools_and_technologies": {
            "Operating Systems": [],
            "Languages": [],
            "Databases": [],
            "Automation Tools": [],
            "Load Testing": [],
            "Version Control": [],
            "Bug Trackers": [],
        },
        "links": {"linkedin": "", "github": ""},
        "contact": {"email": "", "phone": ""},
        "parse_source": "keyword_fallback",
    }


def parse_resume_structured(resume_text, model="llama3"):
    """
    Primary: LLM chunked parse. Fallback: heuristic structured parse from raw text.
    """
    structured = ask_ollama_for_structured_data_chunked(resume_text, model=model)
    if _resume_has_usable_sections(structured):
        structured["parse_source"] = structured.get("parse_source") or "llm"
        return structured

    print("[WARN] LLM resume parse returned empty sections; using structured fallback parser.")
    fallback = build_structured_resume_fallback(resume_text)
    if not _resume_has_usable_sections(fallback):
        raise ResumeParseError("Resume parsing returned no usable sections.")
    return fallback


def build_structured_data_from_skills(skills_list):
    """Build a minimal structured resume dict from a list of skills."""
    if not skills_list:
        return None
    skills = [s.strip() for s in skills_list if isinstance(s, str) and s.strip()]
    if not skills:
        return None
    return {
        "name": "Candidate",
        "skills": skills,
        "work_experience": [],
        "projects": [],
        "education": [],
        "certifications": [],
    }

