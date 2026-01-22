import streamlit as st
import pandas as pd
import io
import xlsxwriter

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Amazon Variation Creator", page_icon="📦")

st.title("📦 Amazon Variation Creator")
st.markdown("""
**Instructions:**
1. Download the **Plan Template** below if you need a starting point.
2. Upload your **Master Category Listing Report** (from Amazon).
3. Upload your completed **Planning File**.
4. Click **Run Automation** to get your clean upload files.
""")

# --- SIDEBAR: CONFIGURATION (Client Proofing) ---
st.sidebar.header("🔧 Column Settings")
st.sidebar.info("Adjust these if your Amazon file headers look different.")

# Default values based on our testing
col_sku = st.sidebar.text_input("SKU Header", value="SKU")
col_var_attr = st.sidebar.text_input("Variation Attribute (in Plan)", value="Size")
val_theme = st.sidebar.text_input("Theme Name (e.g. SizeName)", value="SizeName")

# --- TEMPLATE GENERATOR ---
def generate_template():
    # Creates a sample file for users to fill out
    data = {
        'SKU': ['NEW-PARENT-SKU', 'EXISTING-CHILD-SKU-1', 'EXISTING-CHILD-SKU-2'],
        'Size': ['', 'Small', 'Medium'], 
        'Color': ['', 'Red', 'Blue'],
        'Price': ['', '19.99', '19.99'],
        'Quantity': ['', '10', '15']
    }
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
        # Highlight the Parent SKU cell (A2) to indicate it's special
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        format_yellow = workbook.add_format({'bg_color': '#FFFF00'})
        worksheet.write('A2', 'NEW-PARENT-SKU', format_yellow)
    return buffer.getvalue()

# --- FILE UPLOADER SECTION ---
st.info("💡 **Tip:** Don't have a plan file yet? Download the template below.")
st.download_button(
    label="📄 Download Plan Template (.xlsx)",
    data=generate_template(),
    file_name="Plan_Template.xlsx",
    mime="application/vnd.ms-excel",
    help="Click to download a sample file with the correct headers."
)

st.markdown("---") 

col1, col2 = st.columns(2)
with col1:
    master_file = st.file_uploader("📂 1. Upload Master CLR (.xlsx)", type=['xlsx'])
with col2:
    plan_file = st.file_uploader("📂 2. Upload Plan File (.xlsx)", type=['xlsx'])

# --- LOGIC FUNCTIONS ---
def process_files(master, plan, sku_col, var_col, theme_name):
    # 1. READ MASTER (Smart Header Detection)
    # Read first 10 rows without header to scan
    df_temp = pd.read_excel(master, header=None, nrows=10)
    
    # Locate the SKU header
    header_idx = None
    for idx, row in df_temp.iterrows():
        # Convert to string to avoid type errors
        if sku_col in row.astype(str).values:
            header_idx = idx
            break
            
    if header_idx is None:
        return None, f"❌ Could not find column '{sku_col}' in the first 10 rows of Master File."

    # Reload Master with correct header
    master.seek(0) # Reset file pointer
    df_master = pd.read_excel(master, header=header_idx)
    
    # Clean Data
    df_master[sku_col] = df_master[sku_col].astype(str).str.strip()

    # Add a helper column to track which rows we change
    df_master['__TOUCHED__'] = False 
    
    # 2. READ PLAN
    df_plan = pd.read_excel(plan)
    if 'SKU' not in df_plan.columns:
        return None, "❌ Plan file must have a 'SKU' column (case-sensitive)."

    new_parents_to_add = []
    processed_count = 0
    
    try:
        # Row 1 (Index 0) is Parent, Rows 2+ are Children
        new_parent_sku = str(df_plan.iloc[0]['SKU']).strip()
        children_data = df_plan.iloc[1:].copy()
    except:
        return None, "❌ Plan file format invalid. Row 2 must be Parent, Rows 3+ Children."

    # --- PROCESS CHILDREN ---
    for index, row in children_
