import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px

# ---------- Supabase Setup ----------
SUPABASE_URL = "https://orcofktzjrbbjczcqqrg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9yY29ma3R6anJiYmpjemNxcXJnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgzMjMxOTUsImV4cCI6MjA2Mzg5OTE5NX0.V2lxi3pZZzPuUX3uUjt8I1ZML_uLTbkDFDTxvcEbQ9I"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Restoration CRM & Cash Flow", layout="wide")
st.title("🔧 Restoration CRM + Cash Flow Tool")

# ---------- Helpers ----------
def fetch_data(table):
    try:
        res = supabase.table(table).select("*").execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"❌ Error fetching {table}: {e}")
        return pd.DataFrame()

def insert_data(table, data_dict):
    try:
        supabase.table(table).insert([data_dict], returning="minimal").execute()
        st.success("✅ Data Added")
    except Exception as e:
        st.error(f"❌ Insert failed: {e}")

def update_data(table, record_id, data_dict):
    try:
        supabase.table(table).update(data_dict).eq("id", record_id).execute()
        st.success("✅ Data Updated")
    except Exception as e:
        st.error(f"❌ Update failed: {e}")

# ---------- Projects ----------
st.header("📁 Projects")
with st.expander("➕ Add Project"):
    name = st.text_input("Project Name")
    lead = st.text_input("Lead Name")
    job_type = st.selectbox("Job Type", ["Water", "Fire", "Mold", "Other"])
    gross_profit = st.number_input("Gross Profit", step=100.0)
    date = st.date_input("Start Date", datetime.today())
    if st.button("Add Project"):
        if name and lead:
            insert_data("projects", {
                "name": name,
                "lead": lead,
                "job_type": job_type,
                "gross_profit": gross_profit,
                "date": date.isoformat()
            })
        else:
            st.warning("❗ Please enter both project name and lead.")

projects_df = fetch_data("projects")
if not projects_df.empty:
    st.dataframe(projects_df)
    st.download_button("📥 Download Projects CSV", projects_df.to_csv(index=False), "projects.csv")

# ---------- Collections ----------
st.header("💰 Collections")
with st.expander("➕ Add Collection"):
    project_options = projects_df["name"].tolist()
    selected_proj = st.selectbox("Linked Project", project_options)
    amount = st.number_input("Amount", step=100.0)
    due_date = st.date_input("Expected Date", datetime.today())
    status = st.selectbox("Status", ["Pending", "Paid", "Late"])
    if st.button("Add Collection"):
        if selected_proj:
            insert_data("collections", {
                "project_name": selected_proj,
                "amount": amount,
                "expected_date": due_date.isoformat(),
                "status": status
            })
        else:
            st.warning("❗ Select a project for the collection.")

collections_df = fetch_data("collections")
if not collections_df.empty:
    st.dataframe(collections_df)
    st.download_button("📥 Download Collections CSV", collections_df.to_csv(index=False), "collections.csv")

# ---------- Expenses ----------
st.header("📉 Expenses / AP")
with st.expander("➕ Add Expense / AP"):
    selected_proj_exp = st.selectbox("Linked Project", project_options, key="exp")
    expense_amt = st.number_input("Expense Amount", step=100.0)
    due_date_exp = st.date_input("Due Date", datetime.today(), key="exp_date")
    urgency = st.selectbox("Urgency", ["Critical", "Flexible", "Low"])
    vendor = st.text_input("Vendor")
    recurring = st.checkbox("Recurring Payroll?")
    if st.button("Add Expense"):
        if selected_proj_exp and vendor:
            insert_data("expenses", {
                "project_name": selected_proj_exp,
                "amount": expense_amt,
                "due_date": due_date_exp.isoformat(),
                "urgency": urgency,
                "vendor": vendor,
                "recurring": recurring
            })
        else:
            st.warning("❗ Enter both project and vendor for the expense.")

expenses_df = fetch_data("expenses")
if not expenses_df.empty:
    st.dataframe(expenses_df)
    st.download_button("📥 Download Expenses CSV", expenses_df.to_csv(index=False), "expenses.csv")

# ---------- Cash Flow Forecast ----------
st.header("📊 Cash Flow Forecast")
cash_balance = st.number_input("💵 Current Cash Balance", value=0.0, step=100.0)

# Forecast inflows (check for empty or missing columns)
if not collections_df.empty and "status" in collections_df.columns and "expected_date" in collections_df.columns:
    future_collections = collections_df[
        (collections_df["status"] != "Paid") &
        (pd.to_datetime(collections_df["expected_date"]) >= datetime.today())
    ]
    inflows = future_collections.groupby("expected_date")["amount"].sum().reset_index()
    inflows.columns = ["date", "inflow"]
else:
    inflows = pd.DataFrame(columns=["date", "inflow"])

# Forecast outflows (check for empty or missing columns)
if not expenses_df.empty and "due_date" in expenses_df.columns:
    future_expenses = expenses_df[
        pd.to_datetime(expenses_df["due_date"]) >= datetime.today()
    ]
    outflows = future_expenses.groupby("due_date")["amount"].sum().reset_index()
    outflows.columns = ["date", "outflow"]
else:
    outflows = pd.DataFrame(columns=["date", "outflow"])

# Merge inflows/outflows and calculate cash balance
forecast_df = pd.merge(inflows, outflows, on="date", how="outer").fillna(0)
forecast_df = forecast_df.sort_values("date")
forecast_df["cash_balance"] = cash_balance + forecast_df["inflow"].cumsum() - forecast_df["outflow"].cumsum()

st.subheader("📅 Weekly Forecast")
st.dataframe(forecast_df)

fig = px.bar(forecast_df, x="date", y=["inflow", "outflow", "cash_balance"],
             title="Cash Flow Forecast", barmode="group")
st.plotly_chart(fig, use_container_width=True)

# ---------- AP Prioritization ----------
st.header("🚨 AP Prioritization Matrix")
if not expenses_df.empty:
    priority = expenses_df.copy()
    priority["urgency_score"] = priority["urgency"].map({"Critical": 3, "Flexible": 2, "Low": 1})
    priority = priority.sort_values(["urgency_score", "amount"], ascending=[False, False])
    st.dataframe(priority[["vendor", "project_name", "amount", "urgency", "due_date"]])

    st.info("Pay highest urgency items first. Use the forecast chart to plan when each can be paid.")

# ---------- Footer ----------
st.markdown("---")
st.markdown("Made with ❤️ for restoration operations. Contact your developer for help.")