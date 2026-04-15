import os
import sys
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
import ollama
import numpy as np
import re

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def fetch_interview_metrics_from_edge_function(auth_token: str, limit: int = 100):
    """
    Fetch interview feedback with metrics from the Supabase edge function.
    Returns interviews ordered chronologically (oldest first).
    
    Args:
        auth_token: User's authentication token (Bearer token)
        limit: Maximum number of interviews to fetch
    
    Returns:
        List of interview feedback objects with metrics, or None if error
    """
    try:
        edge_function_url = f"{SUPABASE_URL}/functions/v1/interview-feedback"
        
        # Query parameters for chronological order
        params = {
            'limit': limit,
            'offset': 0,
            'sort_by': 'interviews.created_at',
            'sort_order': 'asc'  # Oldest first (chronological)
        }
        
        headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json',
            'apikey': SUPABASE_ANON_KEY
        }
        
        print(f"[INFO] Fetching interview metrics from edge function...")
        response = requests.get(edge_function_url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"[ERROR] Edge function returned status {response.status_code}: {response.text}")
            return None
        
        data = response.json()
        
        if not data.get('success'):
            print(f"[ERROR] Edge function returned error: {data.get('error', 'Unknown error')}")
            return None
        
        feedbacks = data.get('data', [])
        
        # Filter to only include feedbacks with metrics
        feedbacks_with_metrics = [
            fb for fb in feedbacks 
            if fb.get('metrics') is not None
        ]
        
        print(f"[INFO] Found {len(feedbacks_with_metrics)} interviews with metrics out of {len(feedbacks)} total")
        
        return feedbacks_with_metrics
    
    except Exception as e:
        print(f"[ERROR] Failed to fetch interview metrics: {e}")
        import traceback
        traceback.print_exc()
        return None


def compute_overall_score(metrics):
    """
    Calculate overall performance score from metrics.
    Returns average of all 6 numeric metrics.
    """
    return round((
        metrics.get('knowledge_depth', 0) +
        metrics.get('communication_clarity', 0) +
        metrics.get('confidence_tone', 0) +
        metrics.get('reasoning_ability', 0) +
        metrics.get('relevance_to_question', 0) +
        metrics.get('motivation_indicator', 0)
    ) / 6, 2)


def compute_trend_from_all_scores(scores):
    """
    Compute trend using linear regression across all scores.
    Returns the slope of the trend line.
    Positive slope = improving, Negative = declining, Near zero = stable
    """
    if len(scores) < 2:
        return 0.0
    
    x = np.arange(len(scores))
    y = np.array(scores, dtype=float)
    
    # Calculate linear regression slope
    slope = np.polyfit(x, y, 1)[0]
    
    return slope


def calculate_trend_shape(scores):
    """
    Determine the visual shape of the trend (e.g., "down-then-up", "up-then-down", "steady-up")
    Returns a string describing the trend pattern.
    """
    if len(scores) < 2:
        return "insufficient-data"
    
    if len(scores) == 2:
        if scores[1] > scores[0] + 0.1:
            return "up"
        elif scores[1] < scores[0] - 0.1:
            return "down"
        else:
            return "steady"
    
    # For 3+ scores, analyze pattern using thirds
    first_third = max(1, len(scores) // 3)
    second_third = max(first_third + 1, (len(scores) * 2) // 3)
    
    first_avg = np.mean(scores[:first_third])
    mid_avg = np.mean(scores[first_third:second_third])
    last_avg = np.mean(scores[second_third:])
    
    # Determine pattern
    if first_avg > mid_avg + 0.1 and last_avg > mid_avg + 0.1:
        return "down-then-up"
    elif first_avg < mid_avg - 0.1 and last_avg < mid_avg - 0.1:
        return "up-then-down"
    elif last_avg > first_avg + 0.1:
        return "steady-up"
    elif last_avg < first_avg - 0.1:
        return "steady-down"
    else:
        return "fluctuating"


def calculate_volatility(scores):
    """
    Calculate volatility (standard deviation) of scores.
    Returns volatility level: "low", "medium", "high"
    """
    if len(scores) < 2:
        return "low"
    
    std_dev = np.std(scores)
    mean_score = np.mean(scores)
    
    # Normalize by mean to get coefficient of variation
    cv = (std_dev / mean_score) * 100 if mean_score > 0 else 0
    
    if cv < 10:
        return "low"
    elif cv < 25:
        return "medium"
    else:
        return "high"


def calculate_consistency(scores):
    """
    Calculate consistency level based on score variance.
    Returns: "low", "medium", "high"
    """
    if len(scores) < 2:
        return "low"
    
    std_dev = np.std(scores)
    mean_score = np.mean(scores)
    
    cv = (std_dev / mean_score) * 100 if mean_score > 0 else 0
    
    if cv < 10:
        return "high"
    elif cv < 25:
        return "medium"
    else:
        return "low"


def calculate_regression_trend(slope, threshold=0.05):
    """
    Determine regression trend from slope.
    Returns: "improving", "declining", "stable"
    """
    if slope > threshold:
        return "improving"
    elif slope < -threshold:
        return "declining"
    else:
        return "stable"


def calculate_numeric_summary(feedbacks):
    """
    Calculate ALL numeric metrics deterministically.
    This is the numeric engine that computes everything.
    
    Returns:
        Dictionary with all computed numeric results
    """
    if not feedbacks or len(feedbacks) < 2:
        return None
    
    # Extract all metric values over time
    metrics_list = ['knowledge_depth', 'communication_clarity', 'confidence_tone', 
                   'reasoning_ability', 'relevance_to_question', 'motivation_indicator']
    
    all_metrics = {metric: [] for metric in metrics_list}
    overall_scores = []
    timeline_scores = []
    emotions = []
    
    for feedback in feedbacks:
        metrics = feedback.get('metrics', {})
        if metrics:
            # Calculate overall score for this interview
            overall_score = compute_overall_score(metrics)
            overall_scores.append(overall_score)
            
            # Collect individual metric values
            for metric in metrics_list:
                val = metrics.get(metric)
                if isinstance(val, (int, float)):
                    all_metrics[metric].append(val)
                else:
                    all_metrics[metric].append(0)
            
            # Collect timeline data
            timeline_scores.append({
                'interview_number': len(overall_scores),
                'score': overall_score,
                'emotion': metrics.get('overall_emotion', 'neutral')
            })
            
            emotions.append(metrics.get('overall_emotion', 'neutral'))
    
    if not overall_scores:
        return None
    
    # === OVERALL TREND CALCULATIONS ===
    
    # Calculate regression slope for overall scores
    overall_slope = compute_trend_from_all_scores(overall_scores)
    regression_trend = calculate_regression_trend(overall_slope)
    
    # Calculate percent change (first half vs second half)
    mid_point = len(overall_scores) // 2
    first_half_avg = np.mean(overall_scores[:mid_point]) if mid_point > 0 else overall_scores[0]
    second_half_avg = np.mean(overall_scores[mid_point:]) if mid_point < len(overall_scores) else overall_scores[-1]
    percent_change = round(((second_half_avg - first_half_avg) / first_half_avg) * 100, 2) if first_half_avg > 0 else 0.0
    
    # Calculate mean score
    mean_score = round(np.mean(overall_scores), 2)
    
    # Calculate volatility
    volatility = calculate_volatility(overall_scores)
    
    # Calculate trend shape
    trend_shape = calculate_trend_shape(overall_scores)
    
    # Calculate consistency
    consistency = calculate_consistency(overall_scores)
    
    # Get latest emotion
    latest_emotion = emotions[-1] if emotions else "neutral"
    
    # === METRIC-WISE CALCULATIONS ===
    
    metric_progress = {}
    metric_slopes = {}
    
    for metric in metrics_list:
        metric_values = all_metrics[metric]
        
        if len(metric_values) >= 2:
            # Calculate regression slope for this metric
            metric_slope = compute_trend_from_all_scores(metric_values)
            metric_slopes[metric] = metric_slope
            
            # Calculate first half vs second half
            mid_point = len(metric_values) // 2
            first_half_avg = np.mean(metric_values[:mid_point]) if mid_point > 0 else metric_values[0]
            second_half_avg = np.mean(metric_values[mid_point:]) if mid_point < len(metric_values) else metric_values[-1]
            
            # Calculate volatility for this metric
            metric_vol = calculate_volatility(metric_values)
            
            # Determine trend
            metric_trend = calculate_regression_trend(metric_slope)
            
            metric_progress[metric] = {
                "average_first_half": round(first_half_avg, 2),
                "average_second_half": round(second_half_avg, 2),
                "regression_trend": metric_trend,
                "volatility": metric_vol,
                "mean_score": round(np.mean(metric_values), 2),
                "slope": round(metric_slope, 4)
            }
        else:
            # Single value or no data
            if len(metric_values) == 1:
                metric_progress[metric] = {
                    "average_first_half": round(metric_values[0], 2),
                    "average_second_half": round(metric_values[0], 2),
                    "regression_trend": "stable",
                    "volatility": "low",
                    "mean_score": round(metric_values[0], 2),
                    "slope": 0.0
                }
                metric_slopes[metric] = 0.0
    
    # === FIND BEST AND WEAKEST METRICS ===
    
    # Best improved metric = highest positive slope
    best_metric = None
    if metric_slopes:
        # Filter to only improving metrics (positive slope)
        improving_metrics = {k: v for k, v in metric_slopes.items() if v > 0.05}
        if improving_metrics:
            best_metric = max(improving_metrics, key=improving_metrics.get)
        else:
            # If no improving metrics, find the least declining
            best_metric = max(metric_slopes, key=metric_slopes.get)
    
    # Weakest metric = lowest slope (most declining)
    weakest_metric = None
    if metric_slopes:
        weakest_metric = min(metric_slopes, key=metric_slopes.get)
    
    # Recommended focus = weakest metric
    recommended_focus = weakest_metric
    
    # === BUILD NUMERIC SUMMARY DICTIONARY ===
    
    numeric_summary = {
        "regression_trend": regression_trend,
        "percent_change": percent_change,
        "trend_shape": trend_shape,
        "consistency": consistency,
        "volatility": volatility,
        "mean_score": mean_score,
        "best_metric": best_metric,
        "weakest_metric": weakest_metric,
        "recommended_focus": recommended_focus,
        "metric_progress": metric_progress,
        "timeline_scores": timeline_scores,
        "latest_emotion": latest_emotion,
        "total_interviews": len(feedbacks)
    }
    
    return numeric_summary


def analyze_performance_with_llm(numeric_summary, model="llama3"):
    """
    Use LLM to generate natural language explanations based on numeric results.
    The LLM MUST NOT infer, guess, or decide any numeric values or trends.
    It ONLY generates explanations based on the provided numeric_summary.
    
    Args:
        numeric_summary: Dictionary with all computed numeric results
        model: Ollama model to use
    
    Returns:
        Dictionary with LLM-generated natural language explanations
    """
    if not numeric_summary:
        return {
            'success': False,
            'error': 'No numeric summary provided'
        }
    
    # ✅ Create a cleaned version for LLM (exclude timeline_scores - not needed for analysis)
    # timeline_scores is only used for frontend display, not for LLM analysis
    numeric_summary_for_llm = {
        "regression_trend": numeric_summary.get("regression_trend"),
        "percent_change": numeric_summary.get("percent_change"),
        "trend_shape": numeric_summary.get("trend_shape"),
        "consistency": numeric_summary.get("consistency"),
        "volatility": numeric_summary.get("volatility"),
        "mean_score": numeric_summary.get("mean_score"),
        "best_metric": numeric_summary.get("best_metric"),
        "weakest_metric": numeric_summary.get("weakest_metric"),
        "recommended_focus": numeric_summary.get("recommended_focus"),
        "metric_progress": numeric_summary.get("metric_progress"),
        "latest_emotion": numeric_summary.get("latest_emotion"),
        "total_interviews": numeric_summary.get("total_interviews")
        # ✅ Excluded: "timeline_scores" - not needed for LLM, only for frontend
    }
    
    # ⭐ NEW PRODUCTION-GRADE PROMPT
    prompt = f"""
You are an expert interview performance coach.

You will receive a dictionary called NUMERIC_RESULTS containing all performance metrics computed by a deterministic engine. These values ARE FINAL and MUST NOT be changed, reinterpreted, guessed, or contradicted.

Your job is ONLY to transform these numeric results into clear, actionable, accurate written feedback, without inventing any additional data.

====================================
NUMERIC_RESULTS (DO NOT MODIFY THEM)
====================================

{json.dumps(numeric_summary_for_llm, indent=2)}

====================================
YOUR GUARANTEES (STRICT RULES)
====================================

1. You MUST NOT invent:
   - behaviors
   - personality traits
   - emotions beyond latest_emotion
   - reasons for improvement/decline
   - interview content
   - context not provided

2. You MUST NOT contradict any numeric value.

3. Every explanation MUST be tied DIRECTLY to:
   - regression_trend
   - percent_change
   - metric slopes
   - first/second half averages
   - mean_score
   - volatility
   - recommended_focus
   - individual metric progress

4. All feedback MUST stay within the numeric bounds.

5. Format MUST be valid JSON only.

====================================
OUTPUT FORMAT (STRICT JSON)
====================================

You MUST return ONLY this JSON object:

{{
  "summary": "",
  "key_strengths": [],
  "key_weaknesses": [],
  "detailed_metric_feedback": {{}},
  "action_plan": [],
  "confidence_level": "low" | "medium" | "high"
}}

====================================
FIELD-BY-FIELD OUTPUT RULES
====================================

1. SUMMARY (3–4 sentences)
   MUST include:
   - regression_trend (e.g., declining / improving / stable)
   - percent_change
   - mean_score
   - trend_shape (steady-down, steady-up, fluctuating, etc.)
   - total_interviews

   MUST NOT:
   - infer reasons
   - mention "maybe", "possibly", or guesses
   - invent behavior

   The tone should be neutral, factual, and helpful.

2. KEY_STRENGTHS
   Include ONLY metrics where:
   - metric_progress[metric]["regression_trend"] == "improving"
   OR
   - metric == best_metric
   BUT only if slope is >= 0 (no declining "strengths")

   If there are NO improving metrics:
   → return an empty list.

   Each strength must be a short 1-line factual statement.

3. KEY_WEAKNESSES
   Include ONLY:
   - weakest_metric
   - metrics where regression_trend == "declining"

   Each weakness MUST:
   - Use exact numeric values to explain the decline
   - Reference slope, first_half_avg → second_half_avg, etc.

4. DETAILED_METRIC_FEEDBACK (MOST IMPORTANT SECTION)
   MUST be a dictionary keyed by metric name.

   For EACH metric in metric_progress:
   {{
     "status": "improving" | "declining" | "stable",
     "numeric_summary": "First half avg: X → Second half avg: Y | Slope: Z",
     "interpretation": "What this numeric trend indicates (without guessing behavior)",
     "actionable_steps": [
         "Step 1 based on numeric decline or improvement",
         "Step 2",
         "Step 3"
     ]
   }}

   Interpretation MUST be based ONLY on:
   - How much it dropped/increased
   - Slope steepness
   - Volatility
   - Mean score

   Actionable steps MUST be:
   - universal interview preparation advice
   - NOT tied to assumed behaviors
   - NOT inventing external context
   - should feel like a real coach giving skill-specific help

   EXAMPLE OF VALID COACHING (OK):
   "Structure your answers using STAR to improve clarity."
   "Add 1–2 supporting examples to deepen knowledge answers."

   INVALID (NOT OK):
   "You hesitated a lot" (behavior guess)
   "You were nervous" (not in numeric data)
   "You didn't think clearly" (inference)

5. ACTION_PLAN
   MUST contain 3–5 high-priority steps derived ONLY from:
   - recommended_focus metric
   - biggest numeric declines
   - lowest mean scores

   Each step must be actionable and metric-specific.

6. CONFIDENCE_LEVEL
   Determined ONLY by numeric volatility:
   - volatility == "low"    → "high"
   - volatility == "medium" → "medium"
   - volatility == "high"   → "low"

====================================
IMPORTANT
====================================

- NEVER mention this prompt.
- NEVER add commentary outside the JSON.
- DO NOT say "based on the data above".
- DO NOT justify your reasoning.
- ONLY output the JSON object.
- DO NOT use "..." or ellipsis in the JSON - include all fields completely.
"""
    
    # ✅ RETRY LOOP: Keep trying until we get valid JSON
    max_attempts = 1000  # Set a reasonable upper limit to prevent infinite loops
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        try:
            print(f"[INFO] Using {model} to convert numeric results into readable text... (Attempt {attempt})")
            response = ollama.chat(model=model, messages=[{"role": "system", "content": prompt}])
            response_text = response["message"]["content"].strip()
            
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end != 0:
                json_text = response_text[json_start:json_end]
                
                # ✅ IMPROVED: Clean up JSON more aggressively
                # 1. Remove comments (both # comments and inline comments)
                json_text = re.sub(r'#.*?(?=\n|$)', '', json_text, flags=re.MULTILINE)  # Remove # comments
                json_text = re.sub(r'//.*?(?=\n|$)', '', json_text, flags=re.MULTILINE)  # Remove // comments
                
                # 2. Remove common LLM artifacts
                json_text = re.sub(r'"([^"]+)"\s*\([^)]*\)', r'"\1"', json_text)  # Remove (annotations)
                json_text = re.sub(r'\([^)]*\)', '', json_text)  # Remove any remaining parentheses
                
                # 3. Remove "..." or ellipsis patterns (invalid JSON)
                json_text = re.sub(r'\.\.\.', '', json_text)  # Remove ellipsis
                json_text = re.sub(r',\s*\.\.\.\s*,', ',', json_text)  # Remove ellipsis with commas
                json_text = re.sub(r',\s*\.\.\.\s*\]', ']', json_text)  # Remove ellipsis before array end
                json_text = re.sub(r',\s*\.\.\.\s*\}', '}', json_text)  # Remove ellipsis before object end
                
                # 4. Fix spacing issues
                json_text = re.sub(r'\s+', ' ', json_text)  # Normalize whitespace
                json_text = re.sub(r'"\s+"', '", "', json_text)  # Fix array spacing
                json_text = re.sub(r'"\s+\]', '"]', json_text)  # Fix array end
                json_text = re.sub(r'"\s+\}', '"}', json_text)  # Fix object end
                json_text = re.sub(r'(")\s+(")', r'\1, \2', json_text)  # Fix missing commas
                json_text = re.sub(r',\s*,', ',', json_text)  # Remove double commas
                json_text = re.sub(r'"\s{2,}\]', '"]', json_text)  # Fix array spacing
                
                # 5. Remove trailing commas before } or ]
                json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
                
                # 6. Try to parse, if it fails, try to fix common issues
                try:
                    llm_output = json.loads(json_text)
                    # ✅ SUCCESS! Break out of retry loop
                    print(f"[INFO] Successfully parsed JSON on attempt {attempt}")
                    break
                except json.JSONDecodeError as json_error:
                    print(f"[WARNING] JSON parse error on attempt {attempt}, attempting to fix: {json_error}")
                    print(f"[DEBUG] Problematic JSON section: {json_text[max(0, json_error.pos-50):json_error.pos+50]}")
                    
                    # Additional fixes for common issues
                    # Fix unclosed strings or objects
                    json_text = re.sub(r',\s*}', '}', json_text)  # Remove trailing comma before }
                    json_text = re.sub(r',\s*]', ']', json_text)  # Remove trailing comma before ]
                    
                    # Try parsing again
                    try:
                        llm_output = json.loads(json_text)
                        # ✅ SUCCESS! Break out of retry loop
                        print(f"[INFO] Successfully parsed JSON on attempt {attempt} after fixes")
                        break
                    except json.JSONDecodeError as json_error2:
                        print(f"[ERROR] Failed to parse JSON after fixes on attempt {attempt}: {json_error2}")
                        print(f"[DEBUG] Full JSON text: {json_text}")
                        # Continue to next attempt (retry)
                        continue
            else:
                # No JSON found, try parsing the whole response
                print(f"[WARNING] No JSON boundaries found on attempt {attempt}, attempting to parse full response")
                try:
                    llm_output = json.loads(response_text)
                    # ✅ SUCCESS! Break out of retry loop
                    print(f"[INFO] Successfully parsed JSON on attempt {attempt} from full response")
                    break
                except json.JSONDecodeError:
                    print(f"[WARNING] Failed to parse full response on attempt {attempt}, retrying...")
                    # Continue to next attempt (retry)
                    continue
                    
        except Exception as e:
            print(f"[ERROR] Exception on attempt {attempt}: {e}")
            # Continue to next attempt (retry)
            continue
    
    # Check if we successfully parsed JSON
    if attempt >= max_attempts:
        print(f"[ERROR] Failed to parse JSON after {max_attempts} attempts")
        return {
            'success': False,
            'error': f'Failed to get valid JSON from LLM after {max_attempts} attempts'
        }
    
    # Post-process to enforce strict rules and prevent hallucinations
    # 0. Convert any dict-formatted items to plain strings
    def convert_to_plain_strings(items, field_name):
        """Convert list items to plain strings, handling dict format from LLM"""
        if not items:
            return []
        clean_items = []
        for item in items:
            if isinstance(item, dict):
                # Extract text from dictionary format
                # Check for common keys: step, metric, description, text
                step = item.get("step", "")
                metric = item.get("metric", "")
                desc = item.get("description", item.get("text", ""))
                
                # Priority: step > description/text > metric
                if step:
                    clean_items.append(step)
                elif desc:
                    clean_items.append(desc)
                elif metric:
                    clean_items.append(f"Work on improving {metric.replace('_', ' ')}.")
                else:
                    # Fallback: convert dict to string (but try to extract any string value)
                    # Try to find any string value in the dict
                    string_values = [v for v in item.values() if isinstance(v, str) and v.strip()]
                    if string_values:
                        clean_items.append(string_values[0])
                    else:
                        clean_items.append(str(item))
            else:
                clean_items.append(str(item))
        return clean_items
    
    # ✅ Map new format to old format for backward compatibility
    # New format: key_strengths, key_weaknesses, action_plan, detailed_metric_feedback
    # Old format: strengths, improvement_areas, recommendations
    
    # Handle key_strengths → strengths
    if 'key_strengths' in llm_output:
        llm_output['strengths'] = convert_to_plain_strings(
            llm_output.get('key_strengths', []), 
            'key_strengths'
        )
    elif 'strengths' in llm_output:
        llm_output['strengths'] = convert_to_plain_strings(
            llm_output.get('strengths', []), 
            'strengths'
        )
    else:
        llm_output['strengths'] = []
    
    # Handle key_weaknesses → improvement_areas
    if 'key_weaknesses' in llm_output:
        llm_output['improvement_areas'] = convert_to_plain_strings(
            llm_output.get('key_weaknesses', []), 
            'key_weaknesses'
        )
    elif 'improvement_areas' in llm_output:
        llm_output['improvement_areas'] = convert_to_plain_strings(
            llm_output.get('improvement_areas', []), 
            'improvement_areas'
        )
    else:
        llm_output['improvement_areas'] = []
    
    # Handle action_plan → recommendations
    if 'action_plan' in llm_output:
        llm_output['recommendations'] = convert_to_plain_strings(
            llm_output.get('action_plan', []), 
            'action_plan'
        )
    elif 'recommendations' in llm_output:
        llm_output['recommendations'] = convert_to_plain_strings(
            llm_output.get('recommendations', []), 
            'recommendations'
        )
    else:
        llm_output['recommendations'] = []
    
    # ✅ Keep new detailed_metric_feedback for future use (if present)
    # This will be available in the output but frontend can use it later
    
    # 1. Map confidence_level deterministically from volatility
    volatility = numeric_summary.get('volatility', 'medium')
    if volatility == 'low':
        llm_output['confidence_level'] = 'high'
    elif volatility == 'medium':
        llm_output['confidence_level'] = 'medium'
    else:  # high volatility
        llm_output['confidence_level'] = 'low'
    
    # 2. Filter strengths to only include improving metrics
    metric_progress = numeric_summary.get('metric_progress', {})
    valid_strengths = []
    if llm_output.get('strengths'):
        # Only keep strengths that reference improving metrics
        improving_metrics = [
            metric for metric, data in metric_progress.items()
            if data.get('regression_trend') == 'improving'
        ]
        best_metric = numeric_summary.get('best_metric')
        if best_metric:
            improving_metrics.append(best_metric)
        
        for strength in llm_output['strengths']:
            # Check if strength references an improving metric
            strength_lower = strength.lower()
            for metric in improving_metrics:
                metric_name = metric.replace('_', ' ').lower()
                if metric_name in strength_lower or metric in strength_lower:
                    valid_strengths.append(strength)
                    break
    
    llm_output['strengths'] = valid_strengths
    
    return {
        'success': True,
        'llm_output': llm_output
    }


def generate_improved_metrics_summary(feedbacks, numeric_summary, llm_output):
    """
    Combine numeric results with LLM-generated explanations.
    Returns a clean, frontend-friendly JSON payload.
    """
    if not numeric_summary:
        return {
            "success": False,
            "error": "No numeric summary available"
        }
    
    # Extract LLM output
    llm_data = llm_output.get('llm_output', {}) if llm_output.get('success') else {}
    
    # Build the final summary combining numeric results and LLM explanations
    return {
        "success": True,
        "total_interviews": numeric_summary['total_interviews'],
        "numeric_results": {
            "regression_trend": numeric_summary['regression_trend'],
            "percent_change": numeric_summary['percent_change'],
            "trend_shape": numeric_summary['trend_shape'],
            "consistency": numeric_summary['consistency'],
            "volatility": numeric_summary['volatility'],
            "mean_score": numeric_summary['mean_score'],
            "best_metric": numeric_summary['best_metric'],
            "weakest_metric": numeric_summary['weakest_metric'],
            "recommended_focus": numeric_summary['recommended_focus'],
            "latest_emotion": numeric_summary['latest_emotion']
        },
        "metric_progress": numeric_summary['metric_progress'],
        "timeline_scores": numeric_summary['timeline_scores'],
        "llm_explanations": {
            "summary": llm_data.get('summary', ''),
            "strengths": llm_data.get('strengths', []),
            "improvement_areas": llm_data.get('improvement_areas', []),
            "recommendations": llm_data.get('recommendations', []),
            "confidence_level": llm_data.get('confidence_level', 'medium')
        }
    }


def analyze_user_performance(auth_token: str, model="llama3", limit=100):
    """
    Main function to analyze a user's interview performance trends.
    
    Args:
        auth_token: User's authentication token (Bearer token)
        model: Ollama model to use (default: "llama3")
        limit: Maximum number of interviews to analyze (default: 100)
    
    Returns:
        Dictionary with analysis results including numeric metrics and LLM explanations
    """
    print(f"[INFO] Starting performance trend analysis...")
    
    # Fetch interviews from edge function
    feedbacks = fetch_interview_metrics_from_edge_function(auth_token, limit)
    
    if not feedbacks:
        return {
            'success': False,
            'error': 'No interviews with metrics found or failed to fetch data',
            'total_interviews': 0
        }
    
    print(f"[INFO] Analyzing {len(feedbacks)} interviews...")
    
    # STEP 1: Calculate ALL numeric metrics deterministically
    numeric_summary = calculate_numeric_summary(feedbacks)
    
    if not numeric_summary:
        return {
            'success': False,
            'error': 'Insufficient data for analysis (need at least 2 interviews)',
            'total_interviews': len(feedbacks) if feedbacks else 0
        }
    
    # STEP 2: Generate LLM explanations based on numeric results
    llm_output = analyze_performance_with_llm(numeric_summary, model)
    
    # STEP 3: Combine numeric results with LLM explanations
    summary = generate_improved_metrics_summary(feedbacks, numeric_summary, llm_output)
    
    return summary


def analyze_performance_from_feedbacks(feedbacks, model="llama3"):
    """
    Analyze interview performance trends from provided feedbacks data.
    This function accepts feedbacks directly instead of fetching them.
    
    Args:
        feedbacks: List of feedback objects with metrics (from interview_feedback table)
        model: Ollama model to use (default: "llama3")
    
    Returns:
        Dictionary with clean, frontend-friendly analysis results
    """
    print(f"[INFO] Starting performance trend analysis from provided feedbacks...")
    
    if not feedbacks:
        return {
            'success': False,
            'error': 'No interviews with metrics found',
            'total_interviews': 0
        }
    
    # Filter to only include feedbacks with metrics
    feedbacks_with_metrics = [
        fb for fb in feedbacks 
        if fb.get('metrics') is not None
    ]
    
    if not feedbacks_with_metrics:
        return {
            'success': False,
            'error': 'No interviews with metrics found in provided data',
            'total_interviews': 0
        }
    
    print(f"[INFO] Analyzing {len(feedbacks_with_metrics)} interviews with metrics...")
    
    # STEP 1: Calculate ALL numeric metrics deterministically
    numeric_summary = calculate_numeric_summary(feedbacks_with_metrics)
    
    if not numeric_summary:
        return {
            'success': False,
            'error': 'Insufficient data for analysis (need at least 2 interviews)',
            'total_interviews': len(feedbacks_with_metrics)
        }
    
    # STEP 2: Generate LLM explanations based on numeric results
    llm_output = analyze_performance_with_llm(numeric_summary, model)
    
    # STEP 3: Combine numeric results with LLM explanations
    summary = generate_improved_metrics_summary(feedbacks_with_metrics, numeric_summary, llm_output)
    
    return summary


def print_analysis_results(analysis):
    """
    Pretty print the analysis results.
    Shows numeric results first, then LLM explanations.
    """
    if not analysis.get('success'):
        print(f"\n[ERROR] Analysis failed: {analysis.get('error', 'Unknown error')}")
        return
    
    print("\n" + "=" * 70)
    print("INTERVIEW PERFORMANCE TREND ANALYSIS")
    print("=" * 70)
    
    print(f"\nTotal Interviews Analyzed: {analysis.get('total_interviews', 'N/A')}")
    
    # === NUMERIC RESULTS ===
    numeric = analysis.get('numeric_results', {})
    print("\n" + "-" * 70)
    print("NUMERIC RESULTS (Deterministic Calculations)")
    print("-" * 70)
    print(f"Regression Trend: {numeric.get('regression_trend', 'N/A').upper()}")
    print(f"Percent Change (First Half → Second Half): {numeric.get('percent_change', 0):+.2f}%")
    print(f"Mean Score: {numeric.get('mean_score', 'N/A')}/10")
    print(f"Trend Shape: {numeric.get('trend_shape', 'N/A')}")
    print(f"Consistency: {numeric.get('consistency', 'N/A').upper()}")
    print(f"Volatility: {numeric.get('volatility', 'N/A').upper()}")
    print(f"Best Metric: {numeric.get('best_metric', 'N/A').replace('_', ' ').title() if numeric.get('best_metric') else 'N/A'}")
    print(f"Weakest Metric: {numeric.get('weakest_metric', 'N/A').replace('_', ' ').title() if numeric.get('weakest_metric') else 'N/A'}")
    print(f"Recommended Focus: {numeric.get('recommended_focus', 'N/A').replace('_', ' ').title() if numeric.get('recommended_focus') else 'N/A'}")
    print(f"Latest Emotion: {numeric.get('latest_emotion', 'N/A')}")
    
    # Metric Progress
    metric_progress = analysis.get('metric_progress', {})
    if metric_progress:
        print("\n" + "-" * 70)
        print("METRIC PROGRESS (Per Metric)")
        print("-" * 70)
        for metric, data in metric_progress.items():
            metric_name = metric.replace('_', ' ').title()
            trend_icon = "📈" if data.get('regression_trend') == 'improving' else "📉" if data.get('regression_trend') == 'declining' else "➡️"
            print(f"\n{trend_icon} {metric_name}:")
            print(f"  Average (First Half): {data.get('average_first_half', 'N/A')}/10")
            print(f"  Average (Second Half): {data.get('average_second_half', 'N/A')}/10")
            print(f"  Mean Score: {data.get('mean_score', 'N/A')}/10")
            print(f"  Regression Trend: {data.get('regression_trend', 'N/A').upper()}")
            print(f"  Volatility: {data.get('volatility', 'N/A').upper()}")
            print(f"  Slope: {data.get('slope', 'N/A')}")
    
    # Timeline
    timeline = analysis.get('timeline_scores', [])
    if timeline:
        print("\n" + "-" * 70)
        print("PERFORMANCE TIMELINE")
        print("-" * 70)
        for entry in timeline:
            print(f"Interview #{entry.get('interview_number', 'N/A')}: "
                  f"Score {entry.get('score', 'N/A')}/10, "
                  f"Emotion: {entry.get('emotion', 'N/A')}")
    
    # === LLM EXPLANATIONS ===
    llm = analysis.get('llm_explanations', {})
    print("\n" + "=" * 70)
    print("NATURAL LANGUAGE EXPLANATIONS (LLM Generated)")
    print("=" * 70)
    
    if llm.get('summary'):
        print("\n" + "-" * 70)
        print("SUMMARY")
        print("-" * 70)
        print(f"  {llm['summary']}")
    
    if llm.get('strengths'):
        print("\n" + "-" * 70)
        print("STRENGTHS")
        print("-" * 70)
        for strength in llm['strengths']:
            print(f"  ✓ {strength}")
    
    if llm.get('improvement_areas'):
        print("\n" + "-" * 70)
        print("IMPROVEMENT AREAS")
        print("-" * 70)
        for area in llm['improvement_areas']:
            print(f"  → {area}")
    
    if llm.get('recommendations'):
        print("\n" + "-" * 70)
        print("RECOMMENDATIONS")
        print("-" * 70)
        for rec in llm['recommendations']:
            print(f"  → {rec}")
    
    print(f"\nConfidence Level: {llm.get('confidence_level', 'N/A').upper()}")
    
    print("\n" + "=" * 70)


# CLI usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python analyze_performance_trends.py <auth_token> [model] [limit]")
        print("Example: python analyze_performance_trends.py eyJhbGc... llama3 50")
        print("\nNote: auth_token should be a valid Supabase JWT token")
        print("\nAlternatively, use the API endpoint: POST /api/analyze-performance-trends")
        sys.exit(1)
    
    auth_token = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "llama3"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    
    # Run analysis
    results = analyze_user_performance(auth_token, model, limit)
    
    # Print results
    print_analysis_results(results)
    
    # Optionally save to file
    if results.get('success'):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"performance_analysis_{timestamp}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n[INFO] Full analysis saved to: {output_file}")
