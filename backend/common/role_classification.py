"""Keyword-based technical role classification (fallback when LLM fails)."""


def classify_job_description_is_technical(job_title, job_description):
    haystack = f"{job_title} {job_description}".lower()
    technical_keywords = [
        "python", "java", "javascript", "typescript", "sql", "api", "backend", "frontend",
        "full stack", "fullstack", "developer", "engineer", "devops", "sre", "automation",
        "selenium", "aws", "cloud", "kubernetes", "docker", "microservices", "react",
        "node", "coding", "programming", "software", "data engineer", "machine learning",
        "qa automation", "test automation", "ci/cd",
    ]
    non_technical_keywords = [
        "sales", "marketing", "hr", "human resources", "recruiter", "customer support",
        "business development", "operations manager", "office assistant",
    ]
    if any(keyword in haystack for keyword in technical_keywords):
        return True
    if any(keyword in haystack for keyword in non_technical_keywords):
        return False
    return False
