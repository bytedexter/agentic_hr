import os
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
import smtplib
import json
import time
from util.llm_factory import LLMFactory
import io
import fitz  
import psycopg2
from dotenv import load_dotenv
load_dotenv()
def pdf_extractor(file_path: str) -> str:
    print("[INFO] Converting PDF to text...")

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    pdf = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
    text = "\n".join([page.get_text() for page in pdf])
    pdf.close()

    safe_text = ''.join([c if ord(c) < 128 or c in '\n\r\t' else '' for c in text])
    return safe_text

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
def get_db_connection():
    """Establishes and returns a database connection."""
    if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        raise ValueError("Database environment variables are not fully set.")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to database: {e}")
        raise
def initialize_db_schema():
    """Creates the candidates table if it doesn't exist. Removed UNIQUE constraint on email."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # This will now create the table correctly since the old one is gone.
        # Notice recipient_email is just TEXT NOT NULL.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recruitement (
                id SERIAL PRIMARY KEY,
                file_path TEXT,
                experience_level TEXT,
                skill_match TEXT,
                response TEXT,
                recipient_email TEXT NOT NULL,
                email_text TEXT,
                name TEXT,
                role TEXT
            );
        """)
        conn.commit()
        print("Database schema initialized successfully.")
    except Exception as e:
        print(f"Error initializing database schema: {e}")
    finally:
        if conn:
            conn.close()
initialize_db_schema()
# Define the state structure
class State(TypedDict):
    file_path: str
    offer_letter_content: str
    generated_token: Optional[str]
    db_insertion_status: str
    email_sent_status: str
    experience_level: str
    skill_match: str
    response: str
    send_email:str
    recipient_email:str
    sub:str
    message:str
    text:str
    name:str
    role: str

def store_data_in_db(state: State) -> State:
    print("\n--- Storing Offer in DB and Sending Email ---")

    try:
        # Insert into recruitement table (no ON CONFLICT)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO recruitement (
                file_path, experience_level, skill_match, response, recipient_email, 
                email_text, name, role
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                state.get('file_path'),
                state.get('experience_level'),
                state.get('skill_match'),
                state.get('response'),
                state.get('recipient_email'),
                state["text"],
                state.get('name'),
                state.get('role')
            )
        )
        candidate_id = cur.fetchone()[0]
        conn.commit()
        db_insertion_status = f"Success (New Recruitement ID: {candidate_id})"
        print(f"Recruitement Data stored in DB ID: {candidate_id}")
        

    except Exception as e:
        print(f"Error storing offer in DB: {e}")
        db_insertion_status = f"Failed: {e}"
    finally:
        if 'conn' in locals() and conn:
            conn.close()
    print("Data stored in db successfully !!")


# Define nodes
def categorize_experience(state: State) -> State:
    application = pdf_extractor(state["file_path"])
    print("\nCategorizing experience level:")
    prompt = ChatPromptTemplate.from_template(
        "Based on the following job application, categorize the candidate as 'Entry-level', 'Mid-level' or 'Senior-level'. "
        "Anyone with experience of more than 7 years is considered 'Senior-level'. "
        "Respond with one of: 'Entry-level', 'Mid-level', or 'Senior-level'.\n\nApplication:\n{application}"
    )
    chain = prompt | LLMFactory.create_llm_instance(temperature=0.2, local_llm=False,max_tokens=1000)
    experience_level = chain.invoke({"application": application}).content
    print(f"Experience Level: {experience_level}")
    return {
        "file_path": file_path,
        "experience_level": experience_level.strip()
    }


def email_details(state:State)->State:
    application = pdf_extractor(state["file_path"])
    print("This is used to extract all the necessary email details from the application")
    prompt=ChatPromptTemplate.from_template(
        f"From the {application},extract the reciever email that is the mail id given in the resume and store it.Only return the email id as a single stirng nothing else.remove the \n and the name with it"
    )
    promptnew=ChatPromptTemplate.from_template(
       f"Only return the name from the resume name of the candidate from the {application} and store it in name variable."
    )
    chain=prompt | LLMFactory.create_llm_instance(temperature=0.2, local_llm=False,max_tokens=1000)
    chainnew=promptnew | LLMFactory.create_llm_instance(temperature=0.2, local_llm=False,max_tokens=1000)
    sender_email="mukhopadhyayaritranptel7@gmail.com"
    recipient_email=chain.invoke({"application": application}).content
    name=chainnew.invoke({"application": application}).content
    print("Name of the Candidate:", name.strip())
    print("Sender Email:", sender_email.strip())
    print("Receiver Email:", recipient_email.strip())
    return{
        "send_email":sender_email.strip(),
        "recipient_email":recipient_email.strip(),
        "name":name.strip(),
    }

def assess_skillset(state: State) -> State:
    application = pdf_extractor(state["file_path"])
    prompt = ChatPromptTemplate.from_template(
        "Based on the job application for a Python Developer, assess the candidate's skillset. "
        "Respond with either 'Match' or 'No Match'.\n\nApplication:\n{application}"
        "The Role is SDE.Store it in the role variable."
    )
    chain = prompt | LLMFactory.create_llm_instance(temperature=0.2, local_llm=False,max_tokens=1000)
    skill_match = chain.invoke({"application": application}).content
    role=chain.invoke({"application": application}).content
    print(f"Skill Match: {skill_match}")
    return {
        "file_path": file_path,
        "experience_level": state["experience_level"],
        "skill_match": skill_match.strip(),
        "role": role.strip()
    }

def schedule_hr_interview(state: State) -> State:
    print("\n[INFO] Scheduling interview...")
    application = pdf_extractor(state["file_path"])
    prompt=ChatPromptTemplate.from_template(
        "Generate the email subject and body for Candidate has been shortlisted for an HR interview by extracting information regarding the candidate from the given application {application} "
        "Save the email subject in sub and body in message."
        "Give the output as a json with keys sub and message."
    )
    chain=prompt | LLMFactory.create_llm_instance(temperature=0.2, local_llm=False,max_tokens=1000)
    response = chain.invoke({"application": application}).content
    print("LLM response:", response)
    cleaned_response = response.strip().strip("```").replace("json", "", 1).strip()
    # Parse the JSON string
    data = json.loads(cleaned_response)

    # Extract the fields
    sub = data["sub"]
    message = data["message"]
    text=f"Subject: {sub}\n\n{message}"
    state["text"]=text
    server=smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(state["send_email"],"aoxm hosj uenj vmrd")
    server.sendmail(state["send_email"],state["recipient_email"],text)
    print("Interview Scheduling Email Sent !!")
    return {
        "file_path": state["file_path"],
        "experience_level": state["experience_level"],
        "skill_match": state["skill_match"],
        "text":state["text"],
        "response": "Candidate has been shortlisted for an HR interview."
    }

def escalate_to_recruiter(state: State) -> State:
    application = pdf_extractor(state["file_path"])
    print("[INFO] Escalating to recruiter.")
    prompt=ChatPromptTemplate.from_template(
        "Generate the email subject and body for Candidate has senior-level experience but doesn't match job skills so the conadidature is escalated to the recruiter by extracting information regarding the candidate from the given application {application} "
        "Save the email subject in sub and body in message."
        "Give the output as a json with keys sub and message."
    )
    chain=prompt | LLMFactory.create_llm_instance(temperature=0.2, local_llm=False,max_tokens=1000)
    response = chain.invoke({"application": application}).content
    print("LLM response:", response)
    cleaned_response = response.strip().strip("```").replace("json", "", 1).strip()
    # Parse the JSON string
    data = json.loads(cleaned_response)

    # Extract the fields
    sub = data["sub"]
    message = data["message"]
    text=f"Subject: {sub}\n\n{message}"
    server=smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(state["send_email"],"aoxm hosj uenj vmrd")
    server.sendmail(state["send_email"],state["recipient_email"],text)
    print("Escalating Email Sent !!")
    return {
        "file_path": state["file_path"],
        "experience_level": state["experience_level"],
        "skill_match": state["skill_match"],
        "response": "Candidate has senior-level experience but doesn't match job skills."
    }

def reject_application(state: State) -> State:
    print("[INFO] Rejecting application.")
    application = pdf_extractor(state["file_path"])
    prompt=ChatPromptTemplate.from_template(
        "Generate the email subject and body for Candidate doesn't meet JD and has been rejected. by extracting information regarding the candidate from the given application {application} "
        "Save the email subject in sub and body in message."
        "Give the output as a json with keys sub and message."
    )
    chain=prompt | LLMFactory.create_llm_instance(temperature=0.2, local_llm=False,max_tokens=1000)
    response = chain.invoke({"application": application}).content
    print("LLM response:", response)
    cleaned_response = response.strip().strip("```").replace("json", "", 1).strip()
    # Parse the JSON string
    data = json.loads(cleaned_response)

    # Extract the fields
    sub = data["sub"]
    message = data["message"]
    text=f"Subject: {sub}\n\n{message}"
    state["text"]=text
    server=smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(state["send_email"],"aoxm hosj uenj vmrd")
    server.sendmail(state["send_email"],state["recipient_email"],text)
    print("Rejection Email Sent !!")
    return {
        "file_path": state["file_path"],
        "experience_level": state["experience_level"],
        "skill_match": state["skill_match"],
        "text":state["text"],
        "response": "Candidate doesn't meet JD and has been rejected."
    }

# Routing logic
def route_app(state: State) -> str:
    if state["skill_match"] == "Match":
        return "schedule_hr_interview"
    elif state["experience_level"] == "Senior-level":
        return "escalate_to_recruiter"
    else:
        return "reject_application"

def graph_builder(state: State) -> State:
    print("[INFO] Building the Garbh workflow.")
    workflow = StateGraph(State)
    workflow.add_node("categorize_experience", categorize_experience)
    workflow.add_node("store_data_in_db", store_data_in_db)
    workflow.add_node("assess_skillset", assess_skillset)
    workflow.add_node("email_details", email_details)
    workflow.add_node("schedule_hr_interview", schedule_hr_interview)
    workflow.add_node("escalate_to_recruiter", escalate_to_recruiter)
    workflow.add_node("reject_application", reject_application)

    workflow.add_edge(START, "categorize_experience")
    workflow.add_edge("categorize_experience", "email_details")
    workflow.add_edge("email_details", "assess_skillset")
    workflow.add_conditional_edges(
        "assess_skillset",
        route_app,
        {
            "schedule_hr_interview": "schedule_hr_interview",
            "escalate_to_recruiter": "escalate_to_recruiter",
            "reject_application": "reject_application"
        }
    )
    workflow.add_edge("schedule_hr_interview", "store_data_in_db")
    workflow.add_edge("escalate_to_recruiter", "store_data_in_db")
    workflow.add_edge("reject_application", "store_data_in_db")
    workflow.add_edge("store_data_in_db", END)
    app = workflow.compile()
    return app
graph=graph_builder(State)
if __name__ == "__main__":
    initialize_db_schema()
    folder_path = "C:\\Users\\l43ar\\Downloads\\AgenticHR\\agentic_hr\\CVList"

    # Loop through all files in the folder
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        # Optionally skip directories or non-PDF files
        if os.path.isfile(file_path) and filename.endswith(".pdf"):
            data=graph.invoke({
                "file_path": file_path
            })
        print(f"Resume {filename} processed successfully.\n")
        time.sleep(5)