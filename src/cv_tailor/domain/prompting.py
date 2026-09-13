"""Data blocks handed to the model. Delimited so instructions cannot be overridden."""


def job_and_cv(job_description: str, cv_content: str) -> str:
    return (
        "<job_description>\n"
        f"{job_description.strip()}\n"
        "</job_description>\n\n"
        "<cv>\n"
        f"{cv_content.strip()}\n"
        "</cv>"
    )
