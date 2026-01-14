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

# Initialize
DB_PATH = "lab_inventory.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

db = Database(DB_PATH)

st.set_page_config(page_title="Failure Forward", page_icon="🧬", layout="wide")

# Sidebar for navigation
page = st.sidebar.radio("Navigation", ["📤 Add Data", "🔍 Search Data", "📊 View All"])


# --- Helpers -------------------------------------------------------------

OPTIONS = [
    "Project ID", "Sample ID", "Expressed", "KD", "Sequence", "Soluble",
    "Date", "Scientist", "Comments", "Protocol"
]

def load_dataframe(uploaded_file) -> pd.DataFrame:
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)

def normalize_str(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    # pandas uses NaN for missing; pd.isna handles many types
    if pd.isna(value):
        return ""
    return str(value).strip()

def normalize_date(value) -> str:
    if value is None or pd.isna(value):
        return datetime.now().isoformat()
    try:
        return pd.to_datetime(value).isoformat()
    except Exception:
        return str(value)

def build_best_guess_indices(column_names, options):
    col_enc = st.session_state.get("column_encodings")
    opt_enc = st.session_state.get("option_encodings")

    if col_enc is None or opt_enc is None:
        with st.spinner("Analyzing column names..."):
            st.session_state.column_encodings = encode_texts(column_names)
            st.session_state.option_encodings = encode_texts(options)

    similarities = cosine_similarity(st.session_state.column_encodings, st.session_state.option_encodings)
    return [int(np.argmax(sim)) for sim in similarities]

def render_column_mapping(column_names):
    best_indices = build_best_guess_indices(column_names, OPTIONS)

    st.subheader("Column Name Mapping")
    selected_values = {}

    for i, col_name in enumerate(column_names):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write(col_name)
        with c2:
            selected = st.selectbox(
                "Select option",
                OPTIONS,
                key=f"map_{i}",
                index=best_indices[i],
                label_visibility="collapsed",
            )
        selected_values[col_name] = selected

    # Invert mapping: "Sample ID" -> actual dataframe column name (if assigned)
    mapping = {}
    for df_col, canonical in selected_values.items():
        # last one wins if user maps two cols to same canonical field
        mapping[canonical] = df_col

    return mapping, set(selected_values.values())

def get_project_id(mapped_fields):
    st.subheader("🔑 Project ID (Required)")
    if "Project ID" in mapped_fields:
        st.success("✅ Project ID is mapped from your file.")
        return None  # means "use column"
    project_id = st.text_input("Enter Project ID", "", help="This Project ID will be applied to ALL rows.")
    if not project_id:
        st.warning("⚠️ Project ID is required before importing data.")
    return project_id.strip() if project_id else ""

def get_extra_fields(mapped_fields):
    st.subheader("➕ Add Extra Information (Optional)")
    all_optional_fields = ["Comments", "Protocol", "Other Notes"]
    available = [f for f in all_optional_fields if f not in mapped_fields]

    extra = {}
    if not available:
        st.info("All optional fields are already mapped from your data columns.")
        return extra

    with st.expander("Add optional fields"):
        for field in available:
            v = st.text_input(field, "", key=f"extra_{field}", help="This value will be added to all rows.")
            if v.strip():
                extra[field] = v.strip()
    return extra

def compute_existing_keys(existing_samples):
    # "true duplicate" = same triple (sample_id, researcher, expressed)
    return {
        (normalize_str(s.get("sample_id")), normalize_str(s.get("researcher")), normalize_str(s.get("expressed")))
        for s in existing_samples
        if normalize_str(s.get("sample_id"))
    }

def extract_row_values(df_row, mapping, manual_project_id: str | None, extra_fields: dict):
    # Resolve canonical fields -> df column names
    sample_col = mapping.get("Sample ID")
    researcher_col = mapping.get("Researcher") or mapping.get("Scientist")  # allow Scientist as fallback
    expressed_col = mapping.get("Expressed")
    date_col = mapping.get("Date")

    sample_id = normalize_str(df_row.get(sample_col)) if sample_col else ""
    researcher = normalize_str(df_row.get(researcher_col)) if researcher_col else ""
    expressed = normalize_str(df_row.get(expressed_col)) if expressed_col else ""
    date_str = normalize_date(df_row.get(date_col)) if date_col else datetime.now().isoformat()

    # Project ID: from column if mapped, otherwise from manual input
    if "Project ID" in mapping and mapping["Project ID"]:
        project_id = normalize_str(df_row.get(mapping["Project ID"]))
    else:
        project_id = manual_project_id or ""

    # Extra fields are “global” (same for all rows), not currently stored in DB
    # If you add DB columns later, you can insert them here.
    return sample_id, researcher, expressed, date_str, project_id

# --- Page ---------------------------------------------------------------

if page == "📤 Add Data":
    st.title("🧬 Add New Experiment Data")
    st.markdown("Upload an Excel/CSV file with your experiment data!")
    st.caption("Expected data fields: Sample ID, Researcher/Scientist, Expressed (others optional)")

    uploaded_file = st.file_uploader("Upload file", type=["xlsx", "xls", "csv"])

    if uploaded_file:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"

        if st.session_state.get("last_file_id") != file_id:
            st.session_state.last_file_id = file_id
            st.session_state.df = None
            st.session_state.column_encodings = None
            st.session_state.option_encodings = None

        try:
            if st.session_state.df is None:
                st.session_state.df = load_dataframe(uploaded_file)

            df = st.session_state.df
            st.success(f"✅ Loaded {len(df)} rows from {uploaded_file.name}")

            st.subheader("📋 Data Preview")
            st.dataframe(df.head(10), use_container_width=True)

            column_names = df.columns.tolist()
            mapping, mapped_fields = render_column_mapping(column_names)

            manual_project_id = get_project_id(mapped_fields)
            extra_fields = get_extra_fields(mapped_fields)

            # Require Project ID either mapped OR manually entered
            project_ok = ("Project ID" in mapped_fields) or bool(manual_project_id)

            # Existing samples (for duplicate detection)
            existing_samples = db.get_all_samples()
            existing_keys = compute_existing_keys(existing_samples)

            # Scan for duplicates quickly
            duplicates = []
            for idx, row in df.iterrows():
                sample_id, researcher, expressed, _, _ = extract_row_values(row, mapping, manual_project_id, extra_fields)
                if sample_id and (sample_id, researcher, expressed) in existing_keys:
                    duplicates.append({
                        "row": idx + 1,
                        "Sample ID": sample_id,
                        "Researcher": researcher,
                        "Expressed": expressed
                    })

            if duplicates:
                st.warning(f"⚠️ Found {len(duplicates)} potential duplicate(s) in the database:")
                st.dataframe(pd.DataFrame(duplicates), use_container_width=True)
                skip_duplicates = st.checkbox("Skip duplicate rows during import", value=True)
            else:
                skip_duplicates = False

            if st.button("💾 Import All Data to Database", type="primary", disabled=(not project_ok)):
                with st.spinner("Importing data..."):
                    imported_count = 0
                    skipped_count = 0
                    imported_data = []

                    for idx, row in df.iterrows():
                        try:
                            sample_id, researcher, expressed, date_str, project_id = extract_row_values(
                                row, mapping, manual_project_id, extra_fields
                            )

                            # Skip blank Sample IDs (optional but usually sensible)
                            if not sample_id:
                                skipped_count += 1
                                continue

                            key = (sample_id, researcher, expressed)
                            if skip_duplicates and key in existing_keys:
                                skipped_count += 1
                                continue

                            # NOTE: your Database currently ignores project_id/extra_fields because schema doesn't have them
                            db.add_sample(sample_id=sample_id, researcher=researcher, expressed=expressed, date=date_str)
                            imported_count += 1
                            existing_keys.add(key)

                            imported_data.append({
                                "Project ID": project_id,
                                "Sample ID": sample_id,
                                "Researcher": researcher,
                                "Expressed": expressed,
                                "Date": date_str
                            })
                        except Exception as e:
                            st.warning(f"Row {idx + 1} skipped: {e}")
                            skipped_count += 1

                    st.success(f"✅ Successfully imported {imported_count} samples!")
                    if skipped_count:
                        st.info(f"⏭️ Skipped {skipped_count} row(s)")

                    if imported_data:
                        st.subheader("📋 Import Summary")
                        st.dataframe(pd.DataFrame(imported_data), use_container_width=True)

                    st.info("💡 View all your data in the '📊 View All' tab!")

        except Exception as e:
            st.error(f"❌ Error reading file: {e}")
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
