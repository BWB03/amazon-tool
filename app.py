import streamlit as st
import pandas as pd
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Amazon Variation Creator", page_icon="📦")

st.title("📦 Amazon Variation Creator")
st.markdown("""
**Instructions:**
1. Upload your **Master Category Listing Report** (from Amazon).
2. Upload your **Planning File** (your new variations).
3. The app will auto-detect headers and merge the data.
4. Download the **Clean Upload File**.
""")

# --- SIDEBAR: CONFIGURATION (Client Proofing) ---
st.sidebar.header("🔧 Column Settings")
st.sidebar.info("Adjust these if your Amazon file headers look different.")

# Default values based on our testing
col_sku = st.sidebar.text_input("SKU Header", value="SKU")
col_var_attr = st.sidebar.text_input("Variation Attribute (in Plan)", value="Size")
val_theme = st.sidebar.text_input("Theme Name (e.g. SizeName)", value="SizeName")

# --- FILE UPLOADER SECTION ---
# --- TEMPLATE GENERATOR ---
def generate_template():
    # Create a dummy dataframe that matches your script's expectations
    # Row 1: Headers
    # Row 2: Parent SKU example (The script grabs Row 2 as the Parent)
    # Row 3+: Child SKUs (The script reads these as children)
    
    data = {
        'SKU': ['NEW-PARENT-SKU', 'EXISTING-CHILD-SKU-1', 'EXISTING-CHILD-SKU-2'],
        'Size': ['', 'Small', 'Medium'],  # Example Variation Column
        'Color': ['', 'Red', 'Blue'],     # Example Variation Column
        'Price': ['', '19.99', '19.99'],  # Optional helpful columns
        'Quantity': ['', '10', '15']      
    }
    df_template = pd.DataFrame(data)
    
    # Write to Excel memory buffer
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False)
        
        # Optional: Add a little note in the Excel file
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        # Add a comment or format to help them
        format_yellow = workbook.add_format({'bg_color': '#FFFF00'})
        worksheet.write('A2', 'NEW-PARENT-SKU', format_yellow) # Highlight Parent row
        
    return buffer.getvalue()

# --- DISPLAY DOWNLOAD BUTTON ---
st.markdown("### 1. Need a Plan?")
st.write("Download this template to see exactly how to format your Planning File.")

template_data = generate_template()

st.download_button(
    label="📄 Download Plan Template (.xlsx)",
    data=template_data,
    file_name="Plan_Template.xlsx",
    mime="application/vnd.ms-excel",
    help="Click to download a sample file with the correct headers."
)

st.markdown("---") # Visual divider line
col1, col2 = st.columns(2)
with col1:
    master_file = st.file_uploader("📂 Upload Master CLR (.xlsx)", type=['xlsx'])
with col2:
    plan_file = st.file_uploader("📂 Upload Plan File (.xlsx)", type=['xlsx'])

# --- LOGIC FUNCTIONS ---
def find_header_row(df_preview, sku_header_name):
    """Scans the first 10 rows to find which one contains the SKU header."""
    for i, row in df_preview.iterrows():
        # Convert row to string and check for header
        row_str = row.astype(str).values
        if sku_header_name in row_str:
            return i + 1 # Return Excel row number (0-index + 1)
    return None

def process_files(master, plan, sku_col, var_col, theme_name):
    # 1. READ MASTER (Smart Header Detection)
    # Read first 10 rows without header to scan
    df_temp = pd.read_excel(master, header=None, nrows=10)
    
    # Locate the SKU header
    header_idx = None
    for idx, row in df_temp.iterrows():
        if sku_col in row.values:
            header_idx = idx
            break
            
    if header_idx is None:
        return None, f"❌ Could not find column '{sku_col}' in the first 10 rows of Master File."

    # Reload Master with correct header
    master.seek(0) # Reset file pointer
    df_master = pd.read_excel(master, header=header_idx)
    
    # Clean Data
    df_master[sku_col] = df_master[sku_col].astype(str).str.strip()
    
    # 2. READ PLAN
    df_plan = pd.read_excel(plan)
    if 'SKU' not in df_plan.columns:
        return None, "❌ Plan file must have a 'SKU' column (case-sensitive)."

    new_parents_to_add = []
    processed_count = 0
    
    # Iterate through sheets (if multiple) logic simplified for single sheet upload usually
    # But let's handle the single df_plan we just loaded
    
    try:
        # Row 1 (Index 0) is Parent, Rows 2+ are Children
        new_parent_sku = str(df_plan.iloc[0]['SKU']).strip()
        children_data = df_plan.iloc[1:].copy()
    except:
        return None, "❌ Plan file format invalid. Row 2 must be Parent, Rows 3+ Children."

    # --- PROCESS CHILDREN ---
    for index, row in children_data.iterrows():
        child_sku = str(row['SKU']).strip()
        
        # Dynamic Attribute
        if var_col in row:
            new_var_val = row[var_col]
        else:
            # Fallback: grab 5th col
            if len(row) > 4:
                new_var_val = row.iloc[4]
            else:
                new_var_val = "MISSING"

        mask = df_master[sku_col] == child_sku

        if mask.any():
            df_master.loc[mask, 'Parent SKU'] = new_parent_sku
            df_master.loc[mask, 'Parentage Level'] = 'Child'
            df_master.loc[mask, 'Variation Theme Name'] = theme_name
            # Try to write to the dynamic attribute column if it exists in Master
            if var_col in df_master.columns:
                df_master.loc[mask, var_col] = new_var_val
            
            df_master.loc[mask, 'Listing Action'] = 'Edit (Partial Update)'
            processed_count += 1

    # --- CREATE PARENT ---
    first_child_sku = str(children_data.iloc[0]['SKU']).strip()
    child_row_data = df_master[df_master[sku_col] == first_child_sku]

    if not child_row_data.empty:
        parent_row = child_row_data.iloc[0].copy()
        
        # Wipe and Set Parent Data
        parent_row[sku_col] = new_parent_sku
        parent_row['Parentage Level'] = 'Parent'
        parent_row['Parent SKU'] = '' 
        parent_row['Variation Theme Name'] = theme_name
        parent_row['Listing Action'] = 'Create or Replace (Full Update)'
        parent_row['Item Name'] = f"PARENT - {new_parent_sku} - RENAME ME"
        
        # Clear specific fields for parent (Price, Qty, etc. should be empty)
        # We leave them as is or empty depending on user preference, 
        # but typically we ensure the attribute is blank
        if var_col in parent_row:
            parent_row[var_col] = ''

        new_parents_to_add.append(parent_row)

    if new_parents_to_add:
        df_parents = pd.DataFrame(new_parents_to_add)
        df_final = pd.concat([df_master, df_parents], ignore_index=True)
    else:
        df_final = df_master
        
    return df_final, f"✅ Success! Processed {processed_count} children."

# --- MAIN EXECUTION ---
if st.button("🚀 Run Automation", type="primary"):
    if master_file and plan_file:
        with st.spinner("Processing..."):
            result_df, status_msg = process_files(master_file, plan_file, col_sku, col_var_attr, val_theme)
            
            if "❌" in status_msg:
                st.error(status_msg)
            else:
                st.success(status_msg)
                
                # --- OUTPUT GENERATION (The Formatting Fix) ---
                
                # OPTION 1: Excel (Standard)
                buffer_xlsx = io.BytesIO()
                with pd.ExcelWriter(buffer_xlsx, engine='xlsxwriter') as writer:
                    result_df.to_excel(writer, index=False)
                
                # OPTION 2: Text/Tab-Delimited (Amazon Safe Mode)
                # This strips formatting and forces raw text
                buffer_txt = io.BytesIO()
                result_df.to_csv(buffer_txt, sep='\t', index=False)
                
                st.write("### 📥 Download Results")
                
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button(
                        label="Download Excel (.xlsx)",
                        data=buffer_xlsx.getvalue(),
                        file_name="READY_TO_UPLOAD.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                with c2:
                    st.download_button(
                        label="Download Text File (.txt) - *Recommended*",
                        data=buffer_txt.getvalue(),
                        file_name="READY_TO_UPLOAD.txt",
                        mime="text/plain",
                        help="Upload this file to 'Check My File' on Amazon. It avoids all Excel formatting errors."
                    )
                    
    else:
        st.warning("Please upload both files to continue.")
