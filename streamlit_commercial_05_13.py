import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets Auth
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

product_hierarchy = {
    "Update Search": 1, "Current Owner Search": 2, "Two Owner Search": 3,
    "Full 30 YR Search": 4, "Full 40 YR Search": 5, "Full 50 YR Search": 6,
    "Full 60 YR Search": 7, "Full 80 YR Search": 8, "Full 100 YR Search": 9,
}

st.title("Commercial Prediction Model (05/13/25)")
st.markdown("**Disclaimer:** Predicted pricing is based on a single parcel search.")

if not df.empty:
    # Dropdown for 'Mapped Type' with 'Other' option
    mapped_type_options = list(df["Mapped Type"].unique()) + ["Other"]
    mapped_type = st.selectbox("Select Mapped Type", mapped_type_options)
    if mapped_type == "Other":
        mapped_type = st.text_input("Enter your Mapped Type:")
    
    # Dropdown for 'Mapped Product Ordered' with 'Other' option
    mapped_product_options = list(df["Mapped Product Ordered"].unique()) + ["Other"]
    mapped_product = st.selectbox("Select Mapped Product Ordered", mapped_product_options)
    if mapped_product == "Other":
        mapped_product = st.text_input("Enter your Mapped Product Ordered:")
    
    # Dropdown for 'Online/Offline' with 'Other' option
    online_offline_options = list(df["Offline/Online"].unique())
    online_offline = st.selectbox("Select Online/Offline", online_offline_options)

    # Filter Data based on user selections or "Other" inputs
    filtered_df = df[
        (df["Mapped Type"] == mapped_type) & 
        (df["Mapped Product Ordered"] == mapped_product) &
        (df["Offline/Online"] == online_offline)
    ]

    if st.button("Predict Pricing"):
        if not filtered_df.empty:
            row = filtered_df.iloc[0]

            adjusted_mean = row["Adjusted Forecasted Pricing (mean)"]
            adjusted_median = row["Adjusted Forecasted Pricing (median)"]
            smoothed_mean = row["Smoothed Forecasted Pricing (mean)"]
            smoothed_median = row["Smoothed Forecasted Pricing (median)"]
            predicted_mean = row.get("Predicted Forecasted Pricing (mean)")
            predicted_median = row.get("Predicted Forecasted Pricing (median)")

            # Prediction options with sorting based on the lower limit of the range (ascending order)
            prediction_options = {
                "Adjusted Mean – Smoothed Mean": sorted([adjusted_mean, smoothed_mean]),
                "Adjusted Median – Smoothed Median": sorted([adjusted_median, smoothed_median]),
                "Adjusted Mean – Adjusted Median": sorted([adjusted_mean, adjusted_median]),
                "Smoothed Mean – Smoothed Median": sorted([smoothed_mean, smoothed_median]),
            }

            # Sort the options by the first value (lower limit) of each pair
            sorted_prediction_options = dict(sorted(prediction_options.items(), key=lambda item: item[1][0]))

            # Format the options with correct display
            formatted_options = {}
            seen_ranges = set()

            for label, values in sorted_prediction_options.items():
                lo, hi = values[0], values[1]
                if lo == hi:  # If both values are the same, display as "$lo - $lo"
                    option_text = f"{label} ${lo:,.2f} - ${lo:,.2f}"
                else:  # Otherwise display the range with $ symbol for both values
                    option_text = f"{label} ${lo:,.2f} - ${hi:,.2f}"

                range_key = (round(lo, 2), round(hi, 2))
                if range_key not in seen_ranges:
                    seen_ranges.add(range_key)
                    formatted_options[option_text] = (label, lo, hi)

            st.session_state.prediction_choices = formatted_options
            st.session_state.selection_made = False
            st.session_state.selected_entry = None

        else:
            # If no match is found for the custom data, ask the user to manually input the prediction
            st.warning("No matching data found. Please enter the predicted price manually.")
            manual_predicted_value = st.number_input("Enter Predicted Price", min_value=0.0, format="%.2f")
            st.session_state.selection_made = True
            st.session_state.selected_entry = ("Manual", "Manual Entry", manual_predicted_value, '')

    if "prediction_choices" in st.session_state:
        st.subheader("Select Closest Price Range")
        selected_text = st.radio(
            "Choose range:",
            options=list(st.session_state.prediction_choices.keys()) + ["Other (Enter manually)"],
            index=None,
            format_func=lambda x: x,
            label_visibility="collapsed"
        )

        if selected_text:
            if selected_text == "Other (Enter manually)":
                manual_entry = st.number_input("Enter your own predicted value:", min_value=0.0, format="%.2f")
                st.session_state.selection_made = True
                st.session_state.selected_entry = ("Manual", "Manual Entry", manual_entry, '')
            else:
                st.session_state.selection_made = True
                st.session_state.selected_entry = st.session_state.prediction_choices[selected_text]
                st.success(f"You selected: {selected_text}")

    if st.session_state.get("selection_made", False) and st.button("Submit to Sheet"):
        label, lo, hi = st.session_state.selected_entry
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d")
        sheet_name = "User Prediction Selections"

        try:
            try:
                submission_sheet = sheet.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                submission_sheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
                submission_sheet.append_row([
                    "Mapped Type", "Mapped Product Ordered", "Offline/Online",
                    "Selection Label", "Selected Range", "Range Start", "Range End", "Timestamp"
                ])

            existing = submission_sheet.get_all_records()
            duplicate = any(
                row["Mapped Type"] == mapped_type and
                row["Mapped Product Ordered"] == mapped_product and
                row["Offline/Online"] == online_offline and
                row["Selected Range"] == label
                for row in existing
            )

            if duplicate:
                st.warning("You've already submitted this selection.")
            else:
                submission_sheet.append_row([
                    mapped_type, mapped_product, online_offline,
                    label,
                    lo if label == "Manual Entry" else lo,
                    hi,
                    timestamp
                ])
                st.success("Your selected range has been recorded.")
                
        except Exception as e:
            st.error(f"Failed to record selection: {e}")

else:
    st.warning("No prediction file found. Run the pipeline first.")
