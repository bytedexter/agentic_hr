from app.utils.llm_reflection import invoke_llm_parallel, llm
import json
import os

AGG_PROMPT = """
You are an experienced analyst. Given multiple structured outputs for the same JD, combine them into one consistent and complete output.

JSONs:
{reflected_outputs}

Final output must follow the exact same schema and include all valid points. Merge duplicates where possible.
"""

def scan_job_description(jd: str, count: int, config_path: str) -> dict:
    with open(config_path) as f:
        format_schema = f.read()

    reflections = invoke_llm_parallel(jd, format_schema, count)

    aggregation_prompt = AGG_PROMPT.format(reflected_outputs=json.dumps(reflections, indent=2))
    final_result = llm.invoke(aggregation_prompt)

    return json.loads(final_result.content)