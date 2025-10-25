# --- app.py ---

import streamlit as st
import requests
import uuid

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Agentic AI Nurse",
    page_icon="🤖"
)

st.title("Agentic AI Nurse 🤖🩺")
st.caption("Your smart assistant for preliminary medical interviews")

# --- Session State Management ---
# Unique user ID for this session
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# API endpoint
FASTAPI_ENDPOINT = "http://127.0.0.1:8000/chat"

# --- Chat Interface ---

# Display past messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle new user input
if prompt := st.chat_input("Describe your symptoms..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- Call Backend API ---
    try:
        response = requests.post(
            FASTAPI_ENDPOINT,
            json={"user_id": st.session_state.user_id, "message": prompt}
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        
        ai_response = response.json().get("response", "No response from server.")

        # Add AI response to chat history
        st.session_state.messages.append({"role": "assistant", "content": ai_response})
        with st.chat_message("assistant"):
            st.markdown(ai_response)
            
    except requests.exceptions.RequestException as e:
        st.error(f"Could not connect to the AI Nurse API. Is it running? \n\nError: {e}")