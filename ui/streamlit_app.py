import sys
from pathlib import Path

# Ensure project root is on sys.path for local imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

st.set_page_config(page_title="Loganom AI Demo", layout="wide")

st.title("Loganom AI Demo")

st.write("Use the left sidebar to navigate pages: Overview, Hosts, Alerts.")

st.info("If you have not run the demo yet, execute: python -m cli.anom_score demo")
