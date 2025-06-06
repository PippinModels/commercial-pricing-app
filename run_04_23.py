import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Authenticate with Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("/content/drive/MyDrive/Commercial Data Files/commercial-pricing-pipeline-5646db7d6064.json", scope)

client = gspread.authorize(creds)


# Open the latest Google Sheet
spreadsheet_id = "18Ile59_KqYt1VXixYHNaUE7-NXaMx4Wdu4VpnsBbURM"
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
    mapped_type = st.selectbox("Select Mapped Type", df["usedesc"].unique())
    filtered_df_type = df[df["usedesc"] == mapped_type]

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

          # Base prediction
          adjusted_pricing = row["Adjusted Forecasted Pricing (mean)"]

          # Calculate ranges
          f_mean = row["Forecasted Pricing (mean)"]
          s_mean = row["Smoothed Forecasted Pricing (mean)"]
          mean_range = sorted([f_mean, s_mean])  # always small to large

          f_median = row["Forecasted Pricing (median)"]
          s_median = row["Smoothed Forecasted Pricing (median)"]
          median_range = sorted([f_median, s_median])  # always small to large

          # Display results
          st.subheader("Predicted Pricing")
          st.markdown(f"<h4> ${adjusted_pricing:,.2f}</h4>", unsafe_allow_html=True)

          st.markdown(f"**Forecasted Mean Range:** ${mean_range[0]:,.2f} – ${mean_range[1]:,.2f}")
          st.markdown(f"**Forecasted Median Range:** ${median_range[0]:,.2f} – ${median_range[1]:,.2f}")

    else:
        st.warning("No predictions available for the selected criteria.")
else:
    st.warning("No prediction file found. Run the pipeline first.")

