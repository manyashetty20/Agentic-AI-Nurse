# main.py - Vitals Monitoring, Alerting, and Logging Service
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from typing import Dict, Any, List
from datetime import datetime
import uvicorn

# --- Global In-Memory Database (Simulates Persistence) ---
# Stores the data history for all patients
PATIENT_LOGS: Dict[str, List[Dict[str, Any]]] = {}

# --- Load the Context Database ---
def load_patient_data_lookup():
    """Loads patient context and custom thresholds from JSON file."""
    try:
        with open('patient_data.json', 'r') as f:
            data = json.load(f)
            return {p['patient_id']: p for p in data}
    except FileNotFoundError:
        print("CRITICAL ERROR: 'patient_data.json' not found. Server cannot start.")
        return {}

PATIENT_CONTEXT_DB = load_patient_data_lookup()
app = FastAPI()

# --- CORS Configuration (CRITICAL FIX for UI) ---
# Allows the browser (running on 'null' origin when opened locally) to talk to FastAPI
origins = [
    "http://localhost",
    "http://localhost:8001",
    "null",  # Allows file:// origin access
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Data Model for Incoming Vitals ---
class VitalsData(BaseModel):
    patient_id: str
    hr: int
    bp_sys: int
    bp_dia: int

# --- TIERED MONITORING LOGIC (The Core Agent Analysis) ---
def check_vitals_for_alert(patient_id: str, vitals: Dict[str, Any]) -> Dict[str, Any]:
    """Checks vitals against custom patient baselines to generate a tiered alert."""
    context = PATIENT_CONTEXT_DB.get(patient_id)
    
    if not context:
        return {"flag_color": "ERROR", "justification": f"Patient {patient_id} context missing from database."}

    baseline = context['custom_vitals_baseline']
    hr, bp_sys = vitals['hr'], vitals['bp_sys']
    
    flag = "GREEN_STABLE"
    justification = "Vitals are within acceptable patient-specific range. Monitoring continues."
    
    # Tier 4: RED CRITICAL (Immediate danger)
    if hr > baseline['HR_MAX'] + 10 or bp_sys > baseline['BP_SYS_MAX'] + 15:
        flag = "RED_CRITICAL"
        justification = (f"EMERGENCY TIER 4: HR ({hr} bpm) or Systolic BP ({bp_sys} mmHg) critically exceeds "
                         f"safe limits. IMMEDIATE intervention required for post-MI patient.")

    # Tier 3: ORANGE DANGER (Serious concern)
    elif hr > baseline['HR_MAX'] + 2 or bp_sys > baseline['BP_SYS_MAX'] + 5:
        flag = "ORANGE_DANGER"
        justification = (f"DANGER TIER 3: HR ({hr} bpm) or Systolic BP ({bp_sys} mmHg) is significantly elevated. "
                         f"Notify care team for urgent re-assessment.")

    # Tier 2: YELLOW WARNING (Requires attention)
    elif hr > baseline['HR_MAX'] or bp_sys > baseline['BP_SYS_MAX']:
        flag = "YELLOW_WARNING"
        justification = (f"WARNING TIER 2: Vitals ({hr} bpm / {bp_sys} mmHg) have exceeded managed baseline. "
                         f"Monitor closely and confirm reading in 5 minutes.")
        
    # Tier 1: GREEN STABLE (Normal)
    # If not triggered above, it remains "GREEN_STABLE"

    return {
        "patient_id": patient_id,
        "flag_color": flag,
        "justification": justification,
        "vitals_received": vitals
    }

# --- Data Logging Function ---
def log_vitals_data(patient_id: str, vitals: Dict[str, Any]):
    """Logs the incoming vital signs data to the in-memory log."""
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "hr": vitals['hr'],
        "bp_sys": vitals['bp_sys'],
        "bp_dia": vitals['bp_dia']
    }
    
    if patient_id not in PATIENT_LOGS:
        PATIENT_LOGS[patient_id] = []
        
    PATIENT_LOGS[patient_id].append(log_entry)
    print(f"INFO: Logged data for {patient_id}. Total entries: {len(PATIENT_LOGS[patient_id])}")


# --- FastAPI Endpoints ---

@app.post("/api/vitals/receive")
async def receive_vitals(vitals: VitalsData):
    """Receives data from the 'watch' stream, logs it, and triggers analysis."""
    vitals_dict = vitals.model_dump()
    
    # 1. LOG THE DATA (This is done when the 'demo.py' streamer posts)
    log_vitals_data(vitals.patient_id, vitals_dict)
    
    # 2. TRIGGER THE REAL-TIME ALERT CHECK (Analysis is always done on the latest post)
    analysis_result = check_vitals_for_alert(vitals.patient_id, vitals_dict) 
    
    # NOTE: The UI re-posts to this endpoint to get the latest analysis, 
    # but the logic ensures the analysis runs correctly.
    
    return {"status": "Analysis Complete", "alert_data": analysis_result}


@app.get("/api/vitals/history/{patient_id}")
async def get_patient_history(patient_id: str):
    """Provides the full historical log for a patient (used by the UI polling)."""
    
    # We retrieve the history *without* logging, avoiding the infinite loop bug.
    if patient_id in PATIENT_LOGS:
        return {
            "patient_id": patient_id,
            "total_readings": len(PATIENT_LOGS[patient_id]),
            "readings": PATIENT_LOGS[patient_id]
        }
    return {"patient_id": patient_id, "total_readings": 0, "readings": []}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
