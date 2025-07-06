from typing import TypedDict, List, Union
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
from datetime import datetime, timedelta
from dotenv import load_dotenv
from textblob import TextBlob
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langsmith import traceable
from typing_extensions import Annotated
import re
from util.llm_factory import LLMFactory
from util.system_prompt import (
    report_generation_prompt, feedback_prompt, acknowledgment_prompt, generate_goals_prompt
)
import random
import time
import os.path
import os
import pandas as pd

# Load environment variables
load_dotenv()

llm = LLMFactory.create_llm_instance(temperature=0.2, local_llm=False)
# Retry helper for LLM calls
def invoke_with_retries(prompt, retries: int = 3, delay: int = 2):
    for attempt in range(retries):
        try:
            return llm.invoke([prompt])
        except Exception as e:
            print(f"[Retry] Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise

def remove_markdown(text: str) -> str:
    """
    Removes markdown syntax like bold, italic, headers, and code blocks.
    Preserves bullet points (-, *) and numbered lists (1., 2., etc).
    """
    # Remove bold and italic markers (e.g., **text**, *text*, _text_)
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)

    # Remove headers (e.g., ### Heading)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)

    # Remove inline code and code blocks
    text = re.sub(r"`{1,3}(.*?)`{1,3}", r"\1", text)            # inline code
    text = re.sub(r"```[\s\S]*?```", "", text, flags=re.DOTALL) # code blocks

    # Clean excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

# Calendar setup
def create_calendar_event(employee_name, date, tasks):
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Force fresh login if no creds or invalid
    if not creds or not creds.valid or not creds.refresh_token:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')  # ✅ Force refresh_token
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    event = {
        'summary': f'Performance Review - {employee_name}',
        'description': f"Goals: {'; '.join(tasks)}",
        'start': {
            'dateTime': f"{date}T10:00:00",
            'timeZone': 'Asia/Kolkata'
        },
        'end': {
            'dateTime': f"{date}T10:30:00",
            'timeZone': 'Asia/Kolkata'
        },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"[Calendar] Event created: {event.get('htmlLink')}")


# Shared state definition
class PerformanceState(TypedDict):
    name: str  
    email: str  # static too
    role: str   # static too
    date: str   # also static
    tasks: Annotated[List[str], "allow_multiple"]
    review_scheduled: Annotated[bool, "allow_multiple"]
    notifications: Annotated[List[str], "allow_multiple"]
    acknowledged: Annotated[bool, "allow_multiple"]
    feedback: Annotated[Union[str, None], "allow_multiple"]
    report: Annotated[Union[str, None], "allow_multiple"]

# Generate a random date
def generate_random_date() -> str:
    future_date = datetime.today() + timedelta(days=random.randint(1, 14))
    return future_date.strftime("%Y-%m-%d")

# Goal setting node
from util.system_prompt import generate_goals_prompt

def goal_setting_node(state: PerformanceState) -> PerformanceState:
    prompt_text = generate_goals_prompt.format(role=state['role'])
    response = llm.invoke(prompt_text)
    goals = [g.strip("- ") for g in response.content.strip().split("\n") if g.strip()]
    state["tasks"] = goals[:3]
    return state


# Review scheduler node
def review_scheduler_node(state: PerformanceState) -> PerformanceState:
    state['review_scheduled'] = True
    create_calendar_event(state['name'], state['date'], state['tasks'])
    print(f"[ReviewScheduler] Review scheduled on {state['date']} for {state['name']}.")
    return state

# Notifier node
def notifier_node(state: PerformanceState) -> PerformanceState:
    note = f"Hi {state['name']}, your performance review is set for {state['date']}. Please review your goals."
    state['notifications'].append(note)
    print("[Notifier]", note)
    return state

# Acknowledgment node
def acknowledgment_node(state: PerformanceState) -> PerformanceState:
    prompt_text = acknowledgment_prompt.format(
        name=state['name'],
        tasks=", ".join(state["tasks"])
    )
    llm = LLMFactory.create_llm_instance(temperature=0.2, local_llm=False)
    response = llm.invoke(prompt_text)
    reply = remove_markdown(response.content.lower().strip())
    state['acknowledged'] = 'yes' in reply
    print(f"[Acknowledgment] {state['name']} responded: {response.content}")
    return state

# Condition check for acknowledgment
def check_acknowledgment(state: PerformanceState) -> str:
    return "FeedbackCollector" if state['acknowledged'] else "GoalSetting"

# Feedback collection node
def feedback_node(state: PerformanceState) -> PerformanceState:
    prompt_text = feedback_prompt.format(
        name=state["name"],
        role=state["role"],
        tasks=", ".join(state["tasks"])
    )
    llm = LLMFactory.create_llm_instance(temperature=0.2, local_llm=False)
    response = llm.invoke(prompt_text)
    state["feedback"] = remove_markdown(response.content.strip())
    print(f"[Feedback] {state['name']} says: {state['feedback']}")
    return state

# Report generation node
def report_node(state: PerformanceState) -> PerformanceState:
    prompt_text = report_generation_prompt.format(
        name=state["name"],
        role=state["role"],
        tasks=", ".join(state["tasks"]),
        acknowledged=state["acknowledged"],
        feedback=state["feedback"],
    )
    prompt = HumanMessage(content=prompt_text)
    response = invoke_with_retries(prompt)
    state["report"] = remove_markdown(response.content.strip())
    print(f"[Report] Summary for {state['name']} generated.")
    return state


# Calibration support node
def calibration_node(state: PerformanceState) -> PerformanceState:
    sentiment_score = TextBlob(state['feedback']).sentiment.polarity if state['feedback'] else 0.0
    tag = "Exceeds Expectations" if sentiment_score >= 0.3 else "Meets Expectations" if sentiment_score >= 0 else "Below Expectations"
    summary = (
        f"[Calibration] {state['name']} ({state['role']}):\n"
        f" - Review Date: {state['date']}\n"
        f" - Feedback Sentiment Score: {sentiment_score:.2f}\n"
        f" - Performance Tier: {tag}"
    )
    print(summary)
    state['report'] += "\n\n" + summary
    return state

# Load employee dataset
employee_df = pd.read_csv("Employee_Dataset.csv")

# LangGraph setup
builder = StateGraph(PerformanceState)
builder.add_node("GoalSetting", goal_setting_node)
builder.add_node("ReviewScheduler", review_scheduler_node)
builder.add_node("Notifier", notifier_node)
builder.add_node("Acknowledgment", acknowledgment_node)
builder.add_node("FeedbackCollector", feedback_node)
builder.add_node("ReportGenerator", report_node)
builder.add_node("CalibrationSupport", calibration_node)

builder.add_conditional_edges("Acknowledgment", check_acknowledgment, {
    "FeedbackCollector": "FeedbackCollector",
    "GoalSetting": "GoalSetting"
})

builder.set_entry_point("GoalSetting")
builder.add_edge("GoalSetting", "ReviewScheduler")
builder.add_edge("ReviewScheduler", "Notifier")
builder.add_edge("Notifier", "Acknowledgment")
builder.add_edge("Acknowledgment", "FeedbackCollector")
builder.add_edge("FeedbackCollector", "ReportGenerator")
builder.add_edge("ReportGenerator", "CalibrationSupport")
builder.add_edge("CalibrationSupport", END)

graph = builder.compile()
try:
    from langchain_core.runnables.graph_mermaid import draw_mermaid_png
    mermaid_str = graph.get_graph().draw_mermaid()
    png_bytes = draw_mermaid_png(
        mermaid_syntax=mermaid_str,
        output_file_path="graph.png",  # Path where PNG will be saved
        background_color="white",
        padding=20,
        )
    print("Graph visualization saved to graph.png")
except ImportError:
    print("Warning: Skipping graph visualization. Install 'mermaid-py' and 'graphviz' for this feature.")
except Exception as e:
    print(f"Warning: Could not generate graph visualization: {e}")

@traceable(name="HR Performance Review Flow")
def run_performance_review(input_state: PerformanceState):
    return graph.invoke(input_state)

# Run workflow for each employee
for _, emp in employee_df.iterrows():
    input_state: PerformanceState = {
        "name": emp['Full Name'],
        "email": emp['Email'],
        "role": emp['Role'],
        "date": generate_random_date(),
        "tasks": [],
        "review_scheduled": False,
        "notifications": [],
        "acknowledged": False,
        "feedback": None,
        "report": None,
    }
    print(f"\n--- Processing {input_state['name']} ({input_state['role']}) ---")
    final_state = run_performance_review(input_state)
    print("Final Report:\n", final_state['report'])
    # with open(f"{input_state['name']}_performance_report.txt", "w") as f:
    #     f.write(final_state['report'])
