import json
import re
try:
    import ollama
except Exception as ollama_import_error:
    ollama = None


RED = "\033[31m"
BOLD = "\033[1m"
BLUE = "\033[34m"
GREEN = "\033[32m"
CYAN = "\033[36m"
RESET = "\033[0m"


def ollama_chat(*, model, messages):
    if ollama is None:
        raise RuntimeError(f"Ollama is not installed or failed to import: {ollama_import_error}")
    return ollama.chat(model=model, messages=messages)


def log(func_name):
    if func_name.startswith("handle_"):
        color_code = (
            BLUE + BOLD if "intro" in func_name else
            GREEN + BOLD if "job" in func_name else
            CYAN + BOLD if "icebreaker" in func_name else
            "\033[35m" + BOLD if "followup" in func_name else
            "\033[33m" + BOLD if "resume" in func_name else
            "\033[96m" + BOLD if "custom" in func_name else
            "\033[91m" + BOLD if "candidate" in func_name else
            RED + BOLD
        )
    else:  # subfunctions like generate_ / assess_
        color_code = (
            BLUE if "intro" in func_name else
            GREEN if "job" in func_name else
            CYAN if "icebreaker" in func_name else
            "\033[35m" if "followup" in func_name else
            "\033[33m" if "resume" in func_name else
            "\033[96m" if "custom" in func_name else
            "\033[91m" if "candidate" in func_name else
            RED
        )

    print(f"{color_code}[Debug] called {func_name}{RESET}")


# ===== BEGINING OF - INTRO & EXPLAINING JOB DESCRIPTION IF NECESSARY FUNCTIONS USED =====


def generate_contextual_intro_reply(job_title, job_description, conversation_history, user_input):
    log("generate_contextual_intro_reply")

    prompt = f"""
    You are an AI interviewer conducting a friendly but professional job interview for the role of: {job_title}.

    Here is the job description:
    {job_description}

    Your job is to:
    1. If the candidate is asking about the job role, explain it in a **natural and conversational** way. Don’t say things like “The job description says…” or “According to the posting.” Instead, speak as if you're the interviewer summarizing it in your own words.
    2. If the job has already been explained and the candidate is asking follow-up questions, answer those briefly and clearly.
    3. If they are not asking about the job, assume you're still in the introduction phase. Just ask something simple like “Can you tell me a bit about yourself?” — keep it short and friendly.
    4. If the job Q&A just ended, gently transition back to the introduction.

    Keep the tone warm, natural, and interviewer-like.
    Respond with 1–2 well-formed sentences only — no headings, labels, or formatting.
    Avoid repeating greetings like "welcome" or "nice to meet you."

    Only explain the job role if the candidate **explicitly asks** about the role, their responsibilities, or what the job involves.
    Do NOT mention the job unless they directly request it.

    If you are explaining the job role because they asked about it, append this tag at the end of your reply: [[job_explained]]
    Do NOT say or display this tag. It will be used internally.

    """

    messages = [{"role": "system", "content": prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_input})

    try:
        response = ollama_chat(model="llama3", messages=messages)
        content = response["message"]["content"].strip()
        job_flag = False
        if "[[job_explained]]" in content:
            job_flag = True
            content = content.replace("[[job_explained]]", "").strip()

        return {"message": content, "job_explained": job_flag}

    except Exception as e:
        print(f"[ERROR] contextual_intro_reply failed: {e}")
        return {"message": "Could you tell me a bit about yourself?", "job_explained": False}


def assess_intro_progress(conversation_history):
    log("assess_intro_progress")
    prompt = f"""
    You are an AI interviewer at the beginning of a job interview. Here's the conversation so far:

    {json.dumps(conversation_history, indent=2)}

    Your goal is to determine if the candidate has successfully introduced themselves.
    A self-introduction should mention some combination of name, education, work experience, background, or motivation.

    Respond with only one of the following:
    - "continue" → if the candidate introduced themselves with name + education or any meaningful combo
    - "wait" → if they seem mid-way (e.g., paused, said “let me tell more”, etc.)
    - "retry" → only if they’re trolling, completely off-topic, or said something like “idk” or “whatever”

    Note: Accept responses like “that’s all” or “I’ve told everything” as "continue" if any intro details were already shared earlier.

    """

    try:
        response = ollama_chat(
        model="llama3",
        messages=[{"role": "system", "content": prompt}]
        )
        return response["message"]["content"].strip().lower()

    except Exception as e:
        print(f"[ERROR] assess_intro_progress failed: {e}")
        return "retry"
    



# ===== END OF - INTRO & EXPLAINING JOB DESCRIPTION IF NECESSARY FUNCTIONS USED =====

# ===== BEGINING OF - ICE BREAKER FUNCTIONS USED =====
def assess_icebreaker_response(user_response, question):
    log("assess_icebreaker_response")

    prompt = f"""
        You are an AI interviewer assistant. Determine if the candidate's response is relevant and thoughtful in the context of the following icebreaker question.

        Icebreaker Question: "{question}"
        Candidate’s Answer: "{user_response}"

        A valid response should:
        - Either directly answer the question OR mention a personal activity, habit, or interest that reflects their personality.
        - Even if off-topic, a sincere and relevant personal detail is acceptable.
        - Avoid rejecting responses just because they aren’t directly about the question topic — as long as they show effort and honesty.


        A retry is only needed if:
        - The response is vague, clearly off-topic, dismissive, or non-personal
        - The candidate avoids answering or responds with things like “idk”, “nothing”, “whatever”, or gibberish

        Important: Casual or short answers like “I just go to the gym” or “I like being outside” are still valid.

        Respond strictly with one word:
        - valid
        - retry
        """


    try:
        response = ollama_chat(
        model="llama3",
        messages=[{"role": "system", "content": prompt}]
        )
        raw = response['message']['content']
        return raw.strip().lower().replace('"', '').replace("'", "")
    except Exception as e:
        print(f"[ERROR] Icebreaker assessment failed: {e}")
        return "retry"


def generate_icebreaker_question(job_title):
    log("generate_icebreaker_question")
    prompt = f"""
            You are an AI interviewer about to begin a conversation with a candidate for the role of {job_title}.
            Please generate a short and friendly icebreaker question to ask after the candidate's introduction.
            Keep it simple, human, and non-technical.Ask something off the topic , Not studies related. Avoid deep topics or clichés.
            Only respond with the question.
            """
    try:
        response = ollama_chat(model="llama3", messages=[{"role": "system", "content": prompt}])
        return response['message']['content'].strip()

    except Exception as e:
        print(f"[ERROR] Icebreaker generation failed: {e}")
        return "What's a hobby you enjoy during weekends?"    
        
# ===== END OF - ICE BREAKER FUNCTIONS USED =====
    

# ===== BEGGINING OF - INTRO FOLLOW-UP FUNCTIONS USED =====

def assess_followup_response(question, user_response):
    log("assess_followup_response")

    system_prompt = """
        You are an AI interviewer evaluating a candidate’s answer to a follow-up question.

        - "strong" → thoughtful, expressive, connected to personal experience or values — even if casual or emotional.
        - "weak" → vague, generic, or unclear — only if it lacks relevance or effort.

        Respond with:
        - strong
        - weak
        Only one word.
    """

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
            {"role": "assistant", "content": user_response}
        ]
        response = ollama_chat(model="llama3", messages=messages)
        result = response["message"]["content"].strip().lower()
        return result if result in ["strong", "weak"] else "strong"
    except Exception as e:
        print(f"[ERROR] assess_followup_response failed: {e}")
        return "strong"



def generate_dynamic_question(job_title, job_description, conversation_history):
    log("generate_dynamic_question")
    messages = [
        {
            "role": "system",
            "content": f"""
            You are an AI interviewer conducting an interview for the role of: {job_title}.

            Job Description:
            {job_description}

            Your goal is to ask a relevant follow-up question to learn more about the candidate’s background, experience, or motivation.

            Use the conversation below to avoid repeating anything and ask something that hasn’t been discussed yet.
            Make the question sound human, natural, and concise — no more than one sentence.
            Avoid asking about technical skills (those come later).

            Only return the question — no explanations, no labels, no intro.
            """
        },
        *conversation_history
    ]

    try:
        response = ollama_chat(model="llama3", messages=messages)
        return response['message']['content'].strip()

    except Exception as e:
        print(f"[ERROR] generate_dynamic_question failed: {e}")
        return "Can you tell me more about your motivation for applying to this role?"


# ===== END OF - INTRO FOLLOW-UP FUNCTIONS USED =====


# ===== BEGGINING OF - RESUME DISCUSSION FUNCTIONS USED =====

def evaluate_resume_response(question, response):
    log("evaluate_resume_response")
    prompt = f"""
    You are an AI interviewer evaluating a candidate's response.

    Question: "{question}"
    Answer: "{response}"

    Label it:
    - strong
    - weak
    - confused
    - off_topic

    Only one word response.
    """
    try:
        res = ollama_chat(model="llama3", messages=[{"role": "system", "content": prompt}])
        return res["message"]["content"].strip().lower()

    except Exception as e:
        print(f"[ERROR] evaluate_resume_response failed: {e}")
        return "confused"

def generate_followup_question(original_question, weak_response):
    log("generate_followup_question")
    prompt = f"""
    You're an AI interviewer. The candidate gave a vague response.

    Original Q: "{original_question}"
    Weak Response: "{weak_response}"

    Generate a polite, specific follow-up question to clarify.
    Only return the follow-up question.
    """
    try:
        res = ollama_chat(model="llama3", messages=[{"role": "system", "content": prompt}])
        content = res["message"]["content"].strip()
        # Remove quotes from beginning and end if present
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        return content

    except:
        return "Could you elaborate a bit more on that?"

# ===== END OF - RESUME DISCUSSION FUNCTIONS USED =====

# ===== BEGINING OF - FUCNTIONS USED FOR CUSTOM QUESTIONS ====== 

def evaluate_custom_response(question, response):
    log("evaluate_custom_response")
    prompt = f"""
    You are an AI interviewer evaluating a candidate's response to a custom technical or behavioral question.

    Question: "{question}"
    Response: "{response}"

    Classify the response using only ONE of the following:

    - "clear" → well-explained, confident, relevant
    - "weak" → relevant but vague or lacking detail
    - "confused" → seems to misunderstand the question
    - "no_answer" → says "I don't know", "not sure", etc.
    - "off_topic" → unrelated, joke, or trolling

    Only return one word.
    """
    try:
        result = ollama_chat(model="llama3", messages=[{"role": "system", "content": prompt}])
        return result["message"]["content"].strip().lower()

    except Exception as e:
        print(f"[ERROR] evaluate_custom_response failed: {e}")
        return "confused"

def generate_custom_followup(question, last_response):
    log("generate_custom_followup")
    prompt = f"""
    You are an AI interviewer.

    The candidate was asked:
    "{question}"

    Their last response was:
    "{last_response}"

    Write a short follow-up question to go deeper or clarify.
    Focus on understanding the candidate's conceptual grasp of the topic.
    Just return the follow-up question only.
    """
    try:
        result = ollama_chat(model="llama3", messages=[{"role": "system", "content": prompt}])
        content = result["message"]["content"].strip()
        # Remove quotes from beginning and end if present
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        return content

    except Exception:
        return "Could you clarify your thinking or give an example?"

def generate_model_answer(question):
    log("generate_model_answer")
    prompt = f"""
        You are an AI interviewer.

        The candidate struggled to answer:
        "{question}"

        Give a **short** model answer in 2–3 concise sentences:
        - Clearly explain the key concept.
        - If helpful, include a quick example.
        - End with "That's how you could approach it."

        Keep it crisp and under 50 words.
        Only return the answer — no explanation or extra text.
        """
    try:
        result = ollama_chat(model="llama3", messages=[{"role": "system", "content": prompt}])
        content = result["message"]["content"].strip()
        # Remove quotes from beginning and end if present
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]
        return content

    except Exception as e:
        print(f"[ERROR] generate_model_answer failed: {e}")
        return "Tuples are immutable; lists are not. Use tuples when values shouldn't change. That's how you could approach it."

# ===== END OF - FUCNTIONS USED FOR CUSTOM QUESTIONS ====== 

# ===== BEGINING OF - FUCNTIONS USED FOR END OF INTERVIEW CANDIDATE QUESTION====== 

def assess_candidate_has_question(user_input):
    log("assess_candidate_has_question")
    prompt = f"""
    You are an AI interviewer wrapping up an interview.

    The candidate was asked: "Do you have any questions before we wrap up?"

    Their response was:
    "{user_input}"

    Decide if they **want to ask something**.

    Respond with:
    - "yes" → if it sounds like a question or shows interest
    - "no" → if it clearly indicates no question or they're done

    Accept phrases like “no”, “not really”, “I'm good”, etc. as "no". Anything question-like = "yes".
    """
    try:
        result = ollama_chat(model="llama3", messages=[{"role": "system", "content": prompt}])
        return result["message"]["content"].strip().lower()

    except Exception as e:
        print(f"[ERROR] assess_candidate_has_question failed: {e}")
        return "no"

def generate_candidate_qna_response(user_question, conversation_history, evaluation_log, job_title, last_chance=False):
    log("generate_candidate_qna_response")
    prompt = f"""
    You are an AI interviewer wrapping up an interview for the role of **{job_title}**.

    Here’s the candidate’s latest message:
    "{user_question}"

    Conversation so far:
    {json.dumps(conversation_history, indent=2)}

    Candidate's performance log:
    {json.dumps(evaluation_log, indent=2)}

    Instructions:
    1. If they ask about next steps, company, or job → answer helpfully.
    2. If they ask for feedback (e.g., “how did I do?”) → give **brief, constructive** feedback without sounding harsh.
    3. If they ask about YOU or try to reverse-interview → politely deflect and return to your role as interviewer.
    4. If the message is vague (“yes”, “I have one”) → say “Sure, go ahead” or “What’s on your mind?”
    5. If the question is clearly off-topic or not appropriate for a job interview setting,
        politely deflect. This includes:
        - Trivia or definitions (e.g., “What is a tuple?”, “What is a black hole?”)
        - Personal questions directed at you as the interviewer
        - General knowledge or unrelated educational topics
        - Attempts to reverse-interview you

        Respond with one of the following:
        - “Let’s stay focused on the interview — happy to address role-related questions.”
        - “That’s a good topic for another time — let’s keep this relevant to the role today.”
        - “I’d love to keep this focused on your fit for the position, if that’s alright.”


    Tone:
    - Keep your response brief (2–3 sentences max).
    - Be professional, kind, and neutral.
    - Avoid scoring, long lectures, or phrases like “great question” or “thanks for asking.”
    - Never make the candidate feel embarrassed or criticized.
    - Only return the reply — no formatting or labels.
    """


    if last_chance:
        prompt += """
    Important: This may be the candidate's **last question**.
    If the question is valid, end your reply with a warm closing line like:
    “This is probably a good place to wrap up — thanks for your thoughtful questions.”

    But only add that if it makes sense — don’t force it on vague or unclear inputs.
    """

    prompt += """
    Tone:
    - Stay professional, clear, and human-like.
    - Be brief: no more than 3 sentences.
    - Avoid phrases like “great question” or “thanks for asking.”
    - Never act like you’re the one being interviewed.
    - Only return your reply — no formatting, tags, or explanations.
    """


    try:
        result = ollama_chat(model="llama3", messages=[{"role": "system", "content": prompt}])
        return result["message"]["content"].strip()

    except Exception as e:
        print(f"[ERROR] generate_candidate_qna_response failed: {e}")
        return "Please go ahead — I'm happy to answer."



# ===== END OF - FUCNTIONS USED FOR END OF INTERVIEW CANDIDATE QUESTION====== 

# ===== BEGINING OF - FUCNTIONS USED FOR EVALUATING CANDIDATE QUESTION====== 

def analyze_individual_responses(evaluation_log, model="llama3"):
    log("analyze_individual_responses")
    analyzed = []

    for item in evaluation_log:
        q = item["question"]
        a = item["response"]

        prompt = f"""
            Evaluate the following interview response:

            Question: "{q}"
            Candidate's Answer: "{a}"

            Provide detailed evaluation metrics in JSON format.
            For each metric, give a numeric score from 0 to 10, plus an emotion label.

            Metrics to include:
            1. knowledge_depth – understanding of the question
            2. communication_clarity – organization and flow of ideas
            3. confidence_tone – tone of communication (e.g., confident, nervous, neutral)
            4. reasoning_ability – logical reasoning or problem-solving shown
            5. relevance_to_question – how well it stays on-topic
            6. motivation_indicator – enthusiasm, passion, or drive reflected in response

            Respond ONLY in valid JSON:
            {{
            "knowledge_depth": 0–10,
            "communication_clarity": 0–10,
            "confidence_tone": 0–10,
            "reasoning_ability": 0–10,
            "relevance_to_question": 0–10,
            "motivation_indicator": 0–10,
            "emotion": "label"
            }}
            """

        try:
            result = ollama_chat(model=model, messages=[{"role": "system", "content": prompt}])
            response_text = result["message"]["content"].strip()
            
            # Try to extract JSON from the response
            try:
                # First, try to parse the whole response
                parsed = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from the response
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start != -1 and json_end != 0:
                    json_text = response_text[json_start:json_end]
                    parsed = json.loads(json_text)
                else:
                    # If no JSON found, use default values
                    raise Exception("No JSON found in response")
            
            item["knowledge_depth"] = parsed.get("knowledge_depth", 5)
            item["communication_clarity"] = parsed.get("communication_clarity", 5)
            item["confidence_tone"] = parsed.get("confidence_tone", 5)
            item["reasoning_ability"] = parsed.get("reasoning_ability", 5)
            item["relevance_to_question"] = parsed.get("relevance_to_question", 5)
            item["motivation_indicator"] = parsed.get("motivation_indicator", 5)
            item["emotion"] = parsed.get("emotion", "neutral")

            
        except Exception as e:
            print(f"[ERROR] analyze_individual_responses failed for question '{q[:50]}...': {e}")
            print(f"[DEBUG] Response text: {response_text if 'response_text' in locals() else 'No response'}")

            # Assign safe default values so JSON parsing errors don't break the flow
            item["knowledge_depth"] = 5
            item["communication_clarity"] = 5
            item["confidence_tone"] = 5
            item["reasoning_ability"] = 5
            item["relevance_to_question"] = 5
            item["motivation_indicator"] = 5
            item["emotion"] = "unknown"
            item["overall_score"] = 5.0  # Optional overall average placeholder


        analyzed.append(item)

    return analyzed


def generate_final_summary_review(job_title, conversation_history, analyzed_log, model="llama3"):
    log("generate_final_summary_review")

    def build_deterministic_fallback():
        overall_rating = round(avg_overall_rating, 1)
        if overall_rating >= 7.5:
            final_label = "strong"
        elif overall_rating >= 5.5:
            final_label = "average"
        else:
            final_label = "weak"

        summary_parts = [
            f"The candidate showed {final_label} overall alignment for the {job_title} role.",
            f"Overall performance averaged {overall_rating:.1f}/10, with knowledge depth at {avg_knowledge_depth:.1f}/10 and communication clarity at {avg_communication_clarity:.1f}/10.",
            f"The dominant emotional tone was {overall_emotion}, with reasoning ability at {avg_reasoning_ability:.1f}/10 and relevance at {avg_relevance_to_question:.1f}/10.",
        ]
        if strong_responses:
            summary_parts.append(f"There were {strong_responses} stronger responses that showed useful baseline capability.")
        if weak_responses:
            summary_parts.append(f"There were {weak_responses} weaker responses where the candidate needed more depth or specificity.")
        summary = " ".join(summary_parts).strip()
        if not summary.endswith(final_label):
            summary = f"{summary} {final_label}"

        strengths = []
        if avg_knowledge_depth >= 6:
            strengths.append("Demonstrated workable baseline knowledge for several interview topics.")
        if avg_communication_clarity >= 6:
            strengths.append("Communicated ideas with reasonable clarity in parts of the interview.")
        if avg_relevance_to_question >= 6:
            strengths.append("Stayed relevant to the questions and generally addressed the intent of prompts.")
        if avg_motivation_indicator >= 6:
            strengths.append("Showed signs of motivation and interest in the role.")
        if not strengths:
            strengths.append("Completed the interview flow and provided enough responses for a baseline evaluation.")
            strengths.append("Showed willingness to engage with the interview process.")

        improvements = []
        if avg_knowledge_depth < 6:
            improvements.append("Improve technical depth by preparing clearer examples, concepts, and project details.")
        if avg_communication_clarity < 6:
            improvements.append("Use more structured answers with context, action, and outcome to improve clarity.")
        if avg_confidence_tone < 6 or nervous_responses > 0 or unsure_responses > 0:
            improvements.append("Practice delivery and mock interviews to improve confidence and reduce hesitation.")
        if avg_reasoning_ability < 6:
            improvements.append("Explain the reasoning behind decisions more explicitly instead of giving short conclusions.")
        if avg_relevance_to_question < 6:
            improvements.append("Answer the exact question first, then support it with a concrete example.")
        if not improvements:
            improvements.append("Continue sharpening role-specific examples to make strong answers more consistent.")

        return {
            "summary": f"{summary} (Overall Rating: {overall_rating:.1f}/10)",
            "key_strengths": "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(strengths[:8])),
            "improvement_areas": "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(improvements[:8])),
            "overall_rating": overall_rating,
            "metrics": {
                "overall_rating": overall_rating,
                "knowledge_depth": round(avg_knowledge_depth, 1),
                "communication_clarity": round(avg_communication_clarity, 1),
                "confidence_tone": round(avg_confidence_tone, 1),
                "reasoning_ability": round(avg_reasoning_ability, 1),
                "relevance_to_question": round(avg_relevance_to_question, 1),
                "motivation_indicator": round(avg_motivation_indicator, 1),
                "overall_emotion": overall_emotion,
                "overall_emotion_summary": f"The candidate's overall tone was {overall_emotion}.",
            }
        }


    # Calculate overall statistics for context using new detailed metrics
    total_responses = len(analyzed_log)
    if total_responses > 0:
        avg_knowledge_depth = sum(item.get('knowledge_depth', 5) for item in analyzed_log) / total_responses
        avg_communication_clarity = sum(item.get('communication_clarity', 5) for item in analyzed_log) / total_responses
        avg_confidence_tone = sum(item.get('confidence_tone', 5) for item in analyzed_log) / total_responses
        avg_reasoning_ability = sum(item.get('reasoning_ability', 5) for item in analyzed_log) / total_responses
        avg_relevance_to_question = sum(item.get('relevance_to_question', 5) for item in analyzed_log) / total_responses
        avg_motivation_indicator = sum(item.get('motivation_indicator', 5) for item in analyzed_log) / total_responses
        avg_overall_rating = (
            avg_knowledge_depth +
            avg_communication_clarity +
            avg_confidence_tone +
            avg_reasoning_ability +
            avg_relevance_to_question +
            avg_motivation_indicator
        ) / 6

        weak_responses = sum(1 for item in analyzed_log if item.get('evaluation') in ['weak', 'confused'])
        strong_responses = sum(1 for item in analyzed_log if item.get('evaluation') in ['strong', 'good'])
        nervous_responses = sum(1 for item in analyzed_log if item.get('emotion') == 'nervous')
        unsure_responses = sum(1 for item in analyzed_log if item.get('emotion') == 'unsure')
        # === Derive overall emotion across all responses ===
        emotion_counts = {}
        for item in analyzed_log:
            emotion = item.get("emotion", "neutral").lower()
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        # Pick the most frequent emotion
        overall_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"

    else:
        avg_knowledge_depth = avg_communication_clarity = avg_confidence_tone = 5
        avg_reasoning_ability = avg_relevance_to_question = avg_motivation_indicator = 5
        avg_overall_rating = 5
        weak_responses = strong_responses = nervous_responses = unsure_responses = 0
        overall_emotion = "neutral"  # ✅ ADD THIS LINE - Initialize overall_emotion for empty log case


    prompt = f"""
    You are an expert interview evaluator. Based on the following interaction, provide a comprehensive evaluation:

    Job Title: {job_title}

    Here is the full conversation:
    {json.dumps(conversation_history, indent=2)}

    And here is the evaluated log:
    {json.dumps(analyzed_log, indent=2)}

    EVALUATION STATISTICS:
    - Total Responses: {total_responses}
    - Overall Dominant Emotion: {overall_emotion.capitalize()}
    - Avg Knowledge Depth: {avg_knowledge_depth:.1f}/10
    - Avg Communication Clarity: {avg_communication_clarity:.1f}/10
    - Avg Confidence & Tone: {avg_confidence_tone:.1f}/10
    - Avg Reasoning Ability: {avg_reasoning_ability:.1f}/10
    - Avg Relevance to Question: {avg_relevance_to_question:.1f}/10
    - Avg Motivation Indicator: {avg_motivation_indicator:.1f}/10
    - Weak Responses: {weak_responses}
    - Strong Responses: {strong_responses}
    - Nervous Responses: {nervous_responses}
    - Unsure Responses: {unsure_responses}

    
    Please provide a comprehensive evaluation in JSON format with four sections:

    1. SUMMARY: Write a short 4–5 sentence summary evaluating the candidate's overall fit for this job. 
    - Consider knowledge and clarity across questions
    - Consider emotional tone (confidence, nervousness, etc.)
    - Consider communication effectiveness
    - The summary **must explicitly end with one of these exact words, in lowercase: "strong", "average", or "weak". 
        This is mandatory, as it will be programmatically extracted.**


    2. KEY STRENGTHS: List 6–8 **specific, evidence-based strengths** the candidate demonstrated. 
        - Only include strengths if they are clearly supported by the evaluation log 
            (e.g., knowledge rating ≥ 6/10, "strong" responses, confident/enthusiastic tone, or concrete examples mentioned). 
        - Where possible, link the strength to how it can be leveraged to improve weaker areas 
            (e.g., “Strong communication in casual answers — could apply this clarity to technical explanations”). 
        - If no strong evidence exists, explicitly state: 
            "No significant strengths were demonstrated due to vague or non-specific responses."
        - Avoid generic filler like "professional demeanor" unless clearly evident.

    3. IMPROVEMENT AREAS: List 6–8 **concrete, actionable improvement areas**. 
        - Tie each point directly to weaknesses in the evaluation log 
            (e.g., ratings < 5/10, multiple "weak/confused" responses, nervous/unsure emotional tone). 
        - Provide specific guidance on how to improve (e.g., “Instead of one-word answers, provide examples of projects to show depth”). 
        - If performance was consistently weak, you may state: 
            "The candidate should significantly improve technical depth, communication clarity, and confidence before reapplying."

    4. OVERALL EMOTION SUMMARY – a **one-sentence description** of the candidate’s overall emotional tone throughout the interview.  
        Example: "Started nervous but became confident by the end" or "Consistently calm and professional."  
        Return this line in the JSON as **"overall_emotion_summary"**.

    Return your response strictly as a single valid JSON object, with no text, comments, or explanations before or after it. 

    JSON format:
    {{
        "summary": "2–3 sentence summary here",
        "key_strengths": "1. [Specific strength 1]\\n2. [Specific strength 2]\\n3. [Specific strength 3]",
        "improvement_areas": "1. [Specific area 1]\\n2. [Specific area 2]\\n3. [Specific area 3]",
        "overall_rating": {avg_overall_rating:.1f},
        "overall_emotion_summary": "Short sentence describing emotional tone, e.g., 'Started nervous but became confident by the end.'"
    }}

    Be specific, constructive, and relevant to the {job_title} position. Base your analysis on the actual conversation and evaluation data provided.
    """

    parsed_response = {
        "summary": "Interview completed. Detailed AI summary was unavailable, so a fallback summary was generated.",
        "key_strengths": "1. Completed the interview flow and answered multiple questions.\n2. Provided enough conversation data for a baseline evaluation.",
        "improvement_areas": "1. Improve depth and specificity in answers.\n2. Practice confidence, clarity, and structured examples before the next interview.",
        "overall_rating": avg_overall_rating,
        "overall_emotion_summary": "Emotion summary not generated",
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = ollama_chat(model=model, messages=[{"role": "system", "content": prompt}])
            response_text = result["message"]["content"].strip()

            # Try to extract JSON
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                json_text = response_text[json_start:json_end]
                json_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_text)
                parsed_response = json.loads(json_text)
            else:
                parsed_response = json.loads(response_text)

            # ✅ Success → return with rating in summary
            parsed_rating = parsed_response.get('overall_rating', avg_overall_rating)
            try:
                parsed_rating = float(parsed_rating)
            except Exception:
                parsed_rating = avg_overall_rating
            return {
                'summary': parsed_response.get('summary', '') + f" (Overall Rating: {parsed_rating:.1f}/10)",
                'key_strengths': parsed_response.get('key_strengths', ''),
                'improvement_areas': parsed_response.get('improvement_areas', ''),
                'overall_rating': parsed_rating,
                'metrics': {
                    "overall_rating": round(parsed_rating, 1),
                    "knowledge_depth": round(avg_knowledge_depth, 1),
                    "communication_clarity": round(avg_communication_clarity, 1),
                    "confidence_tone": round(avg_confidence_tone, 1),
                    "reasoning_ability": round(avg_reasoning_ability, 1),
                    "relevance_to_question": round(avg_relevance_to_question, 1),
                    "motivation_indicator": round(avg_motivation_indicator, 1),
                    "overall_emotion": overall_emotion,
                    "overall_emotion_summary": parsed_response.get("overall_emotion_summary", "Emotion summary not generated")
                }
            }

        except Exception as e:
            print(f"[WARN] Attempt {attempt+1}/{max_retries} failed: {e}")
            if "Failed to connect to Ollama" in str(e):
                return build_deterministic_fallback()
            if attempt < max_retries - 1:
                continue  # 🔁 retry again
            else:
                print("[ERROR] All retries failed")

    # === Fallback if all retries fail ===
    return build_deterministic_fallback()
