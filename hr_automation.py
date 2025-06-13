import os
import smtplib
import uuid
import json
import time
import io
import fitz
import shutil
import markdown
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langsmith import traceable
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.graph_mermaid import draw_mermaid_png

# Import from your existing util folder
from util.llm_factory import LLMFactory
from util.system_prompt import (
    generate_offer_letter_prompt,
    onboarding_completion_success_email_and_first_day_orientation_prompt,
    prompt_categorize_experience,
    prompt_assess_skillset,
    prompt_assess_skillset_new,
    prompt_email_details,
    prompt_email_details_new,
    prompt_schedule_interview,
    prompt_escalate_to_recruiter,
    prompt_rejection,
)

# Load .env file
load_dotenv()

# --- Email Configuration ---
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# --- PostgreSQL Database Configuration ---
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# --- Streamlit Application URL ---
STREAMLIT_APP_BASE_URL = os.getenv("STREAMLIT_APP_BASE_URL")


# --- Database Connection Helper ---
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
            password=DB_PASSWORD,
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to database: {e}")
        raise

# --- Initialize Database Schemas ---
def initialize_db_schema():
    """
    Creates the recruitment and candidates tables if they don't exist.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Create recruitment table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS recruitment (
                id SERIAL PRIMARY KEY,
                file_path TEXT,
                experience_level TEXT,
                skill_match TEXT,
                response TEXT,
                recipient_email TEXT NOT NULL,
                email_text TEXT,
                name TEXT,
                role TEXT,
                processed BOOLEAN DEFAULT FALSE,
                status TEXT DEFAULT 'Pending',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
        # Create candidates table
        # FIX: Removed redundant 'TIMESTAMP' keyword
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                start_date TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                offer_letter_content TEXT NOT NULL,
                unique_token TEXT NOT NULL,
                token_expiry TIMESTAMP WITH TIME ZONE NOT NULL,
                offer_status TEXT DEFAULT 'Sent',
                document_status JSONB DEFAULT '{}',
                it_provisioning_status TEXT DEFAULT 'Pending',
                orientation_email_status TEXT DEFAULT 'Pending',
                it_email_id TEXT,
                it_temp_password TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """
        )
        conn.commit()
        print("Database schemas initialized successfully.")
    except Exception as e:
        print(f"Error initializing database schemas: {e}")
    finally:
        if conn:
            conn.close()

# Ensure schemas are initialized when the script starts
initialize_db_schema()

# --- PDF Extractor ---
def pdf_extractor(file_path: str) -> str:
    """
    Extracts text content from a PDF file.
    """
    print(f"[INFO] Converting PDF to text from {os.path.basename(file_path)}...")
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        pdf = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
        text = "\n".join([page.get_text() for page in pdf])
        pdf.close()

        # Sanitize text to remove non-ASCII characters that can cause issues
        safe_text = "".join([c if ord(c) < 128 or c in "\n\r\t" else "" for c in text])
        return safe_text
    except Exception as e:
        print(f"Error extracting PDF from {os.path.basename(file_path)}: {e}")
        return ""

# --- Unified LangGraph State Definition ---
class AppState(TypedDict):
    """
    Unified state for the entire HR automation process (Recruitment & Onboarding).
    """
    file_path: Optional[str] # Path to the current resume being processed

    # Recruitment related fields
    experience_level: Optional[str]
    skill_match: Optional[str]
    recruitment_response: Optional[str] # General response about recruitment outcome
    recruitment_status: Optional[str] # "Accepted", "Escalated", "Rejected"
    recruitment_email_text: Optional[str] # The full email content sent during recruitment

    # Candidate details (extracted during recruitment, used in onboarding)
    name: Optional[str]
    role: Optional[str]
    recipient_email: Optional[str]

    # Onboarding related fields
    start_date: Optional[str] # Proposed start date for offer letter
    offer_letter_content: Optional[str] # Generated offer letter text
    generated_token: Optional[str] # Unique token for onboarding portal
    onboarding_db_insertion_status: Optional[str] # Status of offer insertion into DB
    onboarding_email_sent_status: Optional[str] # Status of offer email sending
    onboarding_candidate_id: Optional[int] # ID of the candidate in the 'candidates' table
    orientation_email_status: Optional[str] # Re-added for reporting, though sent by Streamlit app


# --- LangGraph Nodes (Updated to use AppState) ---

@traceable(name="Categorize Experience")
def categorize_experience(state: AppState) -> AppState:
    """Categorizes candidate's experience level from resume."""
    application_text = pdf_extractor(state["file_path"])
    print("\n--- Categorizing experience level ---")
    prompt = ChatPromptTemplate.from_template(
        prompt_categorize_experience.format(application=application_text)
    )
    chain = prompt | LLMFactory.create_llm_instance(
        temperature=0.2, local_llm=False, max_tokens=1000
    )
    experience_level = chain.invoke({"application": application_text}).content
    print(f"Experience Level: {experience_level.strip()}")
    return {**state, "experience_level": experience_level.strip()}

@traceable(name="Extract Email and Name")
def extract_email_and_name(state: AppState) -> AppState:
    """Extracts candidate's email and name from resume."""
    application_text = pdf_extractor(state["file_path"])
    print("\n--- Extracting email and name details ---")

    # Extract recipient email
    prompt_email = ChatPromptTemplate.from_template(
        prompt_email_details.format(application=application_text)
    )
    chain_email = prompt_email | LLMFactory.create_llm_instance(
        temperature=0.2, local_llm=False, max_tokens=1000
    )
    recipient_email = chain_email.invoke({"application": application_text}).content
    print(f"Receiver Email: {recipient_email.strip()}")

    # Extract candidate name
    prompt_name = ChatPromptTemplate.from_template(
        prompt_email_details_new.format(application=application_text)
    )
    chain_name = prompt_name | LLMFactory.create_llm_instance(
        temperature=0.2, local_llm=False, max_tokens=1000
    )
    name = chain_name.invoke({"application": application_text}).content
    print(f"Name of the Candidate: {name.strip()}")

    return {
        **state,
        "recipient_email": recipient_email.strip(),
        "name": name.strip()
    }

@traceable(name="Assess Skillset and Role")
def assess_skillset_and_role(state: AppState) -> AppState:
    """Assesses candidate's skillset and suggests a role from resume."""
    application_text = pdf_extractor(state["file_path"])
    print("\n--- Assessing skillset and suggesting role ---")

    # Assess skill match
    prompt_skill = ChatPromptTemplate.from_template(
        prompt_assess_skillset.format(application=application_text)
    )
    chain_skill = prompt_skill | LLMFactory.create_llm_instance(
        temperature=0.2, local_llm=False, max_tokens=1000
    )
    skill_match = chain_skill.invoke({"application": application_text}).content
    print(f"Skill Match: {skill_match.strip()}")

    # Suggest role
    prompt_role = ChatPromptTemplate.from_template(
        prompt_assess_skillset_new.format(application=application_text)
    )
    chain_role = prompt_role | LLMFactory.create_llm_instance(
        temperature=0.2, local_llm=False, max_tokens=1000
    )
    role = chain_role.invoke({"application": application_text}).content
    print(f"Suggested Role: {role.strip()}")

    return {
        **state,
        "skill_match": skill_match.strip(),
        "role": role.strip()
    }

@traceable(name="Schedule HR Interview")
def schedule_hr_interview(state: AppState) -> AppState:
    """Generates and sends email for HR interview, updates state."""
    print("\n--- Scheduling HR interview ---")
    application_text = pdf_extractor(state["file_path"])
    prompt = ChatPromptTemplate.from_template(
        prompt_schedule_interview.format(application=application_text)
    )
    chain = prompt | LLMFactory.create_llm_instance(
        temperature=0.2, local_llm=False, max_tokens=1000
    )
    response_llm = chain.invoke({"application": application_text}).content

    email_content = ""
    try:
        cleaned_response = response_llm.strip().strip("```").replace("json", "", 1).strip()
        data = json.loads(cleaned_response)
        sub = data.get("sub", "Interview Invitation")
        message = data.get("message", "We would like to invite you for an HR interview.")
        email_content = f"Subject: {sub}\n\n{message}"
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON for interview email: {e}. Using fallback content.")
        email_content = (
            "Subject: Interview Invitation\n\n"
            "Dear candidate,\n\n"
            "We would like to schedule an interview with you for the "
            f"{state.get('role', 'position')}. "
            "Please reply to this email to arrange a suitable time. \n\n"
            "Sincerely,\nHR Team"
        )

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, state["recipient_email"], email_content)
        print(f"Interview Scheduling Email Sent to {state['recipient_email']}!!")
        return {
            **state,
            "recruitment_email_text": email_content,
            "recruitment_status": "Accepted", # Status for the recruitment table
            "recruitment_response": "Candidate has been shortlisted for an HR interview.",
            "start_date": "October 1, 2025" # Set a default start date for accepted candidates
        }
    except Exception as e:
        print(f"Failed to send interview email: {e}")
        return {
            **state,
            "recruitment_email_text": email_content,
            "recruitment_status": "Email Failed - Accepted",
            "recruitment_response": f"Candidate shortlisted but email failed: {e}",
        }

@traceable(name="Escalate to Recruiter")
def escalate_to_recruiter(state: AppState) -> AppState:
    """Generates and sends email for recruiter escalation, updates state."""
    print("\n--- Escalating to recruiter ---")
    application_text = pdf_extractor(state["file_path"])
    prompt = ChatPromptTemplate.from_template(
        prompt_escalate_to_recruiter.format(application=application_text)
    )
    chain = prompt | LLMFactory.create_llm_instance(
        temperature=0.2, local_llm=False, max_tokens=1000
    )
    response_llm = chain.invoke({"application": application_text}).content

    email_content = ""
    try:
        cleaned_response = response_llm.strip().strip("```").replace("json", "", 1).strip()
        data = json.loads(cleaned_response)
        sub = data.get("sub", "Candidate Review Needed")
        message = data.get("message", "Please review a candidate with senior experience but a skill mismatch.")
        email_content = f"Subject: {sub}\n\n{message}"
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON for escalation email: {e}. Using fallback content.")
        email_content = (
            "Subject: Candidate Review Needed\n\n"
            "Dear Recruiter,\n\n"
            f"Please review {state.get('name', 'a candidate')} for the {state.get('role', 'position')}. "
            "They have senior experience but a skill mismatch for the current role.\n\n"
            "Thanks,\nHR AI"
        )

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, state["recipient_email"], email_content) # Sending to candidate, assuming recruiter would be BCC'd or internal system used
        print(f"Escalation Email Sent to {state['recipient_email']}!!")
        return {
            **state,
            "recruitment_email_text": email_content,
            "recruitment_status": "Escalated",
            "recruitment_response": "Candidate has senior-level experience but doesn't match job skills.",
        }
    except Exception as e:
        print(f"Failed to send escalation email: {e}")
        return {
            **state,
            "recruitment_email_text": email_content,
            "recruitment_status": "Email Failed - Escalated",
            "recruitment_response": f"Candidate escalated but email failed: {e}",
        }

@traceable(name="Reject Application")
def reject_application(state: AppState) -> AppState:
    """Generates and sends rejection email, updates state."""
    print("\n--- Rejecting application ---")
    application_text = pdf_extractor(state["file_path"])
    prompt = ChatPromptTemplate.from_template(
        prompt_rejection.format(application=application_text)
    )
    chain = prompt | LLMFactory.create_llm_instance(
        temperature=0.2, local_llm=False, max_tokens=1000
    )
    response_llm = chain.invoke({"application": application_text}).content

    email_content = ""
    try:
        cleaned_response = response_llm.strip().strip("```").replace("json", "", 1).strip()
        data = json.loads(cleaned_response)
        sub = data.get("sub", "Application Update")
        message = data.get("message", "We regret to inform you that we will not be moving forward with your application.")
        email_content = f"Subject: {sub}\n\n{message}"
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON for rejection email: {e}. Using fallback content.")
        email_content = (
            "Subject: Application Update\n\n"
            "Dear candidate,\n\n"
            "We appreciate your interest in the position. We regret to inform you that we will not be moving forward with your application at this time.\n\n"
            "Sincerely,\nHR Team"
        )

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, state["recipient_email"], email_content)
        print(f"Rejection Email Sent to {state['recipient_email']}!!")
        return {
            **state,
            "recruitment_email_text": email_content,
            "recruitment_status": "Rejected",
            "recruitment_response": "Candidate doesn't meet JD and has been rejected.",
        }
    except Exception as e:
        print(f"Failed to send rejection email: {e}")
        return {
            **state,
            "recruitment_email_text": email_content,
            "recruitment_status": "Email Failed - Rejected",
            "recruitment_response": f"Candidate rejected but email failed: {e}",
        }

@traceable(name="Store Recruitment Data in DB")
def store_recruitment_data_in_db(state: AppState) -> AppState:
    """Stores recruitment outcome data into the 'recruitment' table."""
    print("\n--- Storing recruitment data in DB ---")
    conn = None
    db_insertion_status = "Failed"
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO recruitment (
                file_path, experience_level, skill_match, response, recipient_email,
                email_text, name, role, processed, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                state.get("file_path"),
                state.get("experience_level"),
                state.get("skill_match"),
                state.get("recruitment_response"),
                state.get("recipient_email"),
                state.get("recruitment_email_text"),
                state.get("name"),
                state.get("role"),
                True, # Mark as processed once handled by this graph invocation
                state.get("recruitment_status"),
            ),
        )
        recruitment_id = cur.fetchone()[0]
        conn.commit()
        db_insertion_status = f"Success (New recruitment ID: {recruitment_id})"
        print(f"Recruitment Data stored in DB ID: {recruitment_id}")
        return {
            **state,
            "recruitment_db_insertion_status": db_insertion_status # Store status in unified state
        }

    except Exception as e:
        print(f"Error storing recruitment data in DB: {e}")
        return {
            **state,
            "recruitment_db_insertion_status": f"Failed: {e}"
        }
    finally:
        if conn:
            conn.close()

@traceable(name="Generate Offer Letter")
def generate_offer_letter(state: AppState) -> AppState:
    """Generates the offer letter content."""
    print("\n--- Generating Offer Letter ---")
    # FIX: Pass the formatted string directly to LLMFactory.invoke
    formatted_prompt_string = generate_offer_letter_prompt.format(
        name=state["name"], role=state["role"], start_date=state["start_date"]
    )
    response_message = LLMFactory.invoke(
        system_prompt=formatted_prompt_string,
        human_message=formatted_prompt_string, # Assuming this prompt is primarily a system instruction
        temperature=0.3,
        local_llm=False
    )
    offer_text = response_message.content
    print("Offer Letter Generated.")
    return {**state, "offer_letter_content": offer_text}


@traceable(name="Store Offer in DB and Send Email")
def store_offer_in_db_and_send_email(state: AppState) -> AppState:
    """Stores offer in 'candidates' DB and sends offer email."""
    print("\n--- Storing Offer in DB and Sending Email ---")
    db_insertion_status = "Failed"
    email_sent_status = "Failed"
    generated_token = str(uuid.uuid4())
    token_expiry = datetime.now() + timedelta(days=7)
    conn = None
    candidate_id = None # Initialize candidate_id

    try:
        # 1. Insert into Candidates Database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO candidates (
                name, role, start_date, recipient_email, offer_letter_content,
                unique_token, token_expiry, offer_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                state["name"],
                state["role"],
                state["start_date"],
                state["recipient_email"],
                state["offer_letter_content"],
                generated_token,
                token_expiry,
                "Sent",
            ),
        )
        candidate_id = cur.fetchone()[0] # Get the returned ID
        conn.commit()
        db_insertion_status = f"Success (New Candidate ID: {candidate_id})"
        print(f"Candidate offer stored in DB. Token: {generated_token}")

        # 2. Prepare and Send Email
        if not SENDER_EMAIL or not SENDER_APP_PASSWORD:
            raise ValueError("SENDER_EMAIL or SENDER_APP_PASSWORD not set.")
        
        # Check if STREAMLIT_APP_BASE_URL is set; otherwise, use a generic placeholder
        if not STREAMLIT_APP_BASE_URL:
            print("Warning: STREAMLIT_APP_BASE_URL not set. Onboarding link will be generic.")
            onboarding_link = f"[http://your-onboarding-portal.com/?token=](http://your-onboarding-portal.com/?token=){generated_token}" # Generic fallback URL
        else:
            onboarding_link = f"{STREAMLIT_APP_BASE_URL}?token={generated_token}"


        email_body_html = markdown.markdown(state["offer_letter_content"])
        email_body_html += f"""
        <p>To proceed, please click on the following secure link:</p>
        <p><a href="{onboarding_link}"><b>Click here to access your Onboarding Portal</b></a></p>
        <p>This link is valid for 7 days.</p>
        """
        msg = MIMEText(email_body_html, "html")
        msg["Subject"] = f"Your Job Offer from Our Company - {state['role']}"
        msg["From"] = SENDER_EMAIL
        msg["To"] = state["recipient_email"]

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)

        email_sent_status = "Success"
        print(f"Offer letter email sent successfully to {state['recipient_email']}.")

        return {
            **state,
            "generated_token": generated_token,
            "onboarding_db_insertion_status": db_insertion_status,
            "onboarding_email_sent_status": email_sent_status,
            "onboarding_candidate_id": candidate_id # Store the candidate ID in state
        }

    except (psycopg2.Error, ValueError) as db_err:
        if conn:
            conn.rollback()
        db_insertion_status = f"DB/Config Error: {db_err}"
        print(f"Failed to process offer: {db_err}")
    except Exception as e:
        email_sent_status = f"Email Error: {e}"
        print(f"Failed to send offer email: {e}")
    finally:
        if 'cur' in locals() and cur:
            cur.close()
        if conn:
            conn.close()

    return {
        **state,
        "generated_token": generated_token,
        "onboarding_db_insertion_status": db_insertion_status,
        "onboarding_email_sent_status": email_sent_status,
        "onboarding_candidate_id": candidate_id # Return ID even on partial failure if it was generated
    }


# Re-added the function definition for external use by streamlit_app.py
@traceable(name="Generate and Send Completion Email")
def generate_and_send_completion_email(candidate_id: int) -> Optional[str]:
    """
    Generates a welcome message and first-day orientation, emails it to the
    candidate, and updates their status in the database.
    This function is intended to be called by the Streamlit app.
    """
    print(f"\n--- Generating Completion Email for Candidate ID: {candidate_id} ---")
    conn = None
    email_status = "Failed"
    try:
        if not candidate_id:
            raise ValueError("Candidate ID not found for sending completion email.")

        # 1. Fetch candidate details
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT name, role, recipient_email FROM candidates WHERE id = %s",
            (candidate_id,),
        )
        candidate = cur.fetchone()
        if not candidate:
            raise ValueError(f"No candidate found with ID {candidate_id}")

        # 2. Generate content with LLM
        prompt = (
            onboarding_completion_success_email_and_first_day_orientation_prompt.format(
                name=candidate["name"], role=candidate["role"]
            )
        )
        response_message = LLMFactory.invoke(
            system_prompt=prompt, human_message=prompt, temperature=0.3, local_llm=False
        )
        completion_content = response_message.content
        print("Completion content generated by LLM.")

        # 3. Prepare and Send Email
        if not SENDER_EMAIL or not SENDER_APP_PASSWORD:
            raise ValueError("Sender email credentials are not configured.")

        email_body_html = markdown.markdown(completion_content)
        msg = MIMEText(email_body_html, "html")
        msg["Subject"] = "Welcome Aboard! Your First Day at Our Company"
        msg["From"] = SENDER_EMAIL
        msg["To"] = candidate["recipient_email"]

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)
        print(f"Completion email sent successfully to {candidate['recipient_email']}.")
        email_status = "Sent"

        # 4. Update database status
        cur.execute(
            "UPDATE candidates SET orientation_email_status = 'Sent', updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (candidate_id,),
        )
        conn.commit()
        print(f"Database status updated for candidate ID: {candidate_id}.")

        return completion_content

    except Exception as e:
        print(f"ERROR in completion email process for candidate ID {candidate_id}: {e}")
        if conn:
            conn.rollback()
        email_status = f"Failed: {e}"
        return None
    finally:
        if conn:
            conn.close()


# --- Routing Logic for Main Graph ---

def route_recruitment_outcome(state: AppState) -> str:
    """
    Routes based on the recruitment phase outcome.
    If accepted, proceeds to onboarding. Otherwise, ends.
    """
    recruitment_status_lower = state.get("recruitment_status", "").lower()
    # Only proceed to onboarding if the recruitment status is explicitly "accepted"
    if recruitment_status_lower == "accepted":
        print("Recruitment status is 'Accepted'. Proceeding to onboarding.")
        return "onboarding_start"
    else:
        print(f"Recruitment status is '{state.get('recruitment_status')}'. Ending process.")
        return "end_process"

def route_application_logic(state: AppState) -> str:
    """
    Routes based on skill match and experience level during recruitment.
    """
    skill_match_value = state.get("skill_match", "").strip()
    experience_level_value = state.get("experience_level", "").strip()

    if skill_match_value == "Match":
        return "schedule_hr_interview"
    elif experience_level_value == "Senior-level":
        return "escalate_to_recruiter"
    else: # This covers "No Match" for skill_match and non-Senior-level experience
        return "reject_application"


# --- Unified Main HR Automation Graph Definition ---
def build_main_hr_automation_graph():
    """
    Builds the complete LangGraph workflow for HR automation,
    combining recruitment and onboarding.
    """
    workflow = StateGraph(AppState)

    # Add all nodes
    workflow.add_node("categorize_experience", categorize_experience)
    workflow.add_node("extract_email_and_name", extract_email_and_name)
    workflow.add_node("assess_skillset_and_role", assess_skillset_and_role)
    workflow.add_node("schedule_hr_interview", schedule_hr_interview)
    workflow.add_node("escalate_to_recruiter", escalate_to_recruiter)
    workflow.add_node("reject_application", reject_application)
    workflow.add_node("store_recruitment_data_in_db", store_recruitment_data_in_db)
    workflow.add_node("generate_offer_letter", generate_offer_letter)
    workflow.add_node("store_offer_in_db_and_send_email", store_offer_in_db_and_send_email)
    # The 'send_onboarding_completion_email_node' is NOT part of this graph's workflow,
    # as it's triggered by the Streamlit app.


    # --- Define Flow ---

    # 1. Initial entry point and recruitment phase
    workflow.set_entry_point("categorize_experience")
    workflow.add_edge("categorize_experience", "extract_email_and_name")
    workflow.add_edge("extract_email_and_name", "assess_skillset_and_role")

    # Conditional routing based on recruitment assessment
    workflow.add_conditional_edges(
        "assess_skillset_and_role",
        route_application_logic,
        {
            "schedule_hr_interview": "schedule_hr_interview",
            "escalate_to_recruiter": "escalate_to_recruiter",
            "reject_application": "reject_application",
        },
    )

    # All recruitment outcome paths lead to storing data in DB
    workflow.add_edge("schedule_hr_interview", "store_recruitment_data_in_db")
    workflow.add_edge("escalate_to_recruiter", "store_recruitment_data_in_db")
    workflow.add_edge("reject_application", "store_recruitment_data_in_db")

    # 2. Transition from recruitment to onboarding (or end)
    workflow.add_conditional_edges(
        "store_recruitment_data_in_db",
        route_recruitment_outcome,
        {
            "onboarding_start": "generate_offer_letter",
            "end_process": END, # Rejected/Escalated candidates end here
        },
    )

    # 3. Onboarding phase (only for accepted candidates)
    workflow.add_edge("generate_offer_letter", "store_offer_in_db_and_send_email")
    # This graph's responsibility ends after sending the offer email.
    # The completion email is triggered by the Streamlit app.
    workflow.add_edge("store_offer_in_db_and_send_email", END) 

    app = workflow.compile()

    # Generate Mermaid PNG for visualization
    try:
        mermaid_str = app.get_graph().draw_mermaid()
        draw_mermaid_png(
            mermaid_syntax=mermaid_str,
            output_file_path="hr_automation_workflow.png",
            background_color="white",
            padding=20,
        )
        print("Unified HR automation workflow visualization saved to hr_automation_workflow.png")
    except Exception as e:
        print(f"Could not generate hr_automation_workflow.png: {e}. Ensure 'mermaid-cli' is installed and configured in your environment if running locally.")

    return app

main_hr_automation_graph = build_main_hr_automation_graph()


# --- Main Execution Block ---
if __name__ == "__main__":
    print("--- Starting Unified HR Automation Process ---")

    # Define your folder path where resumes are stored
    # Make sure to change this path as per your local setup
    resume_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CVList")
    processed_resume_folder = os.path.join(resume_folder_path, "processed")
    os.makedirs(processed_resume_folder, exist_ok=True)

    if not os.path.exists(resume_folder_path):
        print(f"Error: Resume folder not found at {resume_folder_path}. Please create it and add PDF resumes.")
    else:
        for filename in os.listdir(resume_folder_path):
            file_path = os.path.join(resume_folder_path, filename)

            if os.path.isfile(file_path) and filename.endswith(".pdf"):
                print(f"\n======== Processing Resume: {filename} ========")
                
                # Initialize AppState for the current resume
                initial_state = AppState(
                    file_path=file_path,
                    experience_level=None,
                    skill_match=None,
                    recruitment_response=None,
                    recruitment_status=None,
                    recruitment_email_text=None,
                    name=None,
                    role=None,
                    start_date=None,
                    offer_letter_content=None,
                    generated_token=None,
                    onboarding_db_insertion_status=None,
                    onboarding_email_sent_status=None,
                    onboarding_candidate_id=None,
                    orientation_email_status=None # Re-added for reporting, though sent by Streamlit app
                )

                # Invoke the unified graph
                final_state = main_hr_automation_graph.invoke(initial_state)

                print(f"\n======== Processing of {filename} Complete ========")
                print(f"Final Recruitment Status: {final_state.get('recruitment_status')}")
                # Only print onboarding statuses if the candidate was accepted
                if final_state.get('recruitment_status', '').lower() == 'accepted':
                    print(f"Offer Email Sent Status: {final_state.get('onboarding_email_sent_status')}")
                    print(f"Offer DB Insertion Status: {final_state.get('onboarding_db_insertion_status')}")
                    # The `orientation_email_status` is managed by the Streamlit app now.
                    # This print statement is for reporting purposes if the Streamlit app later updates the DB.
                    # It's important to remember this script doesn't *send* it directly.
                    print(f"Orientation Email Status (managed by Streamlit): {final_state.get('orientation_email_status', 'N/A - Check Streamlit/DB')}") 
                else:
                    print("Candidate was not accepted for onboarding.")
                print(f"Resume moved to: {processed_resume_folder}")

                # Move the processed resume to the 'processed' subfolder
                shutil.move(file_path, os.path.join(processed_resume_folder, filename))
                time.sleep(1) # Small delay to prevent issues with rapid file operations

    print("\n--- Unified HR Automation Process Complete ---")

    os.system("streamlit run streamlit_app.py")