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
    try:
        with open(config_path, 'r') as f:
            format_schema = f.read()
    except FileNotFoundError:
        raise ValueError(f"Configuration file not found: {config_path}")
    except Exception as e:
        raise ValueError(f"Error reading configuration file: {e}")

    reflections = invoke_llm_parallel(jd, format_schema, count)

    aggregation_prompt = AGG_PROMPT.format(reflected_outputs=json.dumps(reflections, indent=2))
    final_result = llm.invoke(aggregation_prompt)

    try:
        return json.loads(final_result.content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}")