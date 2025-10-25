import uvicorn
import asyncio
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict
from operator import itemgetter

# --- Imports (Unchanged) ---
from langchain_ollama import ChatOllama
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# --- 1. Define Data Structures (Unchanged) ---
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

# --- 2. Configure LLMs (Unchanged) ---
reasoning_llm = ChatOllama(
    model="cniongolo/biomistral", 
    temperature=0
)

# --- 3. Setup RAG (Knowledge Lookup) (Unchanged) ---
embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'}
)
vect_db = Chroma(
    persist_directory="./chroma_db", 
    embedding_function=embeddings
)
retriever = vect_db.as_retriever(search_kwargs={"k": 5})

print("Successfully loaded local LLMs and RAG retriever.")
print("NOTE: Using BioMistral for all tasks. Report generation may take 5-10 minutes.")

# --- 4. Define AI Agent Chains ---

# --- AGENT 2: THE SUMMARIZER ---

# --- STEP 1: Python function to extract facts (THIS IS UPDATED) ---
def extract_facts_from_transcript(messages: List[ChatMessage]) -> dict:
    facts = {
        "name": "N/A",
        "age_gender": "N/A",
        "chief_complaint": "N/A",
        "symptom_details": [],
        "history": "N/A",
        "medications": "N/A",
        "allergies": "N/A"
    }
    
    for i, msg in enumerate(messages):
        if msg.role == 'assistant' and (i + 1 < len(messages)) and messages[i+1].role == 'user':
            question = msg.content.lower()
            answer = messages[i+1].content
            
            if "please tell me your name" in question:
                facts["name"] = answer
            elif "age and gender" in question:
                # --- THIS IS THE FIX for "femal" ---
                answer_clean = answer.lower()
                answer_clean = re.sub(r'\bfemal\b', 'female', answer_clean, flags=re.IGNORECASE)
                answer_clean = re.sub(r'\bmal\b', 'male', answer_clean, flags=re.IGNORECASE)
                facts["age_gender"] = answer_clean.title()
                # --- END FIX ---
            elif "main symptoms" in question:
                facts["chief_complaint"] = answer
            elif "past medical history" in question:
                facts["history"] = answer
            elif "taking any medications" in question:
                facts["medications"] = answer
            elif "any allergies" in question:
                facts["allergies"] = answer
            # Capture symptom details
            elif "describe the pain" in question or "radiate" in question or "severe is the pain" in question or "shortness of breath" in question or "when the pain started" in question or "located" in question or "throbbing" in question or "sensitive to light" in question:
                facts["symptom_details"].append(f"Q: {msg.content}\nA: {answer}")

    return facts

# --- STEP 2: AI prompt that *only* gets the facts (Unchanged) ---
summarizer_prompt = ChatPromptTemplate.from_template(
"""You are a clinical summarizer. You will be given a set of extracted facts.
Write a single, professional summary paragraph.

FACTS:
- Patient: {name}, {age_gender}
- Chief Complaint: {chief_complaint}
- Symptom Details: {symptom_details}
- History: {history}
- Medications: {medications}
- Allergies: {allergies}

Write the summary now.
"""
)

# The new summarizer chain (Unchanged)
summarizer_chain = (
    RunnablePassthrough()
    | (lambda msgs: extract_facts_from_transcript(msgs))
    | summarizer_prompt 
    | reasoning_llm 
    | StrOutputParser()
)


# --- AGENT 3: THE REPORT GENERATOR (Unchanged) ---
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

class DifferentialDiagnosis(BaseModel):
    condition: str = Field(description="The suspected medical condition")
    justification_present: List[str] = Field(description="List of patient's symptoms that support this diagnosis")
    justification_absent: List[str] = Field(description="List of common symptoms for this condition that the patient did NOT report")

class ReportBody(BaseModel):
    red_flags: List[str] = Field(description="List of any 'Red Flag' symptoms that require immediate attention.")
    differential_diagnoses: List[DifferentialDiagnosis] = Field(description="The top 3 most likely differential diagnoses.")

report_body_parser = JsonOutputParser(pydantic_object=ReportBody)
format_instructions = report_body_parser.get_format_instructions()

system_template = """
    You are a senior clinical reasoning AI. Your task is to analyze a patient interview transcript AND retrieved medical context.
    Your *only* job is to generate 'Red Flags' and 'Differential Diagnoses'.
    
    --- RETRIEVED MEDICAL CONTEXT ---
    {context}
    --- END OF CONTEXT ---
    
    --- PATIENT TRANSCRIPT ---
    {transcript}
    --- END OF TRANSCRIPT ---

    **CRITICAL INSTRUCTIONS:**
    1.  Your analysis MUST be based *ONLY* on the symptoms reported in the PATIENT TRANSCRIPT.
    2.  Do NOT hallucinate or invent symptoms.
    3.  For 'Red Flags', list *only* symptoms from the transcript that are high-risk.
    
    You MUST output *only* a valid JSON object matching this schema:
    {format_instructions}
    """

report_prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    ("human", "Full interview transcript:\n\n{transcript}")
])

reasoning_llm_json = reasoning_llm.bind(format="json")

report_generation_chain = (
    {
        "context": itemgetter("transcript") | retriever | format_docs,
        "transcript": itemgetter("transcript"),
        "format_instructions": lambda x: format_instructions
    }
    | report_prompt
    | reasoning_llm_json
    | report_body_parser
)

# --- 5. Hard-Coded Interview Logic (UPDATED) ---

# --- THIS IS THE FIX for "Back ache" ---
def get_symptom_category(complaint: str) -> str:
    """Categorizes a symptom string using synonyms."""
    complaint = complaint.lower().strip()
    
    if "chest pain" in complaint:
        return "chest_pain"
    if "headache" in complaint:
        return "headache"
    if "cough" in complaint:
        return "cough"
    if "abdominal" in complaint or "stomach" in complaint:
        return "abdominal_pain"
    if "shortness of breath" in complaint or "trouble breathing" in complaint:
        return "sob"
    if "ankle" in complaint:
        return "ankle_pain"
    if "back" in complaint:
        return "back_pain"
    
    return "other" # Default category

def get_user_data_for_interview(history: List[ChatMessage]) -> dict:
    """Parses the history to extract key patient data FOR THE INTERVIEW."""
    data = {"name": None, "chief_complaint_category": "other"}
    
    for i, msg in enumerate(history):
        if msg.role == 'assistant' and (i + 1 < len(history)) and history[i+1].role == 'user':
            question = msg.content.lower()
            answer = history[i+1].content
            
            if "please tell me your name" in question and data["name"] is None:
                data["name"] = answer.strip()
            elif "main symptoms" in question and data["chief_complaint_category"] == "other":
                data["chief_complaint_category"] = get_symptom_category(answer)
                
    return data

def determine_next_question(history: List[ChatMessage]) -> str:
    """
    This function replaces the interview AI. It reads the chat history
    and returns the *exact* next question.
    """
    
    last_ai_question = ""
    for msg in reversed(history):
        if msg.role == 'assistant':
            last_ai_question = msg.content.lower()
            break
            
    user_data = get_user_data_for_interview(history)
    name = user_data.get("name")
    name_str = f"Thank you, {name}. " if name else "Thank you. "

    # --- State Machine ---
    
    # State 1: Start
    if "to start, please type" in last_ai_question:
        return "Great! Please tell me your name."
        
    # State 2: Got name, ask for age/gender
    if "please tell me your name" in last_ai_question:
        name_from_last_message = history[-1].content.strip()
        return f"Thank you, {name_from_last_message}. Now, please tell me your age and gender."
        
    # State 3: Got age/gender, ask for symptoms
    if "age and gender" in last_ai_question:
        return f"{name_str}Now, please tell me about your main symptoms."
        
    # State 4: Got symptoms, start deep dive
    if "main symptoms" in last_ai_question:
        symptom_category = get_symptom_category(history[-1].content)
        
        if symptom_category == "chest_pain":
            return f"{name_str}Can you describe the pain? (e.g., Is it sharp, dull, crushing, or a pressure?)"
        if symptom_category == "headache":
            return f"{name_str}Where exactly is the headache located? (e.g., one side, all over, behind the eyes)"
        if symptom_category == "cough":
            return f"{name_str}Is the cough dry, or are you coughing up phlegm?"
        if symptom_category == "abdominal_pain":
             return f"{name_str}Where exactly is the pain? (e.g., upper, lower, left, right)"
        if symptom_category == "sob":
             return f"{name_str}Does this happen when you are resting, or only with activity?"
        if symptom_category == "ankle_pain":
            return f"{name_str}Did this pain start with an injury, like twisting it?"
        if symptom_category == "back_pain":
            return f"{name_str}Where exactly is the back pain? (e.g., upper, lower, one side)"
        
        # Default for "other"
        return f"{name_str}When did this symptom start?"

    # --- State 5: Symptom Deep Dive ---
    
    symptom_category = user_data.get("chief_complaint_category", "other")

    # --- CHEST PAIN questions ---
    if "describe the pain" in last_ai_question and symptom_category == "chest_pain":
        return f"{name_str}Does the pain radiate to your arm, jaw, or back?"
    if "radiate to your arm, jaw" in last_ai_question:
        return f"{name_str}On a scale of 1-10, how severe is the pain?"
    if "severe is the pain" in last_ai_question and symptom_category == "chest_pain":
        return f"{name_str}Do you have any shortness of breath, nausea, or sweating with it?"
    if "shortness of breath, nausea" in last_ai_question:
        return f"{name_str}What were you doing when the pain started?"
    if "when the pain started" in last_ai_question:
        return f"{name_str}To get a complete picture, do you have any past medical history, like diabetes or high blood pressure?"
        
    # ... (Other symptom blocks remain the same) ...
    
    # --- ANKLE PAIN questions ---
    if "start with an injury" in last_ai_question:
        return f"{name_str}Are you able to put weight on it?"
    if "put weight on it" in last_ai_question:
        return f"{name_str}Is there any swelling or bruising?"
    if "swelling or bruising" in last_ai_question:
        return f"{name_str}On a scale of 1-10, how severe is the pain?"
    if "severe is the pain" in last_ai_question and symptom_category == "ankle_pain":
         return f"{name_str}To get a complete picture, do you have any past medical history, like arthritis or gout?"

    # --- BACK PAIN questions ---
    if "where exactly is the back pain" in last_ai_question:
        return f"{name_str}Can you describe the pain? (e.g., sharp, dull ache, burning)"
    if "describe the pain" in last_ai_question and symptom_category == "back_pain":
        return f"{name_str}Does the pain shoot down your leg?"
    if "shoot down your leg" in last_ai_question:
        return f"{name_str}Is there any numbness or tingling?"
    if "numbness or tingling" in last_ai_question:
        return f"{name_str}What makes it better or worse (e.g., sitting, standing, lying down)?"
    if "better or worse" in last_ai_question:
        return f"{name_str}To get a complete picture, do you have any past medical history, like a previous back injury or arthritis?"

    # --- NEW: DEFAULT/OTHER PATH ---
    if symptom_category == "other":
        if "when did this symptom start" in last_ai_question:
            return f"{name_str}On a scale of 1-10, how severe is it?"
        if "severe is the pain" in last_ai_question and symptom_category == "other":
            return f"{name_str}Can you describe the symptom in more detail?"
        if "describe the symptom" in last_ai_question:
            return f"{name_str}To get a complete picture, do you have any past medical history, like diabetes or high blood pressure?"

    # --- State 6: Medical History ---
    if "past medical history" in last_ai_question:
        return f"{name_str}Are you currently taking any medications for that or anything else?"
    if "taking any medications" in last_ai_question:
        return f"{name_str}And do you have any allergies to medications?"
    if "any allergies" in last_ai_question:
        return f"{name_str}Finally, have any of your family members (like parents or siblings) had similar issues?"
    if "family members" in last_ai_question:
        return "Thank you. I have all the information I need."
        
    # Fallback
    return "Thank you. Please press I'm done to generate a report."

# --- 6. Create the FastAPI Server ---

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- THIS ENDPOINT IS UNCHANGED ---
@app.post("/chat")
async def chat(request: ChatRequest):
    next_question = determine_next_question(request.messages)
    return {"response": next_question}

# --- THIS ENDPOINT IS UPDATED ---
@app.post("/generate_report")
async def generate_report(request: ChatRequest):
    
    try:
        # --- NEW: Get user data for the report header ---
        facts = extract_facts_from_transcript(request.messages)
        patient_name = facts.get("name", "N/A")
        patient_age_gender = facts.get("age_gender", "N/A")
        
        # --- Run tasks ONE AT A TIME ---
        print("Starting report generation (Task 1: Summary)...")
        # --- FIX: Pass the messages list, not the transcript string ---
        summary_text = await summarizer_chain.ainvoke(request.messages)
        
        print("...Summary complete. (Task 2: Reasoning)...")
        # The reasoning chain still needs the simple string transcript
        transcript_string = "\n".join([f"{msg.role}: {msg.content}" for msg in request.messages])
        report_body_data = await report_generation_chain.ainvoke({"transcript": transcript_string})
        
        print("...Report tasks complete.")
        
        # --- STEP 3: Manually combine the results (NEW FORMAT) ---
        report_str = f"**Clinical Prep Report**\n\n"
        report_str += f"**Patient Name:** {patient_name}\n"
        report_str += f"**Age & Gender:** {patient_age_gender}\n\n"
        report_str += f"**Summary:**\n{summary_text}\n\n"
        
        report_str += "**Red Flags:**\n"
        if report_body_data['red_flags']:
            for flag in report_body_data['red_flags']:
                report_str += f"- {flag}\n"
        else:
            report_str += "- None identified based on transcript.\n"
            
        report_str += "\n**Differential Diagnoses (DDx):**\n"
        
        if report_body_data['differential_diagnoses']:
            for i, ddx in enumerate(report_body_data['differential_diagnoses']):
                report_str += f"\n**{i+1}. {ddx['condition']}**\n"
                
                if ddx['justification_present']:
                    report_str += "  - *Supporting Symptoms:* " + ", ".join(ddx['justification_present']) + "\n"
                else:
                    report_str += "  - *Supporting Symptoms:* None specified.\n"
                
                
        else:
             report_str += "- No specific diagnoses could be determined.\n"
            
        return {"report": report_str}

    except Exception as e:
        error_message = f"Error generating report: {type(e).__name__}: {e}"
        print(error_message)
        return {"report": f"A critical error occurred on the server.\n\n**Details:**\n{error_message}\n\nPlease check the server logs."}

# --- 7. Run the Server (Unchanged) ---
if __name__ == "__main__":
    print("Starting backend server on http://127.0.0.1:8000")
    print("AI Nurse is ready, with (FAST) Python-based interview logic.")
    uvicorn.run(app, host="127.0.0.1", port=8000)