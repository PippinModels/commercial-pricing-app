import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
json_key = st.secrets["google_sheets"]["json_key"]
service_account_info = json.loads(json_key)
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)

spreadsheet_id = "1YYPoxD46Z0-_BrQhjdDPpU5sSDHwr62j72am5u7wjGE"
sheet = client.open_by_key(spreadsheet_id)
summary_sheet = sheet.worksheet("Summary Sheet")

# Convert to DataFrame
data = summary_sheet.get_all_records()
df = pd.DataFrame(data)

# Define hierarchy
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
st.title("Commercial Prediction Model (05/13/25)")
st.subheader("Predicted pricing is based on a single parcel search")

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


            adjusted_mean = row["Adjusted Forecasted Pricing (mean)"]
            adjusted_median = row["Adjusted Forecasted Pricing (median)"]
            smoothed_mean = row["Smoothed Forecasted Pricing (mean)"]
            smoothed_median = row["Smoothed Forecasted Pricing (median)"]
            predicted_mean = row.get("Predicted Forecasted Pricing (mean)")
            predicted_median = row.get("Predicted Forecasted Pricing (median)")


            prediction_options = {
                " Adjusted Mean – Smoothed Mean": sorted([adjusted_mean, smoothed_mean]),
                " Adjusted Median – Smoothed Median": sorted([adjusted_median, smoothed_median]),
                " Adjusted Mean – Adjusted Median": sorted([adjusted_mean, adjusted_median]),
                " Smoothed Mean – Smoothed Median": sorted([smoothed_mean, smoothed_median]),
            }

            if predicted_mean is not None and predicted_median is not None:
              prediction_options[" Predicted Mean – Predicted Median"] = sorted([predicted_mean, predicted_median])



            st.subheader("Select Closest Price range")
            selected_range_label = st.radio("Choose range:", list(prediction_options.keys()))

            if selected_range_label:
                selected_range_values = prediction_options[selected_range_label]
                st.success(f"You selected: {selected_range_label}")


                try:
                    timestamp = pd.Timestamp.now().strftime("%Y-%m-%d")
                    sheet_name = "User Prediction Selections"

                    try:
                        submission_sheet = sheet.worksheet(sheet_name)
                    except gspread.exceptions.WorksheetNotFound:
                        submission_sheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
                        submission_sheet.append_row([
                             "Mapped Type", "Mapped Product Ordered", "Offline/Online",
                            "Selected Range", "Range Start", "Range End", "Timestamp",
                        ])

                    submission_sheet.append_row([
                        timestamp, mapped_type, mapped_product, online_offline,
                        selected_range_label, selected_range_values[0], selected_range_values[1]
                    ])
                    st.success("Your selected range has been recorded.")
                except Exception as e:
                    st.error(f"Failed to record selection: {e}")
else:
    st.warning("No prediction file found. Run the pipeline first.")
