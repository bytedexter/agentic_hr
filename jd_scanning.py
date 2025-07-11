"""
LLM Reflection and Aggregation Module

This module provides functionality for invoking language models with a reflection-based
approach, running multiple parallel reflections and aggregating their outputs.
Used for job description scanning and analysis.
"""

import json
import re
from typing import List, Dict, Any

from util.llm_factory import LLMFactory, ChatPromptTemplate
from util.system_prompt import prompt_generate_summary, agg_prompt

from langchain.schema.runnable import RunnableLambda
from langchain_core.runnables import Runnable

import logging

logger = logging.getLogger(__name__)


def _extract_valid_json(raw_text: str) -> Dict[str, Any]:
    """Extract valid JSON from LLM output."""
    match = re.search(r"\{[\s\S]*\}", raw_text.strip())
    if not match:
        logger.error("No valid JSON found in LLM output.")
        raise ValueError("No valid JSON found in LLM output.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        raise ValueError(f"Failed to parse JSON: {e}")


def build_reflection_chain(
    jd: str,
    format_schema: str,
    temperature: float = 0.2,
    local_llm: bool = False
) -> Runnable:
    """Return a Runnable chain for a single reflection."""
    llm = LLMFactory.create_llm_instance(
        temperature=temperature,
        local_llm=local_llm
    )

    def run_prompt(_) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_template(prompt_generate_summary).format(
            jd=jd,
            format_schema=format_schema
        )
        try:
            response = llm.invoke(prompt)
            logger.debug("Raw LLM response: %s", response.content)
            return _extract_valid_json(response.content)
        except Exception as e:
            logger.error("Failed to invoke LLM: %s", e)
            raise

    return RunnableLambda(run_prompt)


def build_aggregation_chain(
    reflections: List[Dict[str, Any]],
    temperature: float = 0.2,
    local_llm: bool = False,
) -> Dict[str, Any]:
    """Aggregate multiple reflected outputs into one using a final LLM call."""
    llm = LLMFactory.create_llm_instance(temperature=temperature, local_llm=local_llm)
    try:
        prompt = ChatPromptTemplate.from_template(agg_prompt).format(
            reflected_outputs=json.dumps(reflections, indent=2)
        )
        response = llm.invoke(prompt)
        logger.debug("Aggregation output: %s", response.content)
        return _extract_valid_json(response.content)
    except Exception as e:
        logger.error("Failed to aggregate reflections: %s", e)
        raise


def invoke_llm_with_reflection(jd: str, format_schema: str) -> Dict[str, Any]:
    """Invoke LLM with reflection (3 parallel calls) and aggregate the outputs."""
    if not jd or not jd.strip():
        raise ValueError("Job description cannot be empty")
    if not format_schema or not format_schema.strip():
        raise ValueError("Format schema cannot be empty")

    # Run 3 reflection chains in a loop
    reflections: List[Dict[str, Any]] = []
    for i in range(3):
        print(f"=== INVOKING LLM REFLECTION #{i+1} ===")
        chain = build_reflection_chain(jd, format_schema)
        result = chain.invoke({})
        print(f"\n--- Reflection #{i+1} ---\n{json.dumps(result, indent=2)}")
        reflections.append(result)

    # Step 2: Aggregate the outputs
    aggregated_result = build_aggregation_chain(reflections)
    print("=== FINAL AGGREGATED RESULT ===")
    print(json.dumps(aggregated_result, indent=2))

    return aggregated_result
