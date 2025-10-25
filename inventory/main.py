from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple, Set
import json
import os
from groq import Groq
import PyPDF2
import io
import re # Import regex
import random # Import random for shuffling and leave
from dotenv import load_dotenv

load_dotenv() # Load .env file if used

app = FastAPI(title="Nurse Admin API", version="2.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq client
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY environment variable not set. Using a dummy key. AI features may fail.")
    GROQ_API_KEY = "dummy-key-replace-if-needed" # Prevents startup crash

try:
    groq_client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"Error initializing Groq client: {e}. AI features may fail.")
    groq_client = None


# JSON file paths
INVENTORY_FILE = "inventory.json"
BILLING_FILE = "billing.json"
ROSTER_FILE = "roster.json"
PROTOCOLS_FILE = "protocols.json"
PROTOCOL_CHUNKS_FILE = "protocol_chunks.json"

# ===== HELPER FUNCTIONS =====
def load_json(filename):
    """Load JSON file with error handling"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content: return [] # Handle empty file
                return json.loads(content)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from {filename}. Returning empty list.")
            return []
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return []
    print(f"Info: File {filename} not found. Returning empty list.")
    return []

def save_json(filename, data):
    """Save JSON file with error handling"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {filename}: {e}")

def get_next_id(data):
    """Get next available ID"""
    if not data or not isinstance(data, list): return 1
    ids = [item.get('id', 0) for item in data if isinstance(item, dict)]
    if not ids: return 1
    return max(ids) + 1

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Splits text into overlapping chunks based on character count."""
    if not text: return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        actual_end = min(end + overlap, len(text))
        chunks.append(text[start:actual_end])
        start += chunk_size
        if start >= len(text): break
    print(f"Chunking: Created {len(chunks)} chunks from text.")
    return chunks

def extract_text_from_pdf(pdf_content_bytes):
    """Extract text content from PDF bytes"""
    text = ""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content_bytes))
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text: text += page_text + "\n"
        print(f"PDF Extraction: Extracted {len(text)} characters.")
        return text.strip() if text else None
    except Exception as e:
        print(f"Error reading PDF content: {e}")
        return None

# ===== PYDANTIC MODELS =====
class InventoryItem(BaseModel):
    item_name: str = Field(..., min_length=1)
    manufacturer: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)
    quantity: int = Field(default=0, ge=0)
    expiry_date: Optional[str] = None
    category: Optional[str] = None
    unit: str = Field(default="units")
    reorder_level: int = Field(default=10, ge=0)
    notes: Optional[str] = None

    @validator('expiry_date', pre=True, always=True)
    def validate_expiry_date_format(cls, v):
        if v:
            try: date.fromisoformat(v)
            except (ValueError, TypeError):
                 try: datetime.fromisoformat(v.replace('Z', '+00:00'))
                 except ValueError: raise ValueError('Invalid date format. Use YYYY-MM-DD')
        return v

class BillingItem(BaseModel):
    item_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)

class BillingRecord(BaseModel):
    patient_id: str = Field(..., min_length=1)
    patient_name: str = Field(..., min_length=1)
    doctor_name: str = Field(..., min_length=1)
    items: List[BillingItem] = Field(..., min_items=1)
    payment_status: str = Field(default="pending", pattern="^(pending|paid|cancelled)$")
    payment_method: Optional[str] = None
    notes: Optional[str] = None

class RosterEntry(BaseModel):
    staff_name: str = Field(..., min_length=1)
    role: Optional[str] = None
    shift_date: str
    shift_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_available: bool = True
    notes: Optional[str] = None

    @validator('shift_date', pre=True, always=True)
    def validate_shift_date_format(cls, v):
        try: date.fromisoformat(v)
        except (ValueError, TypeError): raise ValueError('Invalid shift_date format. Use YYYY-MM-DD')
        return v

class Protocol(BaseModel):
    title: str = Field(..., min_length=1)
    category: Optional[str] = None
    content: str = Field(..., min_length=1)
    tags: Optional[str] = None

class ProtocolQuery(BaseModel):
    question: str = Field(..., min_length=1)

# ===== NEW ROSTER GENERATOR MODEL =====
class RosterRequest(BaseModel):
    staff_names: List[str] = Field(..., min_items=1) # Simplified input
    start_date: str # YYYY-MM-DD
    num_days: int = Field(14, gt=0, le=30)
    shifts_per_day: Dict[str, int] = {"Morning": 1, "Afternoon": 1, "Night": 1}
    # Leave/unavailability is now handled by the generator

    @validator('start_date', pre=True, always=True)
    def validate_start_date_format(cls, v):
        try: date.fromisoformat(v)
        except (ValueError, TypeError): raise ValueError('Invalid start_date format. Use YYYY-MM-DD')
        return v

# ===== ROOT ENDPOINT =====
@app.get("/")
def read_root():
     return {"message": "Nurse Admin API v2.0", "endpoints": {"inventory": "/inventory/", "billing": "/billing/", "roster": "/roster/", "protocols": "/protocols/", "analytics": "/analytics/"}}

# ===== INVENTORY ENDPOINTS =====
@app.get("/inventory/")
def list_inventory():
    inventory = load_json(INVENTORY_FILE)
    return sorted(inventory, key=lambda x: x.get('item_name', '').lower())

@app.get("/inventory/available")
def list_available_items():
    inventory = load_json(INVENTORY_FILE)
    today_date = date.today()
    available_items = []
    for item in inventory:
        if not isinstance(item, dict) or item.get('quantity', 0) <= 0: continue
        expiry_date_str = item.get('expiry_date')
        is_expired = False
        if expiry_date_str:
            try:
                exp_date = date.fromisoformat(expiry_date_str.split('T')[0])
                if exp_date <= today_date: is_expired = True
            except (ValueError, TypeError): pass
        if is_expired: continue
        available_items.append({'id': item.get('id', 'N/A'), 'item_name': item.get('item_name', 'Unnamed Item'), 'manufacturer': item.get('manufacturer', 'Unknown'), 'price': item.get('price', 0.0), 'quantity_available': item.get('quantity', 0), 'unit': item.get('unit', 'units'), 'category': item.get('category', 'General')})
    return sorted(available_items, key=lambda x: x['item_name'].lower())

@app.post("/inventory/", status_code=201)
def add_inventory_item(item: InventoryItem):
    data = load_json(INVENTORY_FILE)
    if any(i.get('item_name', '').lower() == item.item_name.lower() for i in data if isinstance(i, dict)):
        raise HTTPException(status_code=400, detail="Item with this name already exists")
    new_item_dict = item.dict()
    new_item_dict['id'] = get_next_id(data)
    now_iso = datetime.now().isoformat()
    new_item_dict['created_at'] = now_iso
    new_item_dict['last_updated'] = now_iso
    if new_item_dict.get('expiry_date'):
         try: new_item_dict['expiry_date'] = date.fromisoformat(new_item_dict['expiry_date'].split('T')[0]).isoformat()
         except: pass
    data.append(new_item_dict)
    save_json(INVENTORY_FILE, data)
    return new_item_dict

@app.put("/inventory/{item_id}")
def update_inventory_item(item_id: int, item_update: InventoryItem):
    data = load_json(INVENTORY_FILE)
    updated = False
    for i, existing_item in enumerate(data):
        if isinstance(existing_item, dict) and existing_item.get('id') == item_id:
            update_data_dict = item_update.dict(exclude_unset=True)
            update_data_dict['created_at'] = existing_item.get('created_at', datetime.now().isoformat())
            update_data_dict['last_updated'] = datetime.now().isoformat()
            update_data_dict['id'] = item_id
            if 'expiry_date' in update_data_dict and update_data_dict['expiry_date']:
                 try: update_data_dict['expiry_date'] = date.fromisoformat(update_data_dict['expiry_date'].split('T')[0]).isoformat()
                 except: pass
            data[i] = update_data_dict
            save_json(INVENTORY_FILE, data)
            updated = True
            return data[i]
    if not updated: raise HTTPException(status_code=404, detail=f"Item with ID {item_id} not found")

@app.delete("/inventory/{item_id}", status_code=200)
def delete_inventory_item(item_id: int):
    data = load_json(INVENTORY_FILE)
    initial_count = len(data)
    data = [item for item in data if not (isinstance(item, dict) and item.get('id') == item_id)]
    if len(data) == initial_count: raise HTTPException(status_code=404, detail=f"Item with ID {item_id} not found")
    save_json(INVENTORY_FILE, data)
    return {"message": "Item deleted successfully"}

@app.get("/inventory/expiring/")
def get_expiring_inventory(days: int = Query(30, ge=1, le=365)):
    inventory = load_json(INVENTORY_FILE)
    today_date = date.today()
    target_date = today_date + timedelta(days=days)
    expiring = []
    for item in inventory:
         if not isinstance(item, dict): continue
         expiry_date_str = item.get('expiry_date')
         if expiry_date_str:
             try:
                 exp_date = date.fromisoformat(expiry_date_str.split('T')[0])
                 if today_date < exp_date <= target_date:
                     days_until = (exp_date - today_date).days
                     item_copy = item.copy()
                     item_copy['days_until_expiry'] = days_until
                     expiring.append(item_copy)
             except (ValueError, TypeError): pass
    return sorted(expiring, key=lambda x: x.get('days_until_expiry', 999))

@app.get("/inventory/low-stock/")
def get_low_stock():
    inventory = load_json(INVENTORY_FILE)
    return [item for item in inventory if isinstance(item, dict) and item.get('quantity', 0) <= item.get('reorder_level', 10)]

# ===== BILLING ENDPOINTS =====
@app.get("/billing/")
def list_billing():
    data = load_json(BILLING_FILE)
    valid_bills = [b for b in data if isinstance(b, dict) and 'date' in b]
    return sorted(valid_bills, key=lambda x: x['date'], reverse=True)

@app.post("/billing/", status_code=201)
def create_bill(bill: BillingRecord):
    inventory_data = load_json(INVENTORY_FILE)
    inventory_backup = [dict(item) for item in inventory_data if isinstance(item, dict)]
    billing_data = load_json(BILLING_FILE)
    inventory_map = {item['id']: item for item in inventory_data if isinstance(item, dict) and 'id' in item}
    total_amount = 0.0
    enriched_items = []
    items_to_update_in_inventory = {}
    for bill_item in bill.items:
        item_id = bill_item.item_id
        qty_needed = bill_item.quantity
        inv_item = inventory_map.get(item_id)
        if not inv_item: raise HTTPException(status_code=404, detail=f"Inventory item ID {item_id} not found")
        current_qty = inv_item.get('quantity', 0)
        if current_qty < qty_needed: raise HTTPException(status_code=400, detail=f"Insufficient quantity for {inv_item.get('item_name', 'Unknown')}. Available: {current_qty}, Requested: {qty_needed}")
        expiry_date_str = inv_item.get('expiry_date')
        if expiry_date_str:
            try:
                exp_date = date.fromisoformat(expiry_date_str.split('T')[0])
                if exp_date <= date.today(): raise HTTPException(status_code=400, detail=f"Item {inv_item.get('item_name', 'Unknown')} has expired on {exp_date.isoformat()}")
            except (ValueError, TypeError): pass
        unit_price = inv_item.get('price', 0.0)
        subtotal = unit_price * qty_needed
        total_amount += subtotal
        enriched_items.append({'item_id': item_id, 'item_name': inv_item.get('item_name', 'Unknown'), 'manufacturer': inv_item.get('manufacturer', 'Unknown'), 'quantity': qty_needed, 'unit_price': unit_price, 'subtotal': round(subtotal, 2), 'unit': inv_item.get('unit', 'units')})
        items_to_update_in_inventory[item_id] = items_to_update_in_inventory.get(item_id, 0) + qty_needed
    try:
        for item in inventory_data:
             if isinstance(item, dict) and item.get('id') in items_to_update_in_inventory:
                 item_id_to_update = item['id']
                 qty_to_deduct = items_to_update_in_inventory[item_id_to_update]
                 item['quantity'] = item.get('quantity', 0) - qty_to_deduct
                 item['last_updated'] = datetime.now().isoformat()
        save_json(INVENTORY_FILE, inventory_data)
        new_bill_dict = bill.dict(exclude={'items'})
        new_bill_dict['id'] = get_next_id(billing_data)
        new_bill_dict['items'] = enriched_items
        new_bill_dict['total_amount'] = round(total_amount, 2)
        new_bill_dict['date'] = date.today().isoformat()
        new_bill_dict['transaction_time'] = datetime.now().isoformat()
        new_bill_dict['payment_status'] = new_bill_dict.get('payment_status', 'pending')
        billing_data.append(new_bill_dict)
        save_json(BILLING_FILE, billing_data)
        return new_bill_dict
    except Exception as e:
        print(f"Error during bill creation/saving: {e}. Rolling back inventory.")
        save_json(INVENTORY_FILE, inventory_backup)
        raise HTTPException(status_code=500, detail=f"Internal server error during bill creation: {str(e)}")

@app.get("/billing/pending/")
def get_pending_bills():
    data = load_json(BILLING_FILE)
    return [bill for bill in data if isinstance(bill, dict) and bill.get('payment_status') == 'pending']

@app.put("/billing/{bill_id}/payment")
def update_payment_status(bill_id: int, payment_status: str = Query(..., pattern="^(pending|paid|cancelled)$"), payment_method: Optional[str] = Query(None)):
    data = load_json(BILLING_FILE)
    updated = False
    for bill in data:
        if isinstance(bill, dict) and bill.get('id') == bill_id:
            bill['payment_status'] = payment_status
            if payment_method: bill['payment_method'] = payment_method
            bill['last_updated'] = datetime.now().isoformat()
            save_json(BILLING_FILE, data)
            updated = True
            return bill
    if not updated: raise HTTPException(status_code=404, detail=f"Bill with ID {bill_id} not found")

# ===== ROSTER ENDPOINTS (MODIFIED) =====
@app.get("/roster/")
def list_roster():
    """Get all roster entries sorted by date"""
    data = load_json(ROSTER_FILE)
    valid_entries = [r for r in data if isinstance(r, dict) and 'shift_date' in r]
    return sorted(valid_entries, key=lambda x: x['shift_date'])


@app.get("/roster/two-weeks/")
def get_two_week_roster():
    """Get roster for next 14 days"""
    data = load_json(ROSTER_FILE)
    today_date = date.today()
    end_date = today_date + timedelta(days=14)
    result = []

    for entry in data:
        if not isinstance(entry, dict) or 'shift_date' not in entry: continue
        try:
            shift_date_obj = date.fromisoformat(entry['shift_date'].split('T')[0])
            if today_date <= shift_date_obj <= end_date:
                result.append(entry)
        except (ValueError, TypeError):
            pass # Ignore entries with invalid dates

    return sorted(result, key=lambda x: x['shift_date'])

# --- (REMOVED) @app.post("/roster/") ---
# --- (REMOVED) @app.put("/roster/{roster_id}") ---
# (Kept delete for manual cleanup)
@app.delete("/roster/{roster_id}", status_code=200)
def delete_roster_entry(roster_id: int):
    """Delete roster entry (Kept for manual cleanup)"""
    data = load_json(ROSTER_FILE)
    initial_count = len(data)
    data = [entry for entry in data if not (isinstance(entry, dict) and entry.get('id') == roster_id)]
    if len(data) == initial_count:
        raise HTTPException(status_code=404, detail=f"Roster entry with ID {roster_id} not found")
    save_json(ROSTER_FILE, data)
    return {"message": "Roster entry deleted successfully"}


# ===== NEW ROSTER GENERATOR ENDPOINT =====
@app.post("/roster/generate", status_code=201)
def generate_roster(request: RosterRequest):
    """
    Generates a new roster based on staff list and rules.
    It automatically assigns one random leave day per week
    and one mandatory rest day after 6 consecutive work days.
    """
    
    # 1. Define schedule parameters
    start_date = date.fromisoformat(request.start_date)
    dates_to_schedule = [start_date + timedelta(days=i) for i in range(request.num_days)]
    date_str_set = {d.isoformat() for d in dates_to_schedule}
    all_staff_names = request.staff_names
    
    # 2. Prepare data structures
    new_entries = []
    # Tracks last assigned shift (date, type)
    last_shift_map: Dict[str, Tuple[date, str]] = {}
    # Tracks consecutive work days
    consecutive_work_days: Dict[str, int] = {name: 0 for name in all_staff_names}
    # Tracks which staff are on leave on which date
    leave_map: Dict[str, Set[str]] = {name: set() for name in all_staff_names} # Key: staff_name, Value: set of leave date strings

    # --- NEW: Pre-generate random leave days ---
    num_weeks = (request.num_days + 6) // 7 # Calculate number of weeks
    for staff_name in all_staff_names:
        for week_num in range(num_weeks):
            week_start_day_index = week_num * 7
            # Find a valid random day index within the schedule and this week
            day_index = random.randint(0, 6)
            leave_date_index = week_start_day_index + day_index
            
            if leave_date_index < request.num_days:
                leave_date = dates_to_schedule[leave_date_index].isoformat()
                leave_map[staff_name].add(leave_date)
                print(f"DEBUG: Auto-assigned leave for {staff_name} on {leave_date}") # DEBUG
    
    # 3. Filter existing roster: Keep only entries OUTSIDE the new date range
    # This effectively clears the schedule for the new period.
    roster_to_keep = [
        entry for entry in load_json(ROSTER_FILE)
        if isinstance(entry, dict) and entry.get('shift_date') not in date_str_set
    ]

    # 4. Find the most recent shift for all staff *before* the new start_date
    roster_before_start = [e for e in roster_to_keep if e.get('shift_date', 'z') < request.start_date]
    roster_before_start.sort(key=lambda x: x.get('shift_date', '2000-01-01'))
    for entry in roster_before_start:
        if isinstance(entry, dict) and 'staff_name' in entry and 'shift_type' in entry:
            last_shift_map[entry['staff_name']] = (date.fromisoformat(entry['shift_date']), entry['shift_type'])

    # 5. Define shift types and their start/end times
    shift_definitions = {
        "Morning": {"start": "07:00", "end": "15:00"},
        "Afternoon": {"start": "15:00", "end": "23:00"},
        "Night": {"start": "23:00", "end": "07:00"}
    }
    
    # 6. Start Generation Loop
    current_max_id = get_next_id(roster_to_keep)
    
    for current_date in dates_to_schedule:
        date_str = current_date.isoformat()
        
        # Staff who worked Night shift yesterday
        yesterday = current_date - timedelta(days=1)
        staff_worked_night_yesterday = set()
        for staff_name in all_staff_names:
            last_work = last_shift_map.get(staff_name)
            if last_work:
                last_date, last_shift = last_work
                if last_date == yesterday and last_shift == "Night":
                    staff_worked_night_yesterday.add(staff_name)

        # Staff who must rest (worked 6 days)
        staff_must_rest = set()
        for staff_name in all_staff_names:
            if consecutive_work_days.get(staff_name, 0) >= 6:
                staff_must_rest.add(staff_name)
                
        # Combine all unavailable staff for this day
        staff_on_leave = {name for name, dates in leave_map.items() if date_str in dates}
        staff_unavailable_today = staff_on_leave.union(staff_must_rest)

        # Assign shifts for the day
        daily_assignments: Dict[str, str] = {} # Tracks who is assigned *today*
        
        # Add pre-generated leave shifts to the roster first
        for staff_name in staff_on_leave:
            leave_entry = {
                "id": current_max_id, "staff_name": staff_name, "role": "Staff",
                "shift_date": date_str, "shift_type": "Leave",
                "start_time": "00:00", "end_time": "00:00",
                "is_available": False, "notes": "Auto-Generated Leave"
            }
            new_entries.append(leave_entry)
            daily_assignments[staff_name] = "Leave" # Mark as assigned
            current_max_id += 1

        # Add mandatory rest day shifts
        for staff_name in staff_must_rest:
            if staff_name not in daily_assignments: # Don't overwrite leave
                rest_entry = {
                    "id": current_max_id, "staff_name": staff_name, "role": "Staff",
                    "shift_date": date_str, "shift_type": "Rest",
                    "start_time": "00:00", "end_time": "00:00",
                    "is_available": False, "notes": "Mandatory Rest Day (6+1)"
                }
                new_entries.append(rest_entry)
                daily_assignments[staff_name] = "Rest"
                current_max_id += 1
        
        # Now assign working shifts
        for shift_type, num_needed in request.shifts_per_day.items():
            if shift_type not in shift_definitions: continue 
                
            num_assigned = 0
            
            # Build list of eligible staff
            eligible_staff = []
            for staff_name in all_staff_names:
                # Rule 1: Not on leave or resting
                if staff_name in staff_unavailable_today:
                    continue
                # Rule 2: Not already assigned today
                if staff_name in daily_assignments:
                    continue
                # Rule 3: No "Clopening" (Night -> Morning)
                if shift_type == "Morning" and staff_name in staff_worked_night_yesterday:
                    continue
                
                eligible_staff.append(staff_name)

            random.shuffle(eligible_staff)
            
            for staff_name in eligible_staff:
                if num_assigned >= num_needed:
                    break # Shift quota filled
                    
                # Assign the shift!
                shift_times = shift_definitions[shift_type]
                new_entry = {
                    "id": current_max_id, "staff_name": staff_name,
                    "role": "Staff", # You can get this from a (future) staff profile
                    "shift_date": date_str, "shift_type": shift_type,
                    "start_time": shift_times["start"], "end_time": shift_times["end"],
                    "is_available": True, "notes": "Auto-Generated"
                }
                new_entries.append(new_entry)
                
                # Update tracking maps
                last_shift_map[staff_name] = (current_date, shift_type)
                daily_assignments[staff_name] = shift_type
                consecutive_work_days[staff_name] = consecutive_work_days.get(staff_name, 0) + 1 # Increment work counter
                
                num_assigned += 1
                current_max_id += 1
            
            if num_assigned < num_needed:
                print(f"WARNING: Could not fill {shift_type} shift on {date_str}. Needed {num_needed}, found {num_assigned}.")


        # After all shifts for the day, reset rest counters for those who didn't work
        for staff_name in all_staff_names:
            if staff_name not in daily_assignments:
                consecutive_work_days[staff_name] = 0
    
    # 7. Save and Return
    save_json(ROSTER_FILE, roster_to_keep + new_entries)
    return {
        "message": f"Successfully generated and added {len(new_entries)} new shifts (including leave/rest days).",
        "new_entries_added": new_entries
    }

# ===== PROTOCOL ENDPOINTS (MODIFIED FOR CHUNKING) =====
@app.get("/protocols/")
def list_protocols():
    """Get all protocols (metadata only)"""
    protocols = load_json(PROTOCOLS_FILE)
    return [{k: v for k, v in p.items()} for p in protocols if isinstance(p,dict)]

@app.get("/protocols/{protocol_id}/full")
def get_full_protocol_chunks(protocol_id: int):
    """Get the full text content of a specific protocol as chunks"""
    protocol_chunks = load_json(PROTOCOL_CHUNKS_FILE)
    protocol_meta = load_json(PROTOCOLS_FILE)
    meta = next((p for p in protocol_meta if isinstance(p, dict) and p.get('id') == protocol_id), None)
    if not meta: raise HTTPException(status_code=404, detail=f"Protocol metadata with ID {protocol_id} not found")
    chunk_entry = next((pc for pc in protocol_chunks if isinstance(pc, dict) and pc.get('protocol_id') == protocol_id), None)
    if not chunk_entry or not chunk_entry.get('chunks'):
         print(f"Warning: Chunks not found for protocol ID {protocol_id}. Returning metadata preview.")
         return {"id": protocol_id, "title": meta.get('title', 'N/A'), "category": meta.get('category', 'N/A'), "tags": meta.get('tags', ''), "chunks": [meta.get('content_preview', 'Full text missing.')]}
    return {"id": protocol_id, "title": meta.get('title', 'N/A'), "category": meta.get('category', 'N/A'), "tags": meta.get('tags', ''), "chunks": chunk_entry.get('chunks', [])}

@app.post("/protocols/upload-pdf/", status_code=201)
async def upload_protocol_pdf(
    file: UploadFile = File(...),
    title: str = Query(...),
    category: Optional[str] = Query(None),
    tags: Optional[str] = Query(None)
):
    """Upload PDF, extract text, CHUNK it, and save metadata/chunks"""
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF.")
    pdf_content = await file.read()
    if not pdf_content: raise HTTPException(status_code=400, detail="PDF file empty.")
    extracted_text = extract_text_from_pdf(pdf_content)
    if not extracted_text: raise HTTPException(status_code=400, detail="Could not extract text from PDF.")
    
    text_chunks = chunk_text(extracted_text, chunk_size=1000, overlap=100)
    if not text_chunks: raise HTTPException(status_code=400, detail="Failed to chunk extracted text.")
    
    protocols_meta = load_json(PROTOCOLS_FILE)
    protocol_chunks_data = load_json(PROTOCOL_CHUNKS_FILE)
    new_protocol_id = get_next_id(protocols_meta)
    now_iso = datetime.now().isoformat()
    new_protocol_meta = {'id': new_protocol_id, 'title': title, 'category': category or 'General', 'tags': tags or '', 'content_preview': text_chunks[0][:100] + '...', 'filename': file.filename, 'created_at': now_iso, 'last_updated': now_iso, 'chunk_count': len(text_chunks)}
    new_protocol_chunk_entry = {'protocol_id': new_protocol_id, 'chunks': text_chunks}
    protocols_meta.append(new_protocol_meta)
    protocol_chunks_data.append(new_protocol_chunk_entry)
    save_json(PROTOCOLS_FILE, protocols_meta)
    save_json(PROTOCOL_CHUNKS_FILE, protocol_chunks_data)
    return new_protocol_meta

@app.post("/protocols/", status_code=201)
def add_protocol(protocol: Protocol):
    """Add protocol manually (text input) - NOW WITH CHUNKING"""
    protocols_meta = load_json(PROTOCOLS_FILE)
    protocol_chunks_data = load_json(PROTOCOL_CHUNKS_FILE)
    new_protocol_dict = protocol.dict()
    new_protocol_id = get_next_id(protocols_meta)
    now_iso = datetime.now().isoformat()
    full_content = new_protocol_dict['content']
    text_chunks = chunk_text(full_content, chunk_size=1000, overlap=100)
    if not text_chunks: text_chunks = [full_content] if full_content else []
    content_preview = text_chunks[0][:100] + ('...' if len(text_chunks[0]) > 100 else '') if text_chunks else ''
    new_protocol_meta = {'id': new_protocol_id, 'title': new_protocol_dict['title'], 'category': new_protocol_dict.get('category') or 'General', 'tags': new_protocol_dict.get('tags') or '', 'content_preview': content_preview, 'filename': None, 'created_at': now_iso, 'last_updated': now_iso, 'chunk_count': len(text_chunks)}
    new_protocol_chunk_entry = {'protocol_id': new_protocol_id, 'chunks': text_chunks}
    protocols_meta.append(new_protocol_meta)
    protocol_chunks_data.append(new_protocol_chunk_entry)
    save_json(PROTOCOLS_FILE, protocols_meta)
    save_json(PROTOCOL_CHUNKS_FILE, protocol_chunks_data)
    return new_protocol_meta

@app.delete("/protocols/{protocol_id}", status_code=200)
def delete_protocol(protocol_id: int):
    """Delete protocol metadata AND its chunks"""
    protocols = load_json(PROTOCOLS_FILE)
    protocol_chunks = load_json(PROTOCOL_CHUNKS_FILE)
    initial_proto_count = len(protocols)
    protocols = [p for p in protocols if not (isinstance(p, dict) and p.get('id') == protocol_id)]
    protocol_chunks = [pc for pc in protocol_chunks if not (isinstance(pc, dict) and pc.get('protocol_id') == protocol_id)]
    if len(protocols) == initial_proto_count: raise HTTPException(status_code=404, detail=f"Protocol with ID {protocol_id} not found")
    save_json(PROTOCOLS_FILE, protocols)
    save_json(PROTOCOL_CHUNKS_FILE, protocol_chunks)
    return {"message": "Protocol and associated text chunks deleted successfully"}

# ===== ASK PROTOCOL QUESTION (MODIFIED FOR CHUNKING & BETTER SEARCH) =====
@app.post("/protocols/ask/")
def ask_protocol_question(query: ProtocolQuery):
    """Ask a question about protocols using Groq AI, searching chunks"""
    if not groq_client:
         raise HTTPException(status_code=503, detail="Groq client not initialized.")

    protocols_meta = load_json(PROTOCOLS_FILE)
    protocol_chunks_data = load_json(PROTOCOL_CHUNKS_FILE)
    print(f"DEBUG: Ask - Loaded {len(protocols_meta)} meta, {len(protocol_chunks_data)} chunk entries.")

    if not protocols_meta:
        return {"answer": "No protocols available.", "protocols_found": 0}

    query_lower = query.question.lower()
    query_keywords = set(re.findall(r'\b\w+\b', query_lower)) # Get individual keywords
    relevant_chunks = []
    protocol_ids_searched = set()
    chunk_map: Dict[int, List[str]] = {pt['protocol_id']: pt['chunks'] for pt in protocol_chunks_data if isinstance(pt, dict) and 'protocol_id' in pt and 'chunks' in pt}
    print(f"DEBUG: Ask - Created chunk map with {len(chunk_map)} entries.")

    for meta in protocols_meta:
         if not isinstance(meta, dict): continue
         protocol_id = meta.get('id')
         if not protocol_id: continue
         protocol_ids_searched.add(protocol_id)
         
         meta_text_lower = f"{meta.get('title', '')} {meta.get('category', '')} {meta.get('tags', '')}".lower()
         meta_match = query_lower in meta_text_lower or any(kw in meta_text_lower for kw in query_keywords)
         
         chunks = chunk_map.get(protocol_id, [])
         if not chunks:
             print(f"DEBUG: Ask - Protocol {protocol_id} metadata found but no chunks found in map.")
             continue

         for i, chunk in enumerate(chunks):
            chunk_lower = chunk.lower()
            score = sum(1 for keyword in query_keywords if keyword in chunk_lower)
            content_direct_match = query_lower in chunk_lower
            
            # Boost score significantly for title/tag match
            if meta_match:
                score += 10 
            if content_direct_match:
                score += 5
                
            if score > 1: # Require at least 2 keyword matches or a direct/meta match
                relevant_chunks.append({'protocol_id': protocol_id, 'title': meta.get('title', 'N/A'), 'category': meta.get('category', 'N/A'), 'chunk_index': i, 'content': chunk, 'score': score})


    print(f"DEBUG: Ask - Found {len(relevant_chunks)} potentially relevant chunks across {len(protocol_ids_searched)} protocols.")

    if not relevant_chunks:
        return {"answer": "No relevant text segments found matching your question within the available protocols.", "protocols_found": 0}

    relevant_chunks.sort(key=lambda x: x['score'], reverse=True)
    MAX_CONTEXT_CHARS = 10000
    current_chars = 0
    context_parts = []
    protocols_used_in_context = []
    protocol_ids_in_context = set()

    for chunk_info in relevant_chunks:
        protocol_id = chunk_info['protocol_id']
        protocol_header = f"Excerpt from Protocol ID {protocol_id}: {chunk_info['title']} (Chunk {chunk_info['chunk_index'] + 1})\n"
        chunk_content = chunk_info['content']
        part = protocol_header + chunk_content
        if current_chars + len(part) < MAX_CONTEXT_CHARS:
            context_parts.append(part)
            current_chars += len(part) + 2
            if protocol_id not in protocol_ids_in_context:
                 protocols_used_in_context.append({"id": protocol_id, "title": chunk_info['title'], "category": chunk_info['category']})
                 protocol_ids_in_context.add(protocol_id)
            if len(context_parts) >= 5: # Limit to top 5 chunks
                print(f"DEBUG: Ask - Reached chunk limit (5).")
                break
        else:
             print(f"DEBUG: Ask - Reached context char limit ({current_chars}). Using {len(context_parts)} chunks.")
             break
    
    context = "\n\n---\n\n".join(context_parts)
    print(f"DEBUG: Ask - Final context length: {len(context)} characters, using {len(protocols_used_in_context)} unique protocols.")

    if not context:
         return {"answer": "Could not build sufficient context from relevant chunks.", "protocols_found": len(relevant_chunks)}

    prompt = f"""You are a precise medical protocol assistant. Answer the user's question based *ONLY* on the following text excerpts from medical protocols. If the answer isn't in these excerpts, state that clearly.

User Question: {query.question}

Provided Excerpts:
{context}

Answer based ONLY on the excerpts provided above:"""

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful medical assistant answering questions strictly based on the provided text excerpts from protocols."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=500
        )
        answer = chat_completion.choices[0].message.content
        return {
            "answer": answer,
            "protocols_found": len(relevant_chunks),
            "protocols_used_in_context": protocols_used_in_context
        }
    except Exception as e:
        print(f"ERROR: Groq API call failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying Groq AI: {str(e)}")

# ===== ANALYTICS ENDPOINTS =====
@app.get("/analytics/dashboard/")
def get_dashboard_stats():
    inventory = load_json(INVENTORY_FILE)
    bills = load_json(BILLING_FILE)
    inventory = inventory if isinstance(inventory, list) else []
    bills = bills if isinstance(bills, list) else []
    total_items = len(inventory)
    low_stock_items_list = get_low_stock()
    expiring_items_list = get_expiring_inventory(30)
    low_stock_count = len(low_stock_items_list)
    expiring_count = len(expiring_items_list)
    out_of_stock_count = len([i for i in inventory if isinstance(i, dict) and i.get('quantity', 0) <= 0])
    today_date = date.today()
    thirty_days_ago = today_date - timedelta(days=30)
    recent_bills = []
    total_revenue_30d = 0.0
    pending_bills_count = 0
    for b in bills:
        if not isinstance(b, dict) or 'date' not in b: continue
        try:
             bill_date = date.fromisoformat(b['date'].split('T')[0])
             if bill_date >= thirty_days_ago:
                 recent_bills.append(b)
                 if b.get('payment_status') != 'cancelled': total_revenue_30d += b.get('total_amount', 0.0)
                 if b.get('payment_status') == 'pending': pending_bills_count += 1
        except (ValueError, TypeError): pass
    return {"inventory": {"total_items": total_items, "low_stock": low_stock_count, "expiring_soon": expiring_count, "out_of_stock": out_of_stock_count}, "billing": {"total_bills_30d": len(recent_bills), "total_revenue_30d": round(total_revenue_30d, 2), "pending_bills": pending_bills_count}}

@app.get("/analytics/inventory-alerts/")
def get_inventory_alerts():
    expiring_list = get_expiring_inventory(30)
    low_stock_list = get_low_stock()
    formatted_expiring = []
    for i in expiring_list:
         if isinstance(i, dict): formatted_expiring.append({"id": i.get('id', 'N/A'), "name": i.get('item_name', 'Unknown'), "expiry_date": i.get('expiry_date', 'N/A'), "days_until_expiry": i.get('days_until_expiry', 'N/A'), "quantity": i.get('quantity', 'N/A')})
    formatted_low_stock = []
    for i in low_stock_list:
         if isinstance(i, dict): formatted_low_stock.append({"id": i.get('id', 'N/A'), "name": i.get('item_name', 'Unknown'), "quantity": i.get('quantity', 'N/A'), "reorder_level": i.get('reorder_level', 'N/A')})
    return {"expiring_soon": formatted_expiring, "low_stock": formatted_low_stock}


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    # Create necessary JSON files if they don't exist
    for filename in [INVENTORY_FILE, BILLING_FILE, ROSTER_FILE, PROTOCOLS_FILE, PROTOCOL_CHUNKS_FILE]: # Use new chunks filename
        if not os.path.exists(filename):
            save_json(filename, [])
            print(f"Created empty file: {filename}")
    port_to_run = 8002
    print(f"Starting server on http://0.0.0.0:{port_to_run}")
    uvicorn.run("main:app", host="0.0.0.0", port=port_to_run, reload=True) # Use string for app object

