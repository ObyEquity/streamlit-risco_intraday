import streamlit as st
from supabase import create_client, Client

url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]

supabase: Client = create_client(url, key)