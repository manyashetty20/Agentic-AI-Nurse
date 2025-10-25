import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date
# import plotly.express as px # Not used
# import plotly.graph_objects as go # Not used

# Configuration
API_URL = "http://localhost:8002" # Ensure this matches your backend port
st.set_page_config(
    page_title="Nurse Admin Dashboard",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
        border-bottom: 3px solid #1f77b4;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .alert-box {
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        color: #333; /* Ensure text is readable */
    }
    .alert-warning {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
    }
    .alert-danger {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
    }
    /* Style for buttons *inside* a form (like submit) */
    div[data-testid="stForm"] .stButton>button {
        width: 100%;
        background-color: #1f77b4;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        border: none;
        font-weight: bold;
        transition: background-color 0.2s;
    }
    div[data-testid="stForm"] .stButton>button:hover {
        background-color: #1557a0;
        cursor: pointer;
    }
    /* Style for buttons *outside* a form (like Add/Remove Item) */
    div:not([data-testid="stForm"]) > .stButton>button {
        background-color: #007bff; /* Different color for distinction */
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        border: none;
        font-weight: bold;
        transition: background-color 0.2s;
    }
    div:not([data-testid="stForm"]) > .stButton>button:hover {
        background-color: #0056b3;
        cursor: pointer;
    }
    /* Improve Expander styling */
     .stExpander > div:first-child > details > summary {
        font-weight: bold;
     }
</style>
""", unsafe_allow_html=True)

# Utility Functions
def make_request(method, endpoint, **kwargs):
    """Make API request with error handling"""
    try:
        url = f"{API_URL}{endpoint}"
        response = requests.request(method, url, **kwargs, timeout=15) # Increased timeout slightly
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            if response.status_code in [200, 204]:
                return {"message": "Success (No content)"}
            else:
                 st.error(f"❌ API Error: Received non-JSON response (Status: {response.status_code})")
                 return None
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Cannot connect to API at {API_URL}. Is the backend ('main.py') running on port 8002?")
        return None
    except requests.exceptions.Timeout:
        st.error("⏱️ API Request timed out. The server might be busy or unresponsive.")
        return None
    except requests.exceptions.HTTPError as e:
        detail = "Unknown error"
        try: detail = e.response.json().get('detail', f"HTTP Status {e.response.status_code}")
        except: detail = f"HTTP Status {e.response.status_code}"
        st.error(f"❌ API Error: {detail}")
        return None
    except Exception as e:
        st.error(f"❌ An unexpected error occurred: {str(e)}")
        return None

def format_currency(amount):
    """Format amount as Indian Rupee"""
    if amount is None: return "₹0.00"
    try: return f"₹{float(amount):,.2f}"
    except (ValueError, TypeError): return "₹ N/A"

def format_date(date_str, fmt="%d %b %Y"):
    """Format ISO date/datetime string"""
    if not date_str: return "N/A"
    try:
        date_str = date_str.replace('Z', '+00:00')
        dt_obj = datetime.fromisoformat(date_str)
        return dt_obj.strftime(fmt)
    except (ValueError, TypeError): return date_str

# Sidebar Navigation
st.sidebar.image("https://img.icons8.com/fluency/96/hospital-3.png", width=100)
st.sidebar.markdown("## 🏥 Nurse Admin")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "💊 Inventory", "💳 Billing", "📅 Roster", "📋 Protocols"],
)

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip**: Use the Roster Generator for smart scheduling.")

# --- Initialize Session State for Bill Items ---
if 'bill_items' not in st.session_state:
    st.session_state.bill_items = [{'id': 0}] # Start with one item row

# Main Content
if page == "📊 Dashboard":
    # --- DASHBOARD CODE (Unchanged) ---
    st.markdown('<div class="main-header">📊 Admin Dashboard</div>', unsafe_allow_html=True)
    stats = make_request("GET", "/analytics/dashboard/")
    if stats:
        cols = st.columns(4)
        inv_stats = stats.get('inventory', {})
        bill_stats = stats.get('billing', {})
        cols[0].metric("Total Items", inv_stats.get('total_items', 0), delta=f"-{inv_stats.get('out_of_stock', 0)} out of stock" if inv_stats.get('out_of_stock', 0) > 0 else "All in stock", delta_color="inverse" if inv_stats.get('out_of_stock', 0) > 0 else "normal")
        cols[1].metric("Low Stock Items", inv_stats.get('low_stock', 0), delta="Needs attention" if inv_stats.get('low_stock', 0) > 0 else "Good", delta_color="inverse" if inv_stats.get('low_stock', 0) > 0 else "normal")
        cols[2].metric("30-Day Revenue", format_currency(bill_stats.get('total_revenue_30d', 0)), delta=f"{bill_stats.get('total_bills_30d', 0)} bills")
        cols[3].metric("Pending Bills", bill_stats.get('pending_bills', 0), delta="Requires action" if bill_stats.get('pending_bills', 0) > 0 else "All clear", delta_color="inverse" if bill_stats.get('pending_bills', 0) > 0 else "normal")
        st.markdown("<hr/>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("⚠️ Inventory Alerts")
            alerts = make_request("GET", "/analytics/inventory-alerts/")
            if alerts:
                low_stock = alerts.get('low_stock', [])
                expiring = alerts.get('expiring_soon', [])
                if low_stock:
                    st.markdown("**🔴 Low Stock Items:**")
                    for item in low_stock: st.markdown(f'<div class="alert-box alert-danger"><b>{item.get("name", "N/A")}</b><br>Current: {item.get("quantity", "N/A")} | Reorder Level: {item.get("reorder_level", "N/A")}</div>', unsafe_allow_html=True)
                else: st.success("✅ All items above reorder level")
                st.markdown("<br>", unsafe_allow_html=True)
                if expiring:
                    st.markdown("**🟡 Expiring Soon (30 days):**")
                    for item in expiring: st.markdown(f'<div class="alert-box alert-warning"><b>{item.get("name", "N/A")}</b><br>Expires: {format_date(item.get("expiry_date", "N/A"))} ({item.get("days_until_expiry", "?")} days)</div>', unsafe_allow_html=True)
                else: st.success("✅ No items expiring in next 30 days")
            else: st.warning("Could not load inventory alerts.")
        with col2:
            st.subheader("📈 Recent Billing Activity")
            recent_bills = make_request("GET", "/billing/")
            if recent_bills:
                try:
                    df = pd.DataFrame(recent_bills)
                    df['date_dt'] = pd.to_datetime(df['date'])
                    recent_bills_sorted = df.sort_values('date_dt', ascending=False).head(5).to_dict('records')
                except Exception as e: recent_bills_sorted = recent_bills[:5]
                if recent_bills_sorted:
                    for bill in recent_bills_sorted:
                        status_color = "🟢 Paid" if bill.get('payment_status') == 'paid' else "🟡 Pending" if bill.get('payment_status') == 'pending' else "🔴 Cancelled"
                        st.markdown(f"**{status_color} - {bill.get('patient_name', 'N/A')}** - {format_currency(bill.get('total_amount', 0))}<br><small>Bill #{bill.get('id', 'N/A')} | {format_date(bill.get('date', ''), '%d %b %y')} | Dr. {bill.get('doctor_name', 'N/A')}</small>", unsafe_allow_html=True)
                        st.markdown("---")
                else: st.info("No recent billing activity found.")
            else: st.warning("Could not load recent bills.")

elif page == "💊 Inventory":
    # --- INVENTORY CODE (Unchanged) ---
    st.markdown('<div class="main-header">💊 Inventory Management</div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📋 All Items", "➕ Add Item", "📊 Reports"])
    inventory_data_for_edit = make_request("GET", "/inventory/") or []
    for item_to_edit in inventory_data_for_edit:
        item_id = item_to_edit.get('id')
        if f'edit_item_{item_id}' in st.session_state and st.session_state[f'edit_item_{item_id}']:
             st.subheader(f"✏️ Editing: {item_to_edit.get('item_name', '')}")
             with st.form(f"edit_form_{item_id}"):
                col1, col2 = st.columns(2)
                with col1:
                    edit_name = st.text_input("Item Name*", value=item_to_edit.get('item_name', ''))
                    edit_manufacturer = st.text_input("Manufacturer*", value=item_to_edit.get('manufacturer', ''))
                    edit_price = st.number_input("Price (₹)*", value=float(item_to_edit.get('price', 0.0)), min_value=0.01, step=0.01, format="%.2f")
                    edit_quantity = st.number_input("Quantity*", value=int(item_to_edit.get('quantity', 0)), min_value=0, step=1)
                with col2:
                    category_options = ["Medicine", "Equipment", "Supplies", "Other"]
                    current_category = item_to_edit.get('category', 'Other')
                    if current_category not in category_options: category_options.append(current_category)
                    cat_index = category_options.index(current_category)
                    edit_category = st.selectbox("Category", category_options, index=cat_index)
                    edit_unit = st.text_input("Unit", value=item_to_edit.get('unit', 'units'))
                    current_expiry_val = None
                    try:
                        if item_to_edit.get('expiry_date'): current_expiry_val = date.fromisoformat(item_to_edit.get('expiry_date').split('T')[0])
                    except: pass
                    edit_expiry_date = st.date_input("Expiry Date (Optional)", value=current_expiry_val)
                    edit_reorder = st.number_input("Reorder Level", value=int(item_to_edit.get('reorder_level', 10)), min_value=0, step=1)
                edit_notes = st.text_area("Notes", value=item_to_edit.get('notes', ''))
                save_edit = st.form_submit_button("💾 Save Changes")
                cancel_edit = st.form_submit_button("❌ Cancel")
                if save_edit:
                    if not edit_name or not edit_manufacturer or edit_price is None: st.error("Please fill in required fields.")
                    else:
                        updated_data = {"item_name": edit_name, "manufacturer": edit_manufacturer, "price": float(edit_price), "quantity": int(edit_quantity), "category": edit_category, "unit": edit_unit, "expiry_date": edit_expiry_date.isoformat() if edit_expiry_date else None, "reorder_level": int(edit_reorder), "notes": edit_notes if edit_notes else None}
                        result = make_request("PUT", f"/inventory/{item_id}", json=updated_data)
                        if result: st.success("Item updated successfully!"); del st.session_state[f'edit_item_{item_id}']; st.rerun()
                if cancel_edit: del st.session_state[f'edit_item_{item_id}']; st.rerun()
             st.markdown("---")
    with tab1:
        st.subheader("All Inventory Items")
        col1, col2, col3 = st.columns([2, 2, 1])
        search_term = col1.text_input("🔍 Search items", placeholder="Search by name or manufacturer")
        all_categories = ["All"] + sorted(list(set(i.get('category', 'Other') for i in inventory_data_for_edit if isinstance(i, dict) and i.get('category'))))
        category_filter = col2.selectbox("Category", all_categories)
        col3.write(""); col3.write("")
        show_low_stock = col3.checkbox("Low Stock Only")
        inventory_display = inventory_data_for_edit
        if inventory_display:
            if search_term:
                search_lower = search_term.lower()
                inventory_display = [i for i in inventory_display if isinstance(i, dict) and (search_lower in i.get('item_name', '').lower() or search_lower in i.get('manufacturer', '').lower())]
            if category_filter != "All": inventory_display = [i for i in inventory_display if isinstance(i,dict) and i.get('category', 'Other') == category_filter]
            if show_low_stock: inventory_display = [i for i in inventory_display if isinstance(i,dict) and i.get('quantity', 0) <= i.get('reorder_level', 10)]
            if inventory_display:
                for item in inventory_display:
                    item_id = item.get('id')
                    if not item_id or (f'edit_item_{item_id}' in st.session_state and st.session_state[f'edit_item_{item_id}']): continue
                    stock_status = '🔴 Low Stock' if item.get('quantity', 0) <= item.get('reorder_level', 10) else '🟢 In Stock'
                    with st.expander(f"{stock_status} | {item.get('item_name', 'N/A')} | Stock: {item.get('quantity', 'N/A')}"):
                        col1, col2, col3 = st.columns(3)
                        with col1: st.markdown(f"**Manufacturer:** {item.get('manufacturer', 'N/A')}\n\n**Category:** {item.get('category', 'N/A')}\n\n**Unit:** {item.get('unit', 'units')}")
                        with col2: st.markdown(f"**Price:** {format_currency(item.get('price'))}\n\n**Quantity:** {item.get('quantity', 'N/A')}\n\n**Reorder Level:** {item.get('reorder_level', 10)}")
                        with col3:
                            expiry = item.get('expiry_date', 'N/A')
                            if expiry and expiry != 'N/A':
                                try:
                                    exp_date = date.fromisoformat(expiry.split('T')[0])
                                    days_left = (exp_date - date.today()).days
                                    if days_left <= 0: st.markdown(f"**<span style='color:red;'>🔴 EXPIRED: {format_date(expiry)}</span>**", unsafe_allow_html=True)
                                    elif days_left < 30: st.markdown(f"**<span style='color:orange;'>🟡 Expiry:** {format_date(expiry)} ({days_left} days)</span>**", unsafe_allow_html=True)
                                    else: st.markdown(f"**Expiry:** {format_date(expiry)}")
                                except: st.markdown(f"**Expiry:** {expiry} (invalid format)")
                            else: st.markdown(f"**Expiry:** N/A")
                        if item.get('notes'): st.info(f"📝 Notes: {item.get('notes')}")
                        b_col1, b_col2, b_col3 = st.columns([1,1,5])
                        with b_col1:
                            if st.button("✏️ Edit", key=f"edit_{item_id}", help="Edit this item"): st.session_state[f'edit_item_{item_id}'] = True; st.rerun()
                        with b_col2:
                            if st.button("🗑️ Delete", key=f"del_{item_id}", help="Delete this item"):
                                if make_request("DELETE", f"/inventory/{item_id}"): st.success("Item deleted successfully!"); st.rerun()
            else: st.info("No items match your filters.")
        else: st.info("Inventory is empty. Add items using the 'Add Item' tab.")
    with tab2:
        st.subheader("Add New Inventory Item")
        with st.form("add_inventory_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                item_name = st.text_input("Item Name*", placeholder="e.g., Paracetamol 500mg")
                manufacturer = st.text_input("Manufacturer*", placeholder="e.g., XYZ Pharma")
                price = st.number_input("Price (₹)*", min_value=0.01, step=0.01, format="%.2f")
                quantity = st.number_input("Quantity*", min_value=0, step=1, value=0)
            with col2:
                category = st.selectbox("Category", ["Medicine", "Equipment", "Supplies", "Other"])
                unit = st.text_input("Unit", value="units", placeholder="e.g., tablets, boxes, ml")
                expiry_date_val = st.date_input("Expiry Date (Optional)", value=None)
                reorder_level = st.number_input("Reorder Level", min_value=0, value=10, step=1)
            notes = st.text_area("Notes (Optional)", placeholder="Additional information")
            submitted = st.form_submit_button("➕ Add Item", use_container_width=True)
            if submitted:
                if not item_name or not manufacturer or price is None or quantity is None: st.error("Please fill in all required (*) fields.")
                else:
                    item_data = {"item_name": item_name, "manufacturer": manufacturer, "price": float(price), "quantity": int(quantity), "category": category, "unit": unit, "expiry_date": expiry_date_val.isoformat() if expiry_date_val else None, "reorder_level": int(reorder_level), "notes": notes if notes else None}
                    result = make_request("POST", "/inventory/", json=item_data)
                    if result: st.success(f"✅ Item '{item_name}' added successfully!"); st.balloons()
    with tab3:
        st.subheader("Inventory Reports")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📉 Low Stock Items**")
            low_stock = make_request("GET", "/inventory/low-stock/")
            if low_stock: st.dataframe(pd.DataFrame(low_stock)[['item_name', 'quantity', 'reorder_level']], use_container_width=True, hide_index=True)
            elif low_stock is not None: st.success("All items above reorder level")
        with col2:
            st.markdown("**⏰ Expiring Soon (30 days)**")
            expiring = make_request("GET", "/inventory/expiring/", params={"days": 30})
            if expiring: st.dataframe(pd.DataFrame(expiring)[['item_name', 'expiry_date', 'days_until_expiry', 'quantity']], use_container_width=True, hide_index=True)
            elif expiring is not None: st.success("No items expiring soon")

elif page == "💳 Billing":
    # --- BILLING CODE (With form fix) ---
    st.markdown('<div class="main-header">💳 Billing Management</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 All Bills", "➕ Create Bill"])
    with tab1:
        st.subheader("All Bills")
        col1, col2, col3 = st.columns(3)
        status_filter = col1.selectbox("Payment Status", ["All", "Pending", "Paid", "Cancelled"])
        search_patient = col2.text_input("🔍 Search Patient/Doctor", placeholder="Name or ID")
        show_recent = col3.selectbox("Show", ["All Time", "Last 7 Days", "Last 30 Days"])
        bills = make_request("GET", "/billing/")
        if bills:
            filtered_bills = bills
            if status_filter != "All": filtered_bills = [b for b in filtered_bills if b.get('payment_status', '').lower() == status_filter.lower()]
            if search_patient:
                search_lower = search_patient.lower()
                filtered_bills = [b for b in filtered_bills if search_lower in b.get('patient_name', '').lower() or search_lower in b.get('patient_id', '').lower() or search_lower in b.get('doctor_name', '').lower()]
            if show_recent != "All Time":
                days = 7 if show_recent == "Last 7 Days" else 30
                cutoff = (datetime.now() - timedelta(days=days)).date()
                filtered_bills = [b for b in filtered_bills if date.fromisoformat(b.get('date','2000-01-01').split('T')[0]) >= cutoff]
            if filtered_bills:
                total_billed = sum(b.get('total_amount', 0) for b in filtered_bills if b.get('payment_status') != 'cancelled')
                total_paid = sum(b.get('total_amount', 0) for b in filtered_bills if b.get('payment_status') == 'paid')
                st.info(f"📊 **{len(filtered_bills)} bills displayed** | **Total Billed: {format_currency(total_billed)}** | **Total Paid: {format_currency(total_paid)}**")
                for bill in filtered_bills:
                    status_emoji = "🟢" if bill.get('payment_status') == 'paid' else "🟡" if bill.get('payment_status') == 'pending' else "🔴"
                    with st.expander(f"{status_emoji} Bill #{bill.get('id','N/A')} | {bill.get('patient_name','N/A')} | {format_currency(bill.get('total_amount', 0))}"):
                        col1, col2 = st.columns(2)
                        with col1: st.markdown(f"**Patient ID:** {bill.get('patient_id', 'N/A')}\n\n**Patient Name:** {bill.get('patient_name', 'N/A')}\n\n**Doctor:** Dr. {bill.get('doctor_name', 'N/A')}\n\n**Date:** {format_date(bill.get('date', 'N/A'))}")
                        with col2:
                            st.markdown(f"**Status:** {bill.get('payment_status', 'N/A').upper()}")
                            if bill.get('payment_method'): st.markdown(f"**Payment Method:** {bill.get('payment_method')}")
                            st.markdown(f"**Total Amount:** {format_currency(bill.get('total_amount', 0))}")
                            st.caption(f"Transaction Time: {format_date(bill.get('transaction_time', ''), '%d %b %Y %H:%M')}")
                        st.markdown("**📦 Items Billed:**")
                        items_df = pd.DataFrame(bill.get('items', []))
                        if not items_df.empty:
                            items_df_display = items_df[['item_name', 'manufacturer', 'quantity', 'unit_price', 'subtotal']]
                            items_df_display.columns = ['Item', 'Manufacturer', 'Qty', 'Unit Price', 'Subtotal']
                            items_df_display['Unit Price'] = items_df_display['Unit Price'].apply(format_currency)
                            items_df_display['Subtotal'] = items_df_display['Subtotal'].apply(format_currency)
                            st.dataframe(items_df_display, use_container_width=True, hide_index=True)
                        else: st.write("No items listed.")
                        if bill.get('notes'): st.info(f"📝 Notes: {bill['notes']}")
                        if bill.get('payment_status') == 'pending':
                             st.markdown("---"); st.markdown("**Update Payment:**")
                             update_cols = st.columns([2,1])
                             payment_method = update_cols[0].selectbox("Payment Method", ["Cash", "Card", "UPI", "Bank Transfer"], key=f"payment_method_{bill.get('id')}")
                             if update_cols[1].button("✅ Mark as Paid", key=f"pay_{bill.get('id')}", use_container_width=True):
                                 result = make_request("PUT", f"/billing/{bill.get('id')}/payment", params={"payment_status": "paid", "payment_method": payment_method})
                                 if result: st.success("Payment updated!"); st.rerun()
                             if st.button("❌ Cancel Bill", key=f"cancel_{bill.get('id')}", use_container_width=True):
                                result = make_request("PUT", f"/billing/{bill.get('id')}/payment", params={"payment_status": "cancelled"})
                                if result: st.warning("Bill marked as cancelled."); st.rerun()
            else: st.info("No bills match your filters.")
        elif bills is not None: st.info("No bills recorded yet.")
    with tab2:
        st.subheader("➕ Create New Bill")
        available_items_data = make_request("GET", "/inventory/available")
        if available_items_data:
            item_options = {f"{item['item_name']} ({item['manufacturer']}) - {format_currency(item['price'])} | Stock: {item['quantity_available']}": item for item in available_items_data}
            item_labels = list(item_options.keys())
            
            # --- Define form elements FIRST ---
            with st.form("create_bill_form", clear_on_submit=True):
                st.markdown("**👤 Patient Information**")
                p_cols = st.columns(3)
                patient_id = p_cols[0].text_input("Patient ID*", placeholder="e.g., P001")
                patient_name = p_cols[1].text_input("Patient Name*", placeholder="e.g., John Doe")
                doctor_name = p_cols[2].text_input("Doctor Name*", placeholder="e.g., Dr. Smith")
                
                st.markdown("---")
                st.markdown("**📦 Add Items to Bill**")
                
                item_rows = st.session_state.bill_items
                total_preview = 0.0
                
                for i in range(len(item_rows)):
                    st.markdown(f"**Item {i+1}**")
                    cols = st.columns([4, 1, 1, 1])
                    item_key = f"item_select_{i}"; qty_key = f"item_qty_{i}"
                    if item_key not in st.session_state: st.session_state[item_key] = item_labels[0] if item_labels else None
                    if qty_key not in st.session_state: st.session_state[qty_key] = 1
                    
                    # Ensure existing session state value is valid
                    if st.session_state[item_key] not in item_labels:
                        st.session_state[item_key] = item_labels[0] if item_labels else None
                        
                    selected_label = cols[0].selectbox(f"Select Item*", options=item_labels, key=item_key, label_visibility="collapsed")
                    selected_item_data = item_options.get(selected_label)
                    
                    if selected_item_data:
                        max_qty = selected_item_data['quantity_available']
                        # Ensure current quantity isn't > max
                        current_qty_val = st.session_state[qty_key]
                        if current_qty_val > max_qty:
                            current_qty_val = max_qty

                        st.session_state[qty_key] = cols[1].number_input(f"Qty (Max {max_qty})", min_value=1, max_value=max_qty, value=current_qty_val, key=f"qty_input_{i}", label_visibility="collapsed")
                        quantity = st.session_state[qty_key]
                        item_price = selected_item_data['price']
                        item_total = item_price * quantity
                        total_preview += item_total
                        cols[2].text_input("Unit Price", value=format_currency(item_price), disabled=True, key=f"price_{i}", label_visibility="collapsed")
                        cols[3].text_input("Subtotal", value=format_currency(item_total), disabled=True, key=f"subtotal_{i}", label_visibility="collapsed")
                    else:
                        cols[0].selectbox("Select Item*", options=["No items available"], disabled=True, label_visibility="collapsed")
                        cols[1].number_input("Qty", value=1, disabled=True, key=f"qty_input_{i}", label_visibility="collapsed")
                        cols[2].text_input("Unit Price", value="N/A", disabled=True, key=f"price_{i}", label_visibility="collapsed")
                        cols[3].text_input("Subtotal", value="N/A", disabled=True, key=f"subtotal_{i}", label_visibility="collapsed")
                
                st.markdown("---")
                notes = st.text_area("Notes (Optional)", placeholder="Billing notes")
                st.markdown(f"### **Grand Total: {format_currency(total_preview)}**")
                
                submitted = st.form_submit_button("💳 Create Bill", use_container_width=True)
                
                if submitted:
                    if not patient_id or not patient_name or not doctor_name: st.error("Please fill in all required patient fields.")
                    elif not item_labels: st.error("Cannot create bill. No items available in inventory.")
                    else:
                        final_bill_items = []
                        valid_submission = True
                        for i in range(len(st.session_state.bill_items)):
                            label = st.session_state.get(f"item_select_{i}")
                            qty = st.session_state.get(f"item_qty_{i}", 1)
                            item_data = item_options.get(label)
                            if not item_data: st.error(f"Invalid item selected for row {i+1}."); valid_submission = False; break
                            final_bill_items.append({"item_id": item_data['id'], "quantity": qty})
                        if valid_submission:
                            bill_payload = {"patient_id": patient_id, "patient_name": patient_name, "doctor_name": doctor_name, "items": final_bill_items, "notes": notes if notes else None}
                            result = make_request("POST", "/billing/", json=bill_payload)
                            if result:
                                st.success(f"✅ Bill #{result.get('id')} created! Total: {format_currency(result.get('total_amount', 0))}"); st.balloons()
                                st.session_state.bill_items = [{'id': 0}] # Reset
            
            # --- FIX: Buttons are MOVED OUTSIDE the st.form block ---
            st.markdown("---") 
            add_remove_cols = st.columns([1, 1, 4])
            with add_remove_cols[0]:
                if st.button("➕ Add Item Row", key="add_bill_item_outside"):
                    st.session_state.bill_items.append({'id': len(st.session_state.bill_items)})
                    st.rerun()
            with add_remove_cols[1]:
                if len(st.session_state.bill_items) > 1:
                    if st.button("➖ Remove Last Row", key="remove_bill_item_outside"):
                        st.session_state.bill_items.pop()
                        # Clear session state for the removed item's widgets
                        last_id = len(st.session_state.bill_items)
                        if f"item_select_{last_id}" in st.session_state: del st.session_state[f"item_select_{last_id}"]
                        if f"item_qty_{last_id}" in st.session_state: del st.session_state[f"item_qty_{last_id}"]
                        st.rerun()
        else:
            st.warning("⚠️ Inventory is empty or unavailable. Cannot create bills.")

elif page == "📅 Roster":
    st.markdown('<div class="main-header">📅 Staff Roster Management</div>', unsafe_allow_html=True)
    
    # --- FIX: Remove 'Add Shift' tab, add 'Generate Roster' tab ---
    tab_titles = ["📋 All Shifts", "📆 2-Week View", "🤖 Generate Roster"]
    tab1, tab2, tab3 = st.tabs(tab_titles)
    
    with tab1:
        st.subheader("All Roster Entries")
        col1, col2 = st.columns(2)
        staff_filter = col1.text_input("🔍 Search Staff", placeholder="Staff name")
        date_filter_val = col2.date_input("Filter by Date (Optional)", value=None)
        
        roster_list = make_request("GET", "/roster/")
        
        if roster_list:
            filtered_roster = roster_list
            if staff_filter: filtered_roster = [r for r in filtered_roster if staff_filter.lower() in r.get('staff_name', '').lower()]
            if date_filter_val: date_str = date_filter_val.isoformat(); filtered_roster = [r for r in filtered_roster if r.get('shift_date') == date_str]
            
            if filtered_roster:
                roster_by_date = {}
                for entry in filtered_roster:
                    shift_date_str = entry.get('shift_date', 'Unknown Date')
                    if shift_date_str not in roster_by_date: roster_by_date[shift_date_str] = []
                    roster_by_date[shift_date_str].append(entry)
                
                for shift_date_str in sorted(roster_by_date.keys(), reverse=True):
                    try:
                        date_obj = date.fromisoformat(shift_date_str.split('T')[0])
                        day_name = date_obj.strftime("%A, %d %b %Y")
                    except:
                         day_name = shift_date_str

                    with st.expander(f"📅 {day_name} - {len(roster_by_date[shift_date_str])} shifts"):
                        for entry in sorted(roster_by_date[shift_date_str], key=lambda x: x.get('start_time', '00:00')):
                            cols = st.columns([2, 1, 2, 1])
                            with cols[0]:
                                availability = "🟢 Available" if entry.get('is_available', True) else "🔴 Unavailable/Leave"
                                st.markdown(f"**{entry.get('staff_name', 'N/A')}**")
                                st.caption(f"{entry.get('role', 'Staff')} | {availability}")
                            cols[1].markdown(f"**Shift:**<br>{entry.get('shift_type', 'N/A')}", unsafe_allow_html=True)
                            cols[2].markdown(f"**Time:**<br>{entry.get('start_time', '--:--')} - {entry.get('end_time', '--:--')}", unsafe_allow_html=True)
                            with cols[3]:
                                if st.button("🗑️ Delete", key=f"del_roster_{entry.get('id', 'N/A')}", help="Delete this shift"):
                                    if make_request("DELETE", f"/roster/{entry.get('id')}"):
                                        st.success("Deleted!")
                                        st.rerun()
                            if entry.get('notes'): st.info(f"📝 Notes: {entry['notes']}")
                            st.markdown("---")
            else: st.info("No shifts match your filters.")
        elif roster_list is not None: st.info("No roster entries found.")

    with tab2:
        # --- MOVED 2-Week View ---
        st.subheader("📆 Next 2 Weeks Schedule")
        
        two_week_roster_data = make_request("GET", "/roster/two-weeks/")
        
        if two_week_roster_data:
            roster_by_day = {}
            for entry in two_week_roster_data:
                d_str = entry.get('shift_date')
                if d_str not in roster_by_day: roster_by_day[d_str] = []
                roster_by_day[d_str].append(entry)

            today = date.today()
            dates_in_view = [today + timedelta(days=i) for i in range(14)]
            
            for week_start_idx in range(0, 14, 7):
                cols = st.columns(7)
                for day_idx in range(7):
                    current_idx = week_start_idx + day_idx
                    if current_idx >= 14: break

                    current_date = dates_in_view[current_idx]
                    date_str = current_date.isoformat()
                    shifts_today = roster_by_day.get(date_str, [])
                    
                    with cols[day_idx]:
                        header_style = "background-color:#1f77b4; color:white; padding: 5px; border-radius: 5px; text-align:center; margin-bottom: 5px;" if current_date == today else "padding: 5px; border-bottom: 1px solid #ccc; margin-bottom: 5px; text-align:center;"
                        st.markdown(f"<div style='{header_style}'><b>{current_date.strftime('%a %d')}</b></div>", unsafe_allow_html=True)
                        
                        # --- FIX: Filter out Leave/Rest shifts ---
                        working_shifts_today = [
                            s for s in shifts_today 
                            if s.get('is_available', True) and s.get('shift_type') not in ['Leave', 'Rest']
                        ]
                        
                        if working_shifts_today:
                            st.markdown(f"<small>{len(working_shifts_today)} working shifts</small>", unsafe_allow_html=True)
                            for shift in sorted(working_shifts_today, key=lambda x: x.get('start_time','00:00')):
                                availability = "🟢" # Always green, as requested
                                st.caption(f"{availability} {shift.get('staff_name','?')} ({shift.get('shift_type','?')})")
                        else:
                            st.caption("No working shifts")
                if week_start_idx == 0: st.markdown("---")

        elif two_week_roster_data is not None:
             st.info("No shifts scheduled for the next 2 weeks.")

    with tab3:
        # --- NEW Roster Generator ---
        st.subheader("🤖 Auto-Generate Roster")
        st.info("Define your staff and let the agent generate a schedule. This respects rest rules (no Night-to-Morning, max 6 consecutive work days) and assigns one random day off per week.")

        # Get existing staff names to pre-fill
        all_roster_data = make_request("GET", "/roster/")
        if all_roster_data:
            staff_names_list = sorted(list(set(e.get('staff_name') for e in all_roster_data if e.get('staff_name'))))
            default_staff_text = "\n".join(staff_names_list)
        else:
            default_staff_text = "Nurse Anna\nDr. Ben\nTech Carla\nAdmin Dave\nNurse Leo\nNurse Maya\nDr. Patel\nNurse Riddhi\nDr. Mohan\nTech Sarah\nAdmin Frank\nNurse David\nDr. Priya" # Full fallback list

        with st.form("generate_roster_form"):
            st.markdown("**1. Define Staff**")
            
            staff_names_raw = st.text_area(
                "Staff Names (one per line)",
                value=default_staff_text,
                height=200,
                help="Enter the names of all staff to be included in scheduling."
            )
            
            st.markdown("**2. Define Schedule Period & Shift Needs**")
            g_cols = st.columns(2)
            start_date_val = g_cols[0].date_input("Start Date", value=date.today() + timedelta(days=1))
            num_days = g_cols[1].number_input("Number of Days to Generate", min_value=7, max_value=30, value=14, step=7)

            s_cols = st.columns(3)
            morning_needed = s_cols[0].number_input("Morning Shifts Needed / Day", min_value=0, value=1)
            afternoon_needed = s_cols[1].number_input("Afternoon Shifts Needed / Day", min_value=0, value=1)
            night_needed = s_cols[2].number_input("Night Shifts Needed / Day", min_value=0, value=1)

            st.warning("Note: This will clear and regenerate all non-leave shifts in the selected date range.")
            submitted = st.form_submit_button("🤖 Generate & Save Roster", use_container_width=True)

            if submitted:
                # --- Parse UI inputs into API payload ---
                staff_list = [name.strip() for name in staff_names_raw.split('\n') if name.strip()]
                
                if not staff_list:
                    st.error("Please enter at least one staff name.")
                elif len(staff_list) < (morning_needed + afternoon_needed + night_needed):
                    st.error(f"Not enough staff ({len(staff_list)}) to cover the required daily shifts ({morning_needed + afternoon_needed + night_needed}). Add more staff or reduce shift needs.")
                else:
                    # Build final payload
                    payload = {
                        "staff_names": staff_list,
                        "start_date": start_date_val.isoformat(),
                        "num_days": num_days,
                        "shifts_per_day": {
                            "Morning": morning_needed,
                            "Afternoon": afternoon_needed,
                            "Night": night_needed
                        }
                    }
                    
                    with st.spinner(f"Generating {num_days}-day roster... This may take a moment."):
                        result = make_request("POST", "/roster/generate", json=payload)
                    
                    if result:
                        st.success(result.get('message', 'Roster generated!'))
                        st.balloons()
                        if result.get('new_entries_added'):
                             st.info(f"Added {len(result['new_entries_added'])} new shifts (including leave/rest days).")
                        st.info("Refresh the 'All Shifts' or '2-Week View' tabs to see the full schedule.")


elif page == "📋 Protocols":
    # --- PROTOCOLS CODE (With content_preview fix) ---
    st.markdown('<div class="main-header">📋 Medical Protocols</div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📚 All Protocols", "➕ Add Protocol", "🤖 Ask AI"])
    
    with tab1:
        st.subheader("All Protocols")
        search_query = st.text_input("🔍 Search Protocols", placeholder="Search title, category, tags...")
        
        protocols_list = make_request("GET", "/protocols/")
        
        if protocols_list:
            filtered_protocols = protocols_list
            if search_query:
                search_lower = search_query.lower()
                filtered_protocols = [
                    p for p in filtered_protocols if isinstance(p, dict) and
                    (search_lower in p.get('title', '').lower() or
                     search_lower in p.get('category', '').lower() or
                     search_lower in p.get('tags', '').lower())
                ]
            
            if filtered_protocols:
                # Group by category
                protocols_by_category = {}
                for p in filtered_protocols:
                    cat = p.get('category', 'General')
                    if cat not in protocols_by_category: protocols_by_category[cat] = []
                    protocols_by_category[cat].append(p)
                
                for cat in sorted(protocols_by_category.keys()):
                    st.markdown(f"#### {cat}")
                    for protocol in sorted(protocols_by_category[cat], key=lambda x: x.get('title','')):
                        protocol_id = protocol.get('id')
                        with st.expander(f"📄 {protocol.get('title', 'N/A')}"):
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                if protocol.get('tags'): st.caption(f"Tags: {protocol['tags']}")
                                st.markdown("**Preview:**")
                                # --- THIS IS THE FIX ---
                                content_preview = protocol.get('content_preview', 'No preview available.')
                                st.markdown(f"> {content_preview}") # Use blockquote for preview
                                # --- END FIX ---
                                if protocol.get('filename'): st.caption(f"📎 Source: {protocol['filename']}")
                                st.caption(f"Added: {format_date(protocol.get('created_at', ''))}")
                            with col2:
                                if st.button("🗑️ Delete", key=f"del_protocol_{protocol_id}", help="Delete this protocol"):
                                    if make_request("DELETE", f"/protocols/{protocol_id}"):
                                        st.success("Protocol deleted!")
                                        st.rerun()
            else:
                st.info("No protocols match your search.")
        elif protocols_list is not None:
             st.info("No protocols found. Add some first!")
    
    with tab2:
        st.subheader("➕ Add New Protocol")
        upload_method = st.radio("Add Method", ["📄 Upload PDF", "✍️ Manual Entry"], horizontal=True)
        
        if upload_method == "📄 Upload PDF":
            with st.form("upload_pdf_form", clear_on_submit=True):
                st.info("Upload a PDF file. The system will extract the text, chunk it, and make it searchable.")
                
                uploaded_file = st.file_uploader("Choose PDF file*", type=['pdf'])
                col1, col2 = st.columns(2)
                title = col1.text_input("Protocol Title*", placeholder="Unique title")
                category = col2.text_input("Category", placeholder="e.g., Emergency")
                tags = st.text_input("Tags (comma-separated)", placeholder="cardiac, pediatric")
                submitted = st.form_submit_button("📤 Upload & Process PDF", use_container_width=True)
                
                if submitted:
                    if not uploaded_file or not title: st.error("PDF file and Title are required.")
                    else:
                        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), 'application/pdf')}
                        params = {'title': title, 'category': category or None, 'tags': tags or None}
                        try:
                            url = f"{API_URL}/protocols/upload-pdf/"
                            response = requests.post(url, files=files, params=params, timeout=60)
                            response.raise_for_status()
                            result = response.json()
                            st.success(f"✅ Protocol '{title}' uploaded & processed!")
                            st.caption(f"Chunks created: {result.get('chunk_count', 'N/A')}"); st.balloons()
                        except requests.exceptions.HTTPError as e:
                             try: detail = e.response.json().get('detail', str(e))
                             except: detail = str(e)
                             st.error(f"❌ Upload failed: {detail}")
                        except Exception as e: st.error(f"❌ Upload failed: {str(e)}")
        
        else: # Manual Entry
            with st.form("add_protocol_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                title = col1.text_input("Protocol Title*", placeholder="Unique title")
                category = col2.text_input("Category", placeholder="e.g., Medication")
                tags = st.text_input("Tags (comma-separated)", placeholder="pain, dosage")
                content = st.text_area("Protocol Content*", height=300, placeholder="Enter full text...")
                submitted = st.form_submit_button("➕ Add Manual Protocol", use_container_width=True)
                
                if submitted:
                    if not title or not content: st.error("Title and Content are required.")
                    else:
                        protocol_data = {"title": title, "category": category or None, "tags": tags or None, "content": content}
                        result = make_request("POST", "/protocols/", json=protocol_data)
                        if result:
                            st.success(f"✅ Protocol '{title}' added!")
                            st.caption(f"Chunks created: {result.get('chunk_count', 'N/A')}"); st.balloons()
    
    with tab3:
        st.subheader("🤖 AI Protocol Assistant")
        st.info("Ask questions about the uploaded protocols using Groq AI.")
        
        protocols_available = make_request("GET", "/protocols/") # Check if any exist
        
        if protocols_available:
            st.markdown(f"📚 **{len(protocols_available)} protocols available** for the AI to reference.")
            
            with st.form("ask_question_form"):
                question = st.text_area("Ask your question", placeholder="e.g., Steps for CPR?", height=100)
                submitted = st.form_submit_button("🔍 Ask AI", use_container_width=True)
                
                if submitted:
                    if not question: st.error("Please enter a question.")
                    else:
                        with st.spinner("🧠 AI is processing..."):
                            payload = {"question": question}
                            result = make_request("POST", "/protocols/ask/", json=payload)
                            
                            if result:
                                st.markdown("---"); st.markdown("#### 💬 AI Response:")
                                st.info(result.get('answer', 'No answer generated.'))
                                st.markdown("---"); st.markdown("#### 📖 Protocols Used:")
                                protocols_used = result.get('protocols_used_in_context', [])
                                if protocols_used:
                                    for p_meta in protocols_used: st.markdown(f"- **{p_meta.get('title', 'N/A')}** (ID: {p_meta.get('id', '?')}, Cat: {p_meta.get('category', 'N/A')})")
                                else: st.caption("No specific protocols identified.")
                                st.caption(f"ℹ️ Found {result.get('protocols_found', 0)} relevant chunks.")
        else:
            st.warning("⚠️ No protocols loaded. Add some first!")


# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #aaa; padding: 1rem; font-size: 0.9em;'>"
    "🏥 Nurse Admin Dashboard | Hackathon Project | FastAPI & Groq AI"
    "</div>",
    unsafe_allow_html=True
)