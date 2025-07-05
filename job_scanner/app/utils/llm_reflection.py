import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from util.llm_factory import LLMFactory
from langchain.prompts import ChatPromptTemplate
from concurrent.futures import ThreadPoolExecutor
import json

llm = LLMFactory.create_llm_instance(temperature=0.2, local_llm=False)

BASE_PROMPT = """
You are an expert HR Analyst. Given the following Job Description, extract structured insights based on predefined categories.

Job Description:
---
{jd}
---

Format your output as valid JSON following this schema:
{format_schema}
"""

def _invoke_single_prompt(jd: str, format_schema: str) -> dict:
    prompt = ChatPromptTemplate.from_template(BASE_PROMPT).format(jd=jd, format_schema=format_schema)
    return json.loads(llm.invoke(prompt).content)

def invoke_llm_parallel(jd: str, format_schema: str, count: int) -> list:
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(_invoke_single_prompt, jd, format_schema) for _ in range(count)]
        return [f.result() for f in futures]
