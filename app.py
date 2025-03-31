import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Authenticate with Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("commercial-pricing-pipeline-5646db7d6064.json", scope)
client = gspread.authorize(creds)

# Open the Google Sheet by ID and get the "Summary Sheet"
spreadsheet_id = "1j98zwn4qc6oq0GKnGapaOyMjaw_zWPvwvqTkSDL4dB8"
sheet = client.open_by_key(spreadsheet_id)
summary_sheet = sheet.worksheet("Summary Sheet")

# Convert to DataFrame
data = summary_sheet.get_all_records()
df = pd.DataFrame(data)

product_hierarchy = {
    "Update Search": 1,
    "Current Owner Search": 2,
    "Two Owner Search": 3,
    "Full 30 YR Search": 4,
    "Full 40 YR Search": 5,
    "Full 50 YR Search": 6,
    "Full 60 YR Search": 7,
    "Full 80 YR Search": 8,
    "Full 100 YR Search": 9,
}

st.title("Commercial Prediction Model")

if not df.empty:
    mapped_type = st.selectbox("Select Mapped Type", df["Mapped Type"].unique())
    filtered_df_type = df[df["Mapped Type"] == mapped_type]

    unique_products = filtered_df_type["Mapped Product Ordered"].unique()
    sorted_products = sorted(unique_products, key=lambda x: product_hierarchy.get(x, float("inf")))
    mapped_product = st.selectbox("Select Mapped Product Ordered", sorted_products)
    filtered_df_product = filtered_df_type[filtered_df_type["Mapped Product Ordered"] == mapped_product]

    unique_online_offline = filtered_df_product["Offline/Online"].unique()
    online_offline = st.selectbox("Select Online/Offline", unique_online_offline)
    filtered_df = filtered_df_product[filtered_df_product["Offline/Online"] == online_offline]

    if st.button("Predict Pricing"):
        if not filtered_df.empty:
            row = filtered_df.iloc[0]
            adjusted_pricing = row["Adjusted Predicted Pricing"]
            st.subheader("Predicted Pricing")
            st.markdown(f"<h4> ${adjusted_pricing:,.2f}</h4>", unsafe_allow_html=True)
        else:
            st.warning("No predictions available for the selected criteria.")
else:
    st.warning("No prediction file found. Run the pipeline first.")
