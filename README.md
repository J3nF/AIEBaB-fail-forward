# AIEBaB Fail Forward 🧬

> Compiling data from failed expression experiments to learn from failure

This project is part of the [AIEBaB conference](https://aiebab.github.io/) hackathon.

## Getting Started

### Installation

```bash
pip install -r requirements.txt
```

### Running the Application

```bash
streamlit run src/app.py
```

## Features

- 📤 **Upload Excel/CSV data** with intelligent column mapping
- 🔍 **Search and filter** experiments
- 📊 **View and export** all collected data
- 🤖 **ML-powered** column name matching
- ✅ **Duplicate detection** to prevent re-uploading same data

## Project Structure

```
AIEBaB-fail-forward/
├── src/
│   ├── app.py           # Main Streamlit application
│   ├── database.py      # Database operations
│   ├── search.py        # Search functionality
│   └── utils.py         # Utility functions
├── requirements.txt     # Python dependencies
└── README.md           # This file
```