import os
import smtplib
import uuid
from email.mime.text import MIMEText
from typing import TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langsmith import traceable
from util.llm_factory import LLMFactory
from util.system_prompt import generate_offer_letter_prompt, onboarding_completion_success_email_and_first_day_orientation_prompt
import markdown
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from recruitement import store_data_in_db, State
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
            password=DB_PASSWORD
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to database: {e}")
        raise

# --- Initialize Database Schema ---
def initialize_db_schema():
    """Creates the candidates table if it doesn't exist. Removed UNIQUE constraint on email."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # This will now create the table correctly since the old one is gone.
        # Notice recipient_email is just TEXT NOT NULL.
        cur.execute("""
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
        """)
        conn.commit()
        print("Database schema initialized successfully.")
    except Exception as e:
        print(f"Error initializing database schema: {e}")
    finally:
        if conn:
            conn.close()

# --- LangGraph State ---
class OnboardingState(TypedDict):
    name: str
    role: str
    start_date: str
    offer_letter_content: str
    recipient_email: str
    generated_token: Optional[str]
    db_insertion_status: str
    email_sent_status: str

# --- LangGraph Nodes ---
@traceable(name="Generate Offer Letter")
def generate_offer_letter(state: OnboardingState) -> OnboardingState:
    print("\n--- Generating Offer Letter ---")
    prompt = generate_offer_letter_prompt.format(
        name=state['name'],
        role=state['role'],
        start_date=state['start_date']
    )
    response_message = LLMFactory.invoke(
        system_prompt=prompt,
        human_message=prompt,
        temperature=0.3,
        local_llm=False
    )
    offer_text = response_message.content
    print("Offer Letter Generated.")
    return {**state, "offer_letter_content": offer_text}


@traceable(name="Store Offer in DB and Send Email")
def store_offer_in_db_and_send_email(state: OnboardingState) -> OnboardingState:
    print("\n--- Storing Offer in DB and Sending Email ---")
    db_insertion_status = "Failed"
    email_sent_status = "Failed"
    generated_token = str(uuid.uuid4())
    token_expiry = datetime.now() + timedelta(days=7)

    try:
        # 1. Insert into Database (without ON CONFLICT)
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
            (state['name'], state['role'], state['start_date'], state['recipient_email'], 
             state['offer_letter_content'], generated_token, token_expiry, 'Sent')
        )
        candidate_id = cur.fetchone()[0]
        conn.commit()
        db_insertion_status = f"Success (New Candidate ID: {candidate_id})"
        print(f"Candidate offer stored in DB. Token: {generated_token}")

        # 2. Prepare and Send Email
        if not SENDER_EMAIL or not SENDER_APP_PASSWORD:
            raise ValueError("SENDER_EMAIL or SENDER_APP_PASSWORD not set.")

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
        msg["To"] = state['recipient_email']

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)
        
        email_sent_status = "Success"
        print(f"Offer letter email sent successfully to {state['recipient_email']}.")

    except (psycopg2.Error, ValueError) as db_err:
        if 'conn' in locals() and conn: conn.rollback()
        db_insertion_status = f"DB/Config Error: {db_err}"
        print(f"Failed to process: {db_err}")
    except Exception as e:
        email_sent_status = f"Email Error: {e}"
        print(f"Failed to send email: {e}")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals() and conn: conn.close()

    return {
        **state,
        "generated_token": generated_token,
        "db_insertion_status": db_insertion_status,
        "email_sent_status": email_sent_status,
    }

# --- NEW FUNCTION (Called by Streamlit after document upload) ---

@traceable(name="Generate and Send Completion Email")
def generate_and_send_completion_email(candidate_id: int) -> Optional[str]:
    """
    Generates a welcome message and first-day orientation, emails it to the
    candidate, and updates their status in the database.
    """
    print(f"\n--- Generating Completion Email for Candidate ID: {candidate_id} ---")
    conn = None
    try:
        # 1. Fetch candidate details
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT name, role, recipient_email FROM candidates WHERE id = %s", (candidate_id,))
        candidate = cur.fetchone()
        if not candidate:
            raise ValueError(f"No candidate found with ID {candidate_id}")

        # 2. Generate content with Gemini LLM
        prompt = onboarding_completion_success_email_and_first_day_orientation_prompt.format(
            name=candidate['name'],
            role=candidate['role']
        )
        response_message = LLMFactory.invoke(
            system_prompt=prompt,
            human_message=prompt,
            temperature=0.3,
            local_llm=False
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
        msg["To"] = candidate['recipient_email']

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)
        print(f"Completion email sent successfully to {candidate['recipient_email']}.")

        # 4. Update database status
        cur.execute(
            "UPDATE candidates SET orientation_email_status = 'Sent', updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (candidate_id,)
        )
        conn.commit()
        print(f"Database status updated for candidate ID: {candidate_id}.")

        return completion_content

    except Exception as e:
        print(f"ERROR in completion email process: {e}")
        if conn: conn.rollback()
        return None
    finally:
        if conn: conn.close()


# --- LangGraph Definition ---
def graph_builder_function():
    graph_builder = StateGraph(OnboardingState)
    graph_builder.add_node("OfferLetterGenerator", generate_offer_letter)
    graph_builder.add_node("DbStoreAndEmailSender", store_offer_in_db_and_send_email)
    graph_builder.set_entry_point("OfferLetterGenerator")
    graph_builder.add_edge("OfferLetterGenerator", "DbStoreAndEmailSender")
    graph_builder.add_edge("DbStoreAndEmailSender", END)
    graph = graph_builder.compile()

    return graph

onboarding_graph = graph_builder_function()

def fetch_latest_recruitment_entry() -> Optional[OnboardingState]:
    """
    Fetch the latest unprocessed candidate from the recruitment table.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Only get rows not yet processed
        cur.execute("""
            SELECT id, name, role, recipient_email
            FROM recruitement
            WHERE processed = FALSE
            ORDER BY id DESC
            LIMIT 1;
        """)
        row = cur.fetchone()

        if not row:
            print("✅ No unprocessed candidates found in recruitment table.")
            return None

        # Mark this row as processed immediately to prevent future reprocessing
        cur.execute("""
            UPDATE recruitement SET processed = TRUE WHERE id = %s;
        """, (row["id"],))
        conn.commit()

        return {
            "name": row["name"],
            "role": row["role"],
            "start_date": "October 1, 2025",  # Optional: infer or fetch from elsewhere
            "recipient_email": row["recipient_email"],
            "offer_letter_content": "",
            "generated_token": None,
            "db_insertion_status": "",
            "email_sent_status": "",
        }

    except Exception as e:
        print(f"❌ Error fetching latest unprocessed recruitment entry: {e}")
        return None
    finally:
        if conn: conn.close()



# # --- Main Execution Block (for testing offer generation) ---
# if __name__ == "__main__":

#     print("\n--- Initializing Database Schema (if needed) ---")
#     initialize_db_schema()

#     print("\n--- Onboarding Process Initiated ---")
#     initial_state: OnboardingState = {
#         "name": input("Enter candidate's name: "),
#         "role": input("Enter candidate's role: "),
#         "start_date": input("Enter start date (e.g., 'October 1, 2025'): "),
#         "recipient_email": input("Enter recipient's email: "),
#         "offer_letter_content": "", "generated_token": None,
#         "db_insertion_status": "", "email_sent_status": "",
#     }

#     print("\nRunning the offer sending graph...")
#     final_state = onboarding_graph.invoke(initial_state)

#     print("\n--- Offer Sending Process Complete ---")
#     print(f"DB Status: {final_state['db_insertion_status']}")
#     print(f"Email Status: {final_state['email_sent_status']}")

#     os.system("streamlit run streamlit_app.py")

def onboarder(state:OnboardingState)->OnboardingState:
    print("\n--- Initializing Database Schema (if needed) ---")
    initialize_db_schema()

    print("\n--- Fetching Latest Candidate from Recruitment Table ---")
    initial_state = fetch_latest_recruitment_entry()

    if initial_state is None:
        print("No candidate available to process.")
    else:
        print("\n🚀 Running the onboarding process...")
        final_state = onboarding_graph.invoke(initial_state)

        print("\n--- Onboarding Process Complete ---")
        print(f"DB Status: {final_state['db_insertion_status']}")
        print(f"Email Status: {final_state['email_sent_status']}")

        os.system("streamlit run streamlit_app.py")
onboarder(OnboardingState)