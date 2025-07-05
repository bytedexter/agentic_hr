from app.utils.llm_reflection import invoke_llm_parallel, llm
import json
import re
import os

AGG_PROMPT = """
You are an experienced analyst. Given multiple structured outputs for the same JD, combine them into one consistent and complete output.

JSONs:
{reflected_outputs}

Final output must follow the exact same schema and include all valid points. Merge duplicates where possible.
"""

def scan_job_description(jd: str, count: int, config_path: str) -> dict:
    # Use the provided config_path, fallback to default if None
    if not config_path:
        config_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'config',
            'jd_output_format.json'
        )
    
    with open(config_path, 'r') as f:
        format_schema = f.read()
    # …rest of function…
    reflections = invoke_llm_parallel(jd, format_schema, count)

    aggregation_prompt = AGG_PROMPT.format(reflected_outputs=json.dumps(reflections, indent=2))
    final_result = llm.invoke(aggregation_prompt)

    # Try to extract JSON using regex if LLM adds extra text
    match = re.search(r"\{.*\}", final_result.content, re.DOTALL)
    if match:
        cleaned_json = match.group(0)
        return json.loads(cleaned_json)
    else:
        raise ValueError("LLM response did not contain valid JSON.")