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

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("🔧 Column Settings")
st.sidebar.info("Adjust these if your Amazon file headers look different.")

col_sku = st.sidebar.text_input("SKU Header", value="SKU")
col_var_attr = st.sidebar.text_input("Variation Attribute (Plan)", value="Size")
val_theme = st.sidebar.text_input("Theme Name (e.g. SizeName)", value="SizeName")

# --- TEMPLATE GENERATOR ---
def generate_template():
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
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        fmt = workbook.add_format({'bg_color': '#FFFF00'})
        worksheet.write('A2', 'NEW-PARENT-SKU', fmt)
    return buffer.getvalue()

# --- FILE UPLOADER SECTION ---
st.info("💡 **Tip:** Don't have a plan file yet? Download the template below.")
st.download_button(
    label="📄 Download Plan Template (.xlsx)",
    data=generate_template(),
    file_name="Plan_Template.xlsx",
    mime="application/vnd.ms-excel"
)

st.markdown("---") 

col1, col2 = st.columns(2)
with col1:
    master_file = st.file_uploader("📂 1. Upload Master CLR", type=['xlsx'])
with col2:
    plan_file = st.file_uploader("📂 2. Upload Plan File", type=['xlsx'])

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
        return None, f"❌ Could not find column '{sku_col}' in Master File."

    # Reload Master with correct header
    master.seek(0)
    df_master = pd.read_excel(master, header=header_idx)
    df_master[sku_col] = df_master[sku_col].astype(str).str.strip()

    # Add a helper column to track which rows we change
    df_master['__TOUCHED__'] = False 
    
    # 2. READ PLAN
    df_plan = pd.read_excel(plan)
    if 'SKU' not in df_plan.columns:
        return None, "❌ Plan file must have a 'SKU' column."

    new_parents_to_add = []
    processed_count = 0
    
    try:
        # Row 1 (Index 0) is Parent, Rows 2+ are Children
        new_parent_sku = str(df_plan.iloc[0]['SKU']).strip()
        children_data = df_plan.iloc[1:].copy()
    except:
        return None, "❌ Plan file invalid. Row 2 must be Parent."

    # --- PROCESS CHILDREN ---
    # This is the line that broke last time:
    for index, row in children_data.iterrows():
        child_sku = str(row['SKU']).strip()
        
        # Dynamic Attribute
        if var_col in row:
            new_var_val = row[var_col]
        else:
            # Fallback: grab 5th col if specific name not found
            if len(row) > 4:
                new_var_val = row.iloc[4]
            else:
                new_var_val = "MISSING"

        mask = df_master[sku_col] == child_sku

        if mask.any():
            df_master.loc[mask, 'Parent SKU'] = new_parent_sku
            df_master.loc[mask, 'Parentage Level'] = 'Child'
            df_master.loc[mask, 'Variation Theme Name'] = theme_name
            # Write to the dynamic attribute column if exists
            if var_col in df_master.columns:
                df_master.loc[mask, var_col] = new_var_val
            
            df_master.loc[mask, 'Listing Action'] = 'Edit (Partial Update)'
            
            # MARK AS TOUCHED
            df_master.loc[mask, '__TOUCHED__'] = True
            processed_count += 1

    # --- CREATE PARENT ---
    first_child_sku = str(children_data.iloc[0]['SKU']).strip()
    child_row_data = df_master[df_master[sku_col] == first_child_sku]

    if not child_row_data.empty:
        parent_row = child_row_data.iloc[0].copy()
        
        # Set Parent Data
        parent_row[sku_col] = new_parent_sku
        parent_row['Parentage Level'] = 'Parent'
        parent_row['Parent SKU'] = '' 
        parent_row['Variation Theme Name'] = theme_name
        parent_row['Listing Action'] = 'Create or Replace (Full Update)'
        parent_row['Item Name'] = f"PARENT - {new_parent_sku} - RENAME ME"
        
        if var_col in parent_row:
            parent_row[var_col] = ''
        
        # MARK AS TOUCHED
        parent_row['__TOUCHED__'] = True

        new_parents_to_add.append(parent_row)

    # --- MERGE & FILTER ---
    if new_parents_to_add:
        df_parents = pd.DataFrame(new_parents_to_add)
        df_final = pd.concat([df_master, df_parents], ignore_index=True)
    else:
        df_final = df_master

    # KEEP ONLY TOUCHED ROWS
    df_final = df_final[df_final['__TOUCHED__'] == True]
    df_final = df_final.drop(columns=['__TOUCHED__'])
        
    return df_final, f"✅ Success! Processed {processed_count} children."

# --- MAIN EXECUTION ---
if st.button("🚀 Run Automation", type="primary"):
    if master_file and plan_file:
        with st.spinner("Processing..."):
            result, msg = process_files(master_file, plan_file, col_sku, col_var_attr, val_theme)
            
            if msg and "❌" in msg:
                st.error(msg)
            else:
                st.success(msg)
                
                # OUTPUT
                # 1. Excel
                buffer_xlsx = io.BytesIO()
                with pd.ExcelWriter(buffer_xlsx, engine='xlsxwriter') as writer:
                    result.to_excel(writer, index=False)
                
                # 2. Text
                buffer_txt = io.BytesIO()
                result.to_csv(buffer_txt, sep='\t', index=False)
                
                st.write("### 📥 Download Results")
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button(
                        label="Download Excel",
                        data=buffer_xlsx.getvalue(),
                        file_name="READY_TO_UPLOAD.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                with c2:
                    st.download_button(
                        label="Download Text File (Recommended)",
                        data=buffer_txt.getvalue(),
                        file_name="READY_TO_UPLOAD.txt",
                        mime="text/plain"
                    )
    else:
        st.warning("Please upload both files to continue.")
