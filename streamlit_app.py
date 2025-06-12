import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
import os
from dotenv import load_dotenv
from datetime import datetime
import json
import time
from onboarding_agent import generate_and_send_completion_email

# Load environment variables
load_dotenv()

# --- Database Configuration ---
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# --- File Storage (Placeholder) ---
UPLOAD_DIR = "uploaded_documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Helper Functions ---
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        return conn
    except psycopg2.OperationalError as e:
        st.error(f"Database Connection Error: {e}. Please ensure the database is running.")
        st.stop()

def get_candidate_by_token(token: str):
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM candidates WHERE unique_token = %s;", (token,))
        candidate = cur.fetchone()
    conn.close()
    return candidate

def update_offer_status(candidate_id: int, status: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE candidates SET offer_status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
                (status, candidate_id)
            )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error updating status: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def save_uploaded_file(uploaded_file, candidate_id, doc_type):
    try:
        ext = uploaded_file.name.split('.')[-1]
        filename = f"{candidate_id}_{doc_type}_{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return filepath
    except Exception as e:
        st.error(f"Error saving file {uploaded_file.name}: {e}")
        return None

def update_document_status(candidate_id, doc_key, status, file_path=None):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT document_status FROM candidates WHERE id = %s;", (candidate_id,))
            doc_status_json = cur.fetchone()['document_status']
            doc_status_json[doc_key] = {"status": status, "path": file_path, "uploaded_at": datetime.now().isoformat()}
            
            cur.execute(
                "UPDATE candidates SET document_status = %s WHERE id = %s;",
                (json.dumps(doc_status_json), candidate_id)
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        conn.close()


# --- Streamlit Page Definitions ---

def show_offer_page():
    candidate = st.session_state.candidate
    st.subheader(f"Hello, {candidate['name']}!")
    st.markdown(f"We are excited to offer you the position of **{candidate['role']}** starting on **{candidate['start_date']}**.")
    st.markdown("---")
    st.subheader("Your Offer Letter")
    st.markdown(candidate['offer_letter_content'], unsafe_allow_html=True)
    st.info("Please review your offer carefully. To proceed, click one of the options below.")

    col1, col2 = st.columns(2)
    if col1.button("✅ Accept Offer", use_container_width=True):
        if update_offer_status(candidate["id"], "Accepted"):
            st.session_state.candidate["offer_status"] = "Accepted"
            st.rerun()
    
    if col2.button("❌ Reject Offer", use_container_width=True):
        if update_offer_status(candidate["id"], "Rejected"):
            st.session_state.candidate["offer_status"] = "Rejected"
            st.rerun()

def show_documents_page():
    st.success(f"Congratulations, {st.session_state.candidate['name']}! You have accepted your offer.")
    st.markdown("Please upload the required documents below to complete your onboarding. The previous employment letter is optional.")
    
    documents_required = {
        "PAN Card": "pan_card",
        "Aadhaar Card": "aadhaar_card",
        "Bank Details (Cancelled Cheque/Statement)": "bank_details",
        "Highest Education Certificate": "education_cert",
        "Previous Employment Relieving Letter (Optional)": "relieving_letter"
    }
    
    with st.form("doc_upload_form"):
        # Dictionary to hold the uploaded file objects
        uploaded_files = {}
        for doc_label, doc_key in documents_required.items():
            # Check if already submitted
            current_status = st.session_state.candidate['document_status'].get(doc_key, {}).get('status', 'Pending')
            
            if current_status == 'Submitted':
                st.markdown(f"**{doc_label}:** ✅ Submitted")
            else:
                uploaded_files[doc_key] = st.file_uploader(
                    f"Upload your {doc_label}", type=["pdf", "jpg", "jpeg", "png"], key=doc_key
                )

        submitted = st.form_submit_button("Save and Continue", use_container_width=True)

        if submitted:
            # --- Validation and Processing Logic ---
            with st.spinner("Processing your documents... Please wait."):
                all_uploads_successful = True
                
                # Validation
                for doc_label, doc_key in documents_required.items():
                    if "Optional" not in doc_label and not uploaded_files.get(doc_key):
                        st.warning(f"Mandatory document missing: {doc_label}")
                        all_uploads_successful = False

                if all_uploads_successful:
                    # Processing
                    for doc_key, file in uploaded_files.items():
                        if file:
                            doc_label = [k for k, v in documents_required.items() if v == doc_key][0]
                            file_path = save_uploaded_file(file, st.session_state.candidate["id"], doc_key)
                            if file_path:
                                if update_document_status(st.session_state.candidate["id"], doc_key, "Submitted", file_path):
                                    st.toast(f"✅ {doc_label} saved successfully!", icon="✅")
                                    # Update session state immediately
                                    st.session_state.candidate['document_status'].setdefault(doc_key, {})['status'] = 'Submitted'
                                else:
                                    st.toast(f"❌ DB update failed for {doc_label}.", icon="❌")
                                    all_uploads_successful = False
                            else:
                                st.toast(f"❌ File save failed for {doc_label}.", icon="❌")
                                all_uploads_successful = False
                            time.sleep(1) # Small delay for toasts

            if all_uploads_successful and any(uploaded_files.values()):
                st.toast("All documents processed successfully!", icon="🎉")
                with st.spinner("Generating final welcome package..."):
                    completion_content = generate_and_send_completion_email(st.session_state.candidate['id'])
                    if completion_content:
                        st.session_state.completion_content = completion_content
                        st.session_state.onboarding_complete = True
                    else:
                        st.error("Could not generate or send the final welcome email. Please contact HR.")
                time.sleep(2)
                st.rerun()
            elif not any(uploaded_files.values()):
                st.warning("Please upload at least one document.")
            else:
                st.error("Some documents failed to process. Please correct them and try again.")


def show_completion_page():
    st.balloons()
    st.title("🎉 Welcome Aboard! 🎉")
    st.success("You have successfully completed all the onboarding steps. We are thrilled to have you join us!")
    st.markdown("---")
    
    if 'completion_content' in st.session_state:
        st.markdown("### A Message For You")
        st.markdown(st.session_state.completion_content, unsafe_allow_html=True)
        st.info("The message above has also been sent to your email for your reference.")
    else:
        st.warning("Could not load completion message. Please check your email or contact HR.")

def show_rejected_page():
    st.error(f"Thank you for your response, {st.session_state.candidate['name']}. Your offer has been marked as Rejected.")
    st.write("We wish you the best in your future endeavors.")

# --- Main App Logic ---
def main():
    st.set_page_config(page_title="Candidate Onboarding", layout="centered")
    st.title("🚀 Candidate Onboarding Portal")

    token = st.query_params.get("token")
    if not token:
        st.error("Invalid/missing token. Please use the link from your offer email.")
        return

    # Fetch candidate data only once and store in session state
    if 'candidate' not in st.session_state:
        candidate_data = get_candidate_by_token(token)
        if not candidate_data:
            st.error("Invalid/expired token. Please contact HR.")
            return
        st.session_state.candidate = candidate_data
        st.session_state.onboarding_complete = False

    # Check for token expiry
    if datetime.now(st.session_state.candidate['token_expiry'].tzinfo) > st.session_state.candidate['token_expiry']:
        st.error("This onboarding link has expired. Please contact HR.")
        return

    # Page routing logic
    offer_status = st.session_state.candidate.get("offer_status")
    
    if st.session_state.onboarding_complete:
        show_completion_page()
    elif offer_status == "Accepted":
        show_documents_page()
    elif offer_status == "Sent":
        show_offer_page()
    elif offer_status == "Rejected":
        show_rejected_page()
    else:
        st.warning("Unknown offer status. Please contact HR.")

if __name__ == "__main__":
    main()