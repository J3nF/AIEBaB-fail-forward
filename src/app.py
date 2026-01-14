import json

import numpy as np
import streamlit as st
import os
from pathlib import Path
from datetime import datetime
from database import Database
from search import search_samples
from utils import encode_texts
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from textsearchpy import Index, Document

from pypdf import PdfReader

# Initialize
DB_PATH = "lab_data.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

db = Database(DB_PATH)

st.set_page_config(page_title="Failure Forward", page_icon="🧬", layout="wide")

protocol_DB_path = "protocol_data.json"
# print(os.getcwd())
# st.info(os.path.abspath(protocol_DB_path))
PROTOCOL_DATABASE = {}
if os.path.exists(protocol_DB_path):
    with open(protocol_DB_path) as f:
        PROTOCOL_DATABASE = json.load(f)

protocol_index = Index()
for key in PROTOCOL_DATABASE:
    doc = Document(text=PROTOCOL_DATABASE[key]["Full Text"], id=key)
    protocol_index.append([doc])

# Sidebar for navigation
page = st.sidebar.radio("Navigation", ["📤 Add Data", "🔍 Search Data", "📊 View All"])

if page == "📤 Add Data":
    st.title("🧬 Add New Experiment Data")
    st.markdown("Upload an Excel file with your experiment data!")
    st.caption("Expected columns: Sample ID, Researcher, Expressed")

    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls", "csv"])

    uploaded_protocol_file = st.file_uploader("Upload Protocol file", type=["pdf", "md", "txt"])

    valid_project = True

    valid_project = valid_project and uploaded_file is not None
    if uploaded_file:

        # Use session state to cache the uploaded file data
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"

        if 'last_file_id' not in st.session_state or st.session_state.last_file_id != file_id:
            # New file uploaded, reset session state
            st.session_state.last_file_id = file_id
            st.session_state.df = None
            st.session_state.column_encodings = None
            st.session_state.option_encodings = None

        try:
            # Read Excel or CSV file only once
            if st.session_state.df is None:
                if uploaded_file.name.endswith('.csv'):
                    st.session_state.df = pd.read_csv(uploaded_file)
                else:
                    st.session_state.df = pd.read_excel(uploaded_file)

            df = st.session_state.df

            # Show preview of data
            st.subheader("📋 Data Preview")
            st.success(f"✅ Loaded {len(df)} rows from {uploaded_file.name}")
            st.dataframe(df.head(10), use_container_width=True)

            #
            # Column Name Mapping Part
            #
            column_names = df.columns.tolist()

            # Options for every combobox
            options = ["Project ID", "Sample ID", "Expressed", "KD/Binding", "Sequence", "Soluble", "Date", "Researcher",
                       "Comments", "Protocol"]

            # Cache encodings to avoid recomputing on every widget change
            if st.session_state.column_encodings is None:
                with st.spinner("Analyzing column names..."):
                    st.session_state.column_encodings = encode_texts(column_names)
                    st.session_state.option_encodings = encode_texts(options)

            column_encodings = st.session_state.column_encodings
            option_encodings = st.session_state.option_encodings

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

            # Check which fields are already mapped
            mapped_fields = set(selected_values.values())

            if len(mapped_fields) != len(selected_values):
                st.error(f"❌ Each column name must be unique")
                valid_project = False

            # Required Project ID
            st.subheader("🔑 Project ID (Required)")

            # Check if Project ID is already in the mapped columns
            if "Project ID" in mapped_fields:
                st.success("✅ Project ID already assigned from your data")
                project_id = "assigned_from_data"  # Flag that it's from data
            else:
                project_id = st.text_input("Enter Project ID", "", help="This project ID will be added to ALL rows")

                if not project_id:
                    st.warning("⚠️ Project ID is required before importing data")

            # Optional extra data
            st.subheader("➕ Add Extra Information (Optional)")

            # Show dropdown for additional optional fields, excluding already mapped ones
            extra_data_fields = {}
            all_optional_fields = ["Comments", "Protocol", "Other Notes"]

            # Map field names to their corresponding column mapping names
            field_to_mapping = {
                "Comments": "Comments",
                "Protocol": "Protocol"
            }

            # Filter out fields that are already mapped
            available_extra_fields = []
            for field in all_optional_fields:
                mapped_name = field_to_mapping.get(field, field)
                if mapped_name not in mapped_fields and field not in mapped_fields:
                    available_extra_fields.append(field)

            if available_extra_fields:
                with st.expander("Add optional fields"):
                    for field in available_extra_fields:
                        value = st.text_input(f"{field}", "", key=f"extra_{field}",
                                              help=f"This will be added to all rows")
                        if value:
                            extra_data_fields[field] = value
            else:
                st.info("All optional fields are already mapped from your data columns")

            # Check for duplicates
            existing_samples = db.get_all_samples()
            duplicates = []

            for idx, row in df.iterrows():
                cur_sample_id = str(row.get('Sample ID', '')) if pd.notna(row.get('Sample ID', '')) else ""
                cur_researcher = str(row.get('Researcher', '')) if pd.notna(row.get('Researcher', '')) else ""
                cur_expressed = str(row.get('Expressed', '')) if pd.notna(row.get('Expressed', '')) else ""

                for existing in existing_samples:
                    # Check if all three fields match
                    if (existing['sample_id'] == cur_sample_id and
                            existing['researcher'] == cur_researcher and
                            existing['expressed'] == cur_expressed and
                            cur_sample_id):  # Only flag if sample ID exists
                        duplicates.append({
                            'row': idx + 1,
                            'Sample ID': cur_sample_id,
                            'Researcher': cur_researcher,
                            'Expressed': cur_expressed
                        })
                        break

            if duplicates:
                st.warning(f"⚠️ Found {len(duplicates)} potential duplicate(s) in the database:")
                dup_df = pd.DataFrame(duplicates)
                st.dataframe(dup_df, use_container_width=True)

            # Duplicate handling option
            skip_duplicates = False
            if duplicates:
                skip_duplicates = st.checkbox("Skip duplicate rows during import", value=True)

            valid_project = valid_project and project_id is not None
        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")
            st.info("Make sure your file is a valid Excel (.xlsx, .xls) or CSV file.")

    protocol_full_text = ""
    protocol_name = None
    if uploaded_protocol_file:

        # Use session state to cache the uploaded file data
        protocol_file_id = f"{uploaded_protocol_file.name}_{uploaded_protocol_file.size}"

        if 'last_protocol_file_id' not in st.session_state or st.session_state.last_protocol_file_id != protocol_file_id:
            # New file uploaded, reset session state
            st.session_state.last_protocol_file_id = protocol_file_id
            st.session_state.protocol = None
            st.session_state.protocol_indexed = False

        if uploaded_protocol_file.name.endswith('.pdf'):
            reader = PdfReader(uploaded_protocol_file)
            all_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)

            protocol_full_text = "\n".join(all_text)
            st.pdf(uploaded_protocol_file)
            st.session_state.protocol = protocol_full_text
            protocol_name = uploaded_protocol_file.name
        else:
            with open(uploaded_protocol_file, 'rb') as file:
                protocol_full_text = file.read()

            st.markdown(protocol_full_text)
            st.session_state.protocol = protocol_full_text
            protocol_name = uploaded_protocol_file.name

        PROTOCOL_DATABASE[project_id] = {"Full Text": protocol_full_text,
                                         "Name": uploaded_protocol_file.name}

        # if not st.session_state.protocol_indexed:
        #     PROTOCOL_DATABASE[uploaded_protocol_file] = full_text
        #     doc = Document(text=full_text, id=uploaded_protocol_file)
        #     protocol_index.append([doc])
        #     st.session_state.protocol_indexed = True

    # Disable import button if Project ID is not provided
    st.text(f"Valid project: {valid_project}")
    if st.button("💾 Import All Data to Database", type="primary", disabled=(not valid_project)):
        df.rename(columns=selected_values, inplace=True)

        with st.spinner("Importing data..."):
            imported_count = 0
            skipped_count = 0
            imported_data = []

            for idx, row in df.iterrows():
                try:
                    # Extract values from columns

                    cur_project_id = str(row.get('Project ID', ''))
                    cur_sample_id = str(row.get('Sample ID', '')) if pd.notna(row.get('Sample ID', '')) else ""
                    cur_researcher = str(row.get('Researcher', '')) if pd.notna(row.get('Researcher', '')) else ""
                    cur_expressed = str(row.get('Expressed', '')) if pd.notna(row.get('Expressed', '')) else ""
                    cur_KD = str(row.get('KD/Binding', ''))
                    cur_sequence = str(row.get('Sequence', ''))
                    cur_soluble = str(row.get('Soluble', ''))
                    cur_date = str(row.get('Date', ''))
                    cur_comments = str(row.get('Comments', ''))
                    cur_protocol = protocol_full_text



                    # Check if this is a duplicate and should be skipped
                    is_duplicate = False
                    if skip_duplicates and cur_sample_id:
                        for existing in existing_samples:
                            # Check if all three fields match for a true duplicate
                            if (existing['sample_id'] == cur_sample_id and
                                    existing['researcher'] == cur_researcher and
                                    existing['expressed'] == cur_expressed):
                                is_duplicate = True
                                skipped_count += 1
                                break

                    if is_duplicate:
                        continue

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
                        sample_id=cur_sample_id,
                        researcher=cur_researcher,
                        expressed=cur_expressed,
                        date=date_str,
                        protocol_name=protocol_name
                    )
                    imported_count += 1

                    # Track imported data for summary
                    imported_data.append({
                        'Sample ID': cur_sample_id,
                        'Researcher': cur_researcher,
                        'Expressed': cur_expressed,
                        'Date': date_str
                    })
                except Exception as e:
                    st.warning(f"Row {idx + 1} skipped: {str(e)}")

            with open(protocol_DB_path, "w") as file:
                json.dump(PROTOCOL_DATABASE, file, indent=4)

            st.success(f"✅ Successfully imported {imported_count} samples!")
            if skipped_count > 0:
                st.info(f"⏭️ Skipped {skipped_count} duplicate(s)")

            # Display summary of imported data
            if imported_data:
                st.subheader("📋 Import Summary")
                summary_df = pd.DataFrame(imported_data)
                st.dataframe(summary_df, use_container_width=True)

            st.info("💡 View all your data in the '📊 View All' tab!")

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
                with st.expander(
                        f"🧬 Sample: {result['sample_id'] or 'Unknown'} | Researcher: {result['researcher'] or 'N/A'}"):
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
        # Display all columns
        st.dataframe(df, use_container_width=True)

        # Download option
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download as CSV",
            csv,
            "lab_data.csv",
            "text/csv",
            key='download-csv'
        )
    else:
        st.info("No samples in database yet. Add some using the 'Add Sample' page!")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Protein Expression Data System** 🧬")
st.sidebar.caption("ML-Powered data collection for smarter experiments")
