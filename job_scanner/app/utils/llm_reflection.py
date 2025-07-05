import re
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from util.llm_factory import LLMFactory
from langchain.prompts import ChatPromptTemplate
from concurrent.futures import ThreadPoolExecutor
import json

llm = LLMFactory.create_llm_instance(temperature=0.2, local_llm=False)

BASE_PROMPT = """
You are an expert HR Analyst. Your job is to extract structured data from the job description below using the format shown.

Do not return any explanations, comments, or schema definitions. Respond ONLY with a valid JSON object that fills in the structure.

Job Description:
---
{jd}
---

Expected Output Format:
{format_schema}
""" 

def _invoke_single_prompt(jd: str, format_schema: str, llm_instance=None) -> dict:
    if llm_instance is None:
        llm_instance = LLMFactory.create_llm_instance(temperature=0.2, local_llm=False)
    try:
        prompt = ChatPromptTemplate.from_template(BASE_PROMPT).format(jd=jd, format_schema=format_schema)
        response = llm_instance.invoke(prompt)
        if not response or not response.content:
            raise ValueError("Empty response from LLM")

        # DEBUG: Print the full LLM response
        print("=== RAW LLM RESPONSE ===")
        print(response.content)

        # Clean and extract JSON using regex
        json_text = response.content.strip()
        match = re.search(r"\{[\s\S]*\}", json_text)
        if not match:
            raise ValueError("LLM response did not contain valid JSON.")
        
        return json.loads(match.group(0))

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from LLM: {e}")
    except Exception as e:
        raise RuntimeError(f"LLM invocation failed: {e}")

def invoke_llm_parallel(jd: str, format_schema: str, count: int, timeout: int = 300) -> list:
    if not jd or not jd.strip():
        raise ValueError("Job description cannot be empty")
    if not format_schema or not format_schema.strip():
        raise ValueError("Format schema cannot be empty")
    if count <= 0:
        raise ValueError("Count must be positive")

    results = []
    failed_count = 0

    with ThreadPoolExecutor(max_workers=min(count, 10)) as executor:
        futures = [executor.submit(_invoke_single_prompt, jd, format_schema, llm) for _ in range(count)]
        for future in futures:
            try:
                result = future.result(timeout=timeout)
                results.append(result)
            except Exception as e:
                failed_count += 1
                print(f"LLM invocation failed: {e}")

    if failed_count == count:
        raise RuntimeError("All LLM invocations failed")
    return results
