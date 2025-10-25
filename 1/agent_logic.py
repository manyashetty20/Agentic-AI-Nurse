# --- agent_logic.py ---

import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.tools.retriever import create_retriever_tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.messages import SystemMessage

# Check if the API key is set
if not os.environ.get("GROQ_API_KEY"):
    raise EnvironmentError("GROQ_API_KEY environment variable not set. Please get a key from console.groq.com and set it.")

# --- 1. Medical Knowledge Base Setup ---
#
DUMMY_MEDICAL_KNOWLEDGE = """
- Symptoms of Myocardial Infarction (Heart Attack): 
  - Chest pain (pressure, tightness), pain in arm/neck/jaw, shortness of breath, sweating, nausea.
- Symptoms of Influenza (Flu):
  - Fever, cough, sore throat, runny nose, muscle aches, fatigue, headaches.
- Symptoms of Type 2 Diabetes:
  - Increased thirst, frequent urination, extreme hunger, unexplained weight loss, fatigue, blurred vision.
- Diagnostic Tests:
  - For Heart Attack: ECG, Troponin blood test.
  - For Flu: Rapid influenza diagnostic test (RIDT).
  - For Diabetes: A1C test, Fasting blood sugar test.
"""

def setup_medical_retriever():
    """
    Creates a RAG retriever from the medical knowledge base.
    This represents the "Medical Database Query".
    """
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.create_documents([DUMMY_MEDICAL_KNOWLEDGE])
    
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    vector_store = FAISS.from_documents(docs, embeddings)
    
    return vector_store.as_retriever()


# --- 2. Agentic Nurse Setup ---
#

def create_agentic_nurse(retriever):
    """
    Creates the Agentic AI Nurse that can reason and use tools.
    This is the "Context Analysis + Reasoning Engine".
    """
    
    llm = ChatGroq(
        # This is the stable, production model
        model_name="llama-3.3-70b-versatile", 
        temperature=0.7
    )

    # Create the tool for the agent to use
    retriever_tool = create_retriever_tool(
        retriever,
        "medical_knowledge_search",
        "Search for information about medical symptoms, conditions, and tests."
    )
    tools = [retriever_tool]

    # --- THIS IS THE NEW, MORE ROBUST PROMPT ---
    prompt_template = """
    You are an "Agentic AI Nurse" conducting a preliminary medical interview.
    Your goal is to gather information and produce a summary for a human clinician.
    DO NOT give a diagnosis.

    **YOUR PRIMARY GOAL:**
    Follow this 4-step workflow. Do not move to the next step until the current one is complete.
    1.  **Greet & Investigate Symptoms:** Greet the patient and ask for their main symptom. Ask 2-3 follow-up questions to understand the symptom (like severity, duration, nature). Use your 'medical_knowledge_search' tool to ask better questions.
    2.  **Gather History (Allergies):** Ask about any known allergies.
    3.  **Gather History (Medications):** After getting an answer for allergies, ask about current medications.
    4.  **Gather History (Conditions) & Report:** After getting an answer for medications, ask about pre-existing conditions. Once you have all three history items, thank the patient and generate the final report.

    **CRITICAL RULE FOR HANDLING ANSWERS:**
    - If the patient's response is unclear, ambiguous, or does not answer your most recent question, you MUST politely state that you didn't understand and re-ask the specific question.
    - **Example:** If you ask about allergies and the patient's response is "it comes and goes," you should say: "I'm sorry, I didn't quite understand. My last question was about allergies. Do you have any known allergies (to food, medication, or otherwise)?"
    - DO NOT move to the next step (e.g., from allergies to medications) until you have a clear "yes" or "no" type of answer for the current question.

    **FINAL REPORT FORMAT:**
    When you reach the end of step 4, generate a report formatted exactly like this:
    
    **Patient Intake Summary**
    
    * **Primary Complaint:** (e.g., "Severe headache and nausea")
    * **Symptom Details:** (e.g., "Started 2 hours ago, pain is sharp and rated 8/10, located behind the eyes.")
    * **Medical History:**
        * **Allergies:** (e.g., "Penicillin")
        * **Medications:** (e.g., "Ibuprofen as needed")
        * **Pre-existing Conditions:** (e.g., "Type 2 Diabetes")
    
    ---
    
    You are now interacting with the patient.
    
    Chat History:
    {chat_history}
    
    Patient's new message:
    {input}
    
    Your next step (thought process, current step, and response):
    {agent_scratchpad}
    """
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    return agent_executor

# --- Main setup logic ---
print("Setting up medical knowledge base...")
medical_retriever = setup_medical_retriever()
print("Creating Agentic AI Nurse (using Groq)...")
agent_nurse_executor = create_agentic_nurse(medical_retriever)
print("Agent is ready.")