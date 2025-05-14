import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# -----------------------------
# GOOGLE SHEETS SETUP
# -----------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
json_key = st.secrets["google_sheets"]["json_key"]
service_account_info = json.loads(json_key)
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)

spreadsheet_id = "1YYPoxD46Z0-_BrQhjdDPpU5sSDHwr62j72am5u7wjGE"
sheet = client.open_by_key(spreadsheet_id)
summary_sheet = sheet.worksheet("Summary Sheet")

# Load data
data = summary_sheet.get_all_records()
df = pd.DataFrame(data)

# Hierarchy setup
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

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.title("Commercial Prediction Model (05/13/25)")

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

    if "prediction_ready" not in st.session_state:
        st.session_state.prediction_ready = False

    if st.button("Predict Pricing"):
        if not filtered_df.empty:
            row = filtered_df.iloc[0]

            # Extract pricing values
            adjusted_mean = row["Adjusted Forecasted Pricing (mean)"]
            adjusted_median = row["Adjusted Forecasted Pricing (median)"]
            smoothed_mean = row["Smoothed Forecasted Pricing (mean)"]
            smoothed_median = row["Smoothed Forecasted Pricing (median)"]
            predicted_mean = row.get("Predicted Forecasted Pricing (mean)")
            predicted_median = row.get("Predicted Forecasted Pricing (median)")

            raw_options = {
                "A. Adjusted Mean – Smoothed Mean": [adjusted_mean, smoothed_mean],
                "B. Adjusted Median – Smoothed Median": [adjusted_median, smoothed_median],
                "C. Adjusted Mean – Adjusted Median": [adjusted_mean, adjusted_median],
                "D. Smoothed Mean – Smoothed Median": [smoothed_mean, smoothed_median],
            }

            if predicted_mean is not None and predicted_median is not None:
                raw_options["E. Predicted Mean – Predicted Median"] = [predicted_mean, predicted_median]

            # Deduplicate
            seen_ranges = set()
            prediction_options = {}
            for label, values in raw_options.items():
                lo, hi = sorted(values)
                range_key = (round(lo, 2), round(hi, 2))
                if range_key not in seen_ranges:
                    seen_ranges.add(range_key)
                    label_with_range = f"{label}: ${lo:,.2f} – ${hi:,.2f}"
                    prediction_options[label_with_range] = [lo, hi]

            # Save to session
            st.session_state.prediction_ready = True
            st.session_state.prediction_options = prediction_options
            st.session_state.filtered_data = {
                "mapped_type": mapped_type,
                "mapped_product": mapped_product,
                "online_offline": online_offline
            }

# Display radio and submit only after pricing is predicted
if st.session_state.get("prediction_ready", False):
    selected_range_label = st.radio(
        "Select the Price Range:",
        options=list(st.session_state.prediction_options.keys()),
        index=None,
        key="selected_range"
    )

    if st.button("Submit Selection"):
        if st.session_state.selected_range:
            selected_range_values = st.session_state.prediction_options[st.session_state.selected_range]
            st.success(f"Selected Range: {st.session_state.selected_range}")

            try:
                timestamp = pd.Timestamp.now().strftime("%Y-%m-%d")
                sheet_name = "Predictions Selections"

                # Try to open or create worksheet
                try:
                    submission_sheet = sheet.worksheet(sheet_name)
                except gspread.exceptions.WorksheetNotFound:
                    sheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
                    sheet = client.open_by_key(spreadsheet_id)  # Refresh sheet reference
                    submission_sheet = sheet.worksheet(sheet_name)
                    submission_sheet.append_row([
                        "Timestamp", "Mapped Type", "Mapped Product Ordered", "Offline/Online",
                        "Selected Range Label", "Range Start", "Range End"
                    ])

                submission_sheet.append_row([
                    timestamp,
                    st.session_state.filtered_data["mapped_type"],
                    st.session_state.filtered_data["mapped_product"],
                    st.session_state.filtered_data["online_offline"],
                    st.session_state.selected_range,
                    selected_range_values[0],
                    selected_range_values[1]
                ])
                st.success("Your selected range has been recorded.")
            except Exception as e:
                st.error(f"Failed to record selection: {e}")
else:
    st.warning("No prediction file found. Run the pipeline first.")

