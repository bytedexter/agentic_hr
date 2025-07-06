import json
import re
from typing import List, Dict, Any

from util.llm_factory import LLMFactory, ChatPromptTemplate
from util.system_prompt import prompt_generate_summary, agg_prompt

from langchain.schema.runnable import RunnableParallel, RunnableLambda
from langchain_core.runnables import Runnable


def _extract_valid_json(raw_text: str) -> Dict[str, Any]:
    """Extract valid JSON from LLM output."""
    match = re.search(r"\{[\s\S]*\}", raw_text.strip())
    if not match:
        raise ValueError("No JSON object found in LLM response.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to decode JSON from LLM response: {e}")


def build_reflection_chain(jd: str, format_schema: str) -> Runnable:
    """Return a Runnable chain for a single reflection."""
    llm = LLMFactory.create_llm_instance(temperature=0.2, local_llm=False)

    def run_prompt(_):
        prompt = ChatPromptTemplate.from_template(prompt_generate_summary).format(
            jd=jd, format_schema=format_schema
        )
        response = llm.invoke(prompt)
        print("=== RAW LLM RESPONSE ===")
        print(response.content)
        return _extract_valid_json(response.content)

    return RunnableLambda(run_prompt)


def build_aggregation_chain(reflections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate multiple reflected outputs into one using a final LLM call."""
    llm = LLMFactory.create_llm_instance(temperature=0.2, local_llm=False)
    prompt = ChatPromptTemplate.from_template(agg_prompt).format(
        reflected_outputs=json.dumps(reflections, indent=2)
    )
    response = llm.invoke(prompt)
    print("=== AGGREGATION OUTPUT ===")
    print(response.content)
    return _extract_valid_json(response.content)


def invoke_llm_with_reflection(jd: str, format_schema: str) -> Dict[str, Any]:
    """Invoke LLM with reflection (3 parallel calls) and aggregate the outputs."""
    if not jd or not jd.strip():
        raise ValueError("Job description cannot be empty")
    if not format_schema or not format_schema.strip():
        raise ValueError("Format schema cannot be empty")

    reflection_chains = RunnableParallel(
        r1=build_reflection_chain(jd, format_schema),
        r2=build_reflection_chain(jd, format_schema),
        r3=build_reflection_chain(jd, format_schema)
    )

    print("=== INVOKING LLM REFLECTION PARALLEL ===")
    results: Dict[str, Any] = reflection_chains.invoke({})
    reflections: List[Dict[str, Any]] = [results["r1"], results["r2"], results["r3"]]

    print("=== RAW REFLECTED OUTPUTS ===")
    for i, ref in enumerate(reflections, 1):
        print(f"\n--- Reflection #{i} ---\n{json.dumps(ref, indent=2)}")

    # Step 2: Aggregate the outputs
    aggregated_result = build_aggregation_chain(reflections)
    print("=== FINAL AGGREGATED RESULT ===")
    print(json.dumps(aggregated_result, indent=2))

    return aggregated_result
