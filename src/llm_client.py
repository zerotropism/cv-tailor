from typing import Any

import ollama

from config import MODEL, PROMPT_RANK, PROMPT_REWRITE


def rank_cvs(job_description: str | None, cvs_dict: dict[str, str]) -> list[dict[str, Any]]:
    """
    Rank CVs based on job description using Ollama.

    Args:
        job_description: The job description text
        cvs_dict: Dictionary with CV names as keys and CV content as values

    Returns:
        List of top 3 candidates with score [0,1] and explanation
    """
    results = []

    for cv_name, cv_content in cvs_dict.items():
        prompt = PROMPT_RANK.format(job_description=job_description, cv_content=cv_content)

        response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])

        content = response["message"]["content"]

        # Parse response
        score_line = [line for line in content.split("\n") if line.startswith("Score:")]
        explanation_line = [line for line in content.split("\n") if line.startswith("Explanation:")]

        if score_line and explanation_line:
            try:
                score = float(score_line[0].split(":")[1].strip())
                explanation = explanation_line[0].split(":", 1)[1].strip()
            except (ValueError, IndexError, AttributeError):
                score = 0.0
                explanation = "Error parsing response"
        else:
            score = 0.0
            explanation = "Invalid response format"

        results.append({"name": cv_name, "score": score, "explanation": explanation})

    # Sort by score and return top 3
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:3]


def rewrite_cv(job_description: str, cv_content: str) -> str:
    """
    Rewrite CV to better match the job description.

    Args:
        job_description: The job description text
        cv_content: The original CV content

    Returns:
        Rewritten CV in Markdown format
    """
    prompt = PROMPT_REWRITE.format(job_description=job_description, cv_content=cv_content)

    response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])

    return response["message"]["content"]
