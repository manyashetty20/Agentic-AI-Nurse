

# demo.py - Single-User Continuous Monitor Simulation
import requests
import time
import random
from typing import Dict, Any, List

# --- Context for Single User P001 ---
PATIENT_ID = "P001"
# P001: Post-MI. Custom Max HR: 110, BP_SYS: 150
# Note: Ranges are slightly expanded to hit the new tiered logic
NORMAL_HR_RANGE = (75, 95)
HIGH_HR_RANGE = (111, 120) # YELLOW_WARNING range (above 110)
CRITICAL_HR_RANGE = (121, 135) # RED_CRITICAL range (above 120)

NORMAL_BP_SYS_RANGE = (120, 145)
HIGH_BP_SYS_RANGE = (151, 165) # YELLOW/ORANGE WARNING range (above 150)
CRITICAL_BP_SYS_RANGE = (166, 185) # RED_CRITICAL range (above 165)

# CRITICAL FIX: The endpoint to post data to
API_URL = "http://127.0.0.1:8001/api/vitals/receive"

def generate_p001_vitals_payload():
    """Generates a random vital sign payload for P001, with a chance of hitting warning/critical tiers."""
    
    # 60% chance of being normal, 20% warning, 20% critical
    tier = random.choices(['NORMAL', 'WARNING', 'CRITICAL'], weights=[60, 20, 20], k=1)[0]
    
    if tier == 'CRITICAL':
        # 50/50 chance of a critical HR or BP event
        if random.choice([True, False]):
            hr = random.randint(*CRITICAL_HR_RANGE) 
            bp_sys = random.randint(*NORMAL_BP_SYS_RANGE)
        else:
            hr = random.randint(*NORMAL_HR_RANGE) 
            bp_sys = random.randint(*CRITICAL_BP_SYS_RANGE) 
            
    elif tier == 'WARNING':
        # Inject warning/danger level vitals
        if random.choice([True, False]):
            hr = random.randint(*HIGH_HR_RANGE) 
            bp_sys = random.randint(*NORMAL_BP_SYS_RANGE)
        else:
            hr = random.randint(*NORMAL_HR_RANGE) 
            bp_sys = random.randint(*HIGH_BP_SYS_RANGE)
    else:
        # Normal monitoring range
        hr = random.randint(*NORMAL_HR_RANGE)
        bp_sys = random.randint(*NORMAL_BP_SYS_RANGE)
        
    # Calculate Diastolic BP realistically
    bp_dia = random.randint(int(bp_sys * 0.4) + 20, int(bp_sys * 0.5) + 30)

    return {
        "patient_id": PATIENT_ID,
        "hr": hr,
        "bp_sys": bp_sys,
        "bp_dia": bp_dia
    }

print(f"--- Starting CONTINUOUS PERSONAL MONITORING for {PATIENT_ID} (30s interval) ---")
i = 0
while True:
    i += 1
    
    data = generate_p001_vitals_payload()
    
    print(f"\n[{i}] Posting new data to log...")
    print(f"    HR: {data['hr']} | BP: {data['bp_sys']}/{data['bp_dia']}")
    
    try:
        # POST data to the receiving endpoint. This triggers logging/analysis on the server.
        response = requests.post(API_URL, json=data)
        
        if response.status_code == 200:
            print(f"-> LOG STATUS: Success (Post complete).")
        else:
            print(f"-> LOG FAILED: Server returned status {response.status_code}")
        
        # Pause for 30 seconds
        time.sleep(60) 
        
    except requests.exceptions.ConnectionError:
        print("\n!!! CRITICAL ERROR: FastAPI server is unreachable. Ensure 'python main.py' is running. !!!")
        break