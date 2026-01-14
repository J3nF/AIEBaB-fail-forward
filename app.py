import numpy as np
import streamlit as st
import os
from pathlib import Path
from datetime import datetime
from database import Database
from search import search_samples
from utils import encode_texts
from sklearn.metrics.pairwise import cosine_similarity

# Initialize
DB_PATH = "lab_inventory.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

db = Database(DB_PATH)

st.set_page_config(page_title="Failure Forward", page_icon="🧬", layout="wide")

# Sidebar for navigation
page = st.sidebar.radio("Navigation", ["📤 Add Data", "🔍 Search Data", "📊 View All"])

if page == "📤 Add Data":
    st.title("🧬 Add New Experiment Data")
    st.markdown("Upload an Excel file with your experiment data!")
    st.caption("Expected columns: Sample ID, Researcher, Expressed")
    
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls", "csv"])
    
    if uploaded_file:
        import pandas as pd
        
        try:
            # Read Excel or CSV file
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ Loaded {len(df)} rows from {uploaded_file.name}")
            
            # Show preview of data
            st.subheader("📋 Data Preview")
            st.dataframe(df.head(10), use_container_width=True)

            """
            Column Name Mapping Part
            """
            column_names = df.columns.tolist()

            # Options for every combobox
            options = ["Project ID", "Sample ID", "Expressed", "KD", "Sequence", "Soluble", "Date", "Scientist", "Comments", "Protocol"]

            column_encodings = encode_texts(column_names)
            option_encodings = encode_texts(options)

            similarities = cosine_similarity(column_encodings, option_encodings)

            best_indice = [np.argmax(sim) for sim in similarities]


            st.title("Column Name Mapping")

            selected_values = {}

            for i, item in enumerate(column_names):
                # You can put text and selectbox on the same row using columns if you like
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(item)
                with col2:
                    # Use a unique key per widget
                    selected = st.selectbox(
                        "Select option",
                        options,
                        key=f"select_{i}",
                        index=int(best_indice[i]),
                    )
                selected_values[item] = selected



            # Check for duplicates
            existing_samples = db.get_all_samples()
            duplicates = []
            
            for idx, row in df.iterrows():
                sample_id = str(row.get('Sample ID', '')) if pd.notna(row.get('Sample ID', '')) else ""
                
                for existing in existing_samples:
                    if (existing['sample_id'] == sample_id and sample_id):  # Only flag as duplicate if sample ID has value
                        duplicates.append({'row': idx + 1, 'Sample ID': sample_id})
                        break
            
            if duplicates:
                st.warning(f"⚠️ Found {len(duplicates)} potential duplicate(s) in the database:")
                dup_df = pd.DataFrame(duplicates)
                st.dataframe(dup_df, use_container_width=True)
            
            # Optional field to add to all rows
            st.subheader("➕ Add Extra Information (Optional)")
            st.markdown("This value will be added to ALL rows in the import:")
            
            extra_scientist = st.text_input("Researcher Name", "", help="This will override the researcher field for all rows")
            
            # Duplicate handling option
            skip_duplicates = False
            if duplicates:
                skip_duplicates = st.checkbox("Skip duplicate rows during import", value=True)
            
            if st.button("💾 Import All Data to Database", type="primary"):
                with st.spinner("Importing data..."):
                    imported_count = 0
                    skipped_count = 0
                    imported_data = []
                    
                    for idx, row in df.iterrows():
                        try:
                            # Extract values from columns
                            sample_id = str(row.get('Sample ID', '')) if pd.notna(row.get('Sample ID', '')) else ""
                            researcher = str(row.get('Researcher', '')) if pd.notna(row.get('Researcher', '')) else ""
                            expressed = str(row.get('Expressed', '')) if pd.notna(row.get('Expressed', '')) else ""
                            
                            # Check if this is a duplicate and should be skipped
                            is_duplicate = False
                            if skip_duplicates and sample_id:
                                for existing in existing_samples:
                                    if existing['sample_id'] == sample_id:
                                        is_duplicate = True
                                        skipped_count += 1
                                        break
                            
                            if is_duplicate:
                                continue
                            
                            # Override researcher if provided
                            if extra_scientist:
                                researcher = extra_scientist
                            
                            # Handle date
                            date_value = row.get('date', None)
                            if date_value and pd.notna(date_value):
                                try:
                                    date_str = pd.to_datetime(date_value).isoformat()
                                except:
                                    date_str = str(date_value)
                            else:
                                date_str = datetime.now().isoformat()
                            
                            db.add_sample(
                                sample_id=sample_id,
                                researcher=researcher,
                                expressed=expressed,
                                date=date_str
                            )
                            imported_count += 1
                            
                            # Track imported data for summary
                            imported_data.append({
                                'Sample ID': sample_id,
                                'Researcher': researcher,
                                'Expressed': expressed,
                                'Date': date_str
                            })
                        except Exception as e:
                            st.warning(f"Row {idx + 1} skipped: {str(e)}")
                    
                    st.success(f"✅ Successfully imported {imported_count} samples!")
                    if skipped_count > 0:
                        st.info(f"⏭️ Skipped {skipped_count} duplicate(s)")
                    
                    # Display summary of imported data
                    if imported_data:
                        st.subheader("📋 Import Summary")
                        summary_df = pd.DataFrame(imported_data)
                        st.dataframe(summary_df, use_container_width=True)
                    
                    st.info("💡 View all your data in the '📊 View All' tab!")
        
        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")
            st.info("Make sure your file is a valid Excel (.xlsx, .xls) or CSV file.")

elif page == "🔍 Search Data":
    st.title("🔍 Search Experiment Repository")
    
    search_query = st.text_input(
        "Search for anything:",
        placeholder="Try: '0001', 'Fran', '12/05/2025', ...",
        key="search"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        filter_person = st.text_input("Filter by Researcher", "")
    with col2:
        filter_sample_id = st.text_input("Filter by Sample ID", "")
    
    if search_query or filter_person or filter_sample_id:
        results = search_samples(
            db, 
            query=search_query,
            person=filter_person,
            antibiotic=filter_sample_id,
            location=""
        )
        
        st.markdown(f"### Found {len(results)} result(s)")
        
        if results:
            for result in results:
                with st.expander(f"🧬 Sample: {result['sample_id'] or 'Unknown'} | Researcher: {result['researcher'] or 'N/A'}"):
                    st.markdown(f"**Sample ID:** {result['sample_id'] or 'N/A'}")
                    st.markdown(f"**Researcher:** {result['researcher'] or 'N/A'}")
                    st.markdown(f"**Expressed:** {result['expressed'] or 'N/A'}")
                    st.markdown(f"**Date:** {result['date'] or 'N/A'}")
                    st.caption(f"Added: {result['created_at']}")
        else:
            st.info("No results found. Try different search terms!")

elif page == "📊 View All":
    st.title("📊 All Samples")
    
    all_samples = db.get_all_samples()
    
    if all_samples:
        st.markdown(f"### Total samples: {len(all_samples)}")
        
        # Quick stats
        col1, col2 = st.columns(2)
        with col1:
            unique_samples = len(set(s['sample_id'] for s in all_samples if s['sample_id']))
            st.metric("Unique Samples", unique_samples)
        with col2:
            unique_researchers = len(set(s['researcher'] for s in all_samples if s['researcher']))
            st.metric("Researchers", unique_researchers)
        
        st.divider()
        
        # Table view
        import pandas as pd
        df = pd.DataFrame(all_samples)
        # Rename columns for display
        display_df = df[['sample_id', 'researcher', 'expressed', 'date']].copy()
        display_df.columns = ['Sample ID', 'Researcher', 'Expressed', 'Date']
        st.dataframe(display_df, use_container_width=True)
        
        # Download option
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download as CSV",
            csv,
            "lab_inventory.csv",
            "text/csv",
            key='download-csv'
        )
    else:
        st.info("No samples in database yet. Add some using the 'Add Sample' page!")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Protein Expression Data System** 🧬")
st.sidebar.caption("ML-Powered data collection for smarter experiments")
