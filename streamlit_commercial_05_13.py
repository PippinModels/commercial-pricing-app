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
    mapped_type = st.selectbox("Select Mapped Type", df["Mapped Type"].unique())
    filtered_df_type = df[df["Mapped Type"] == mapped_type]

    sorted_products = sorted(filtered_df_type["Mapped Product Ordered"].unique(),
                             key=lambda x: product_hierarchy.get(x, float("inf")))
    mapped_product = st.selectbox("Select Mapped Product Ordered", sorted_products)

    filtered_df_product = filtered_df_type[filtered_df_type["Mapped Product Ordered"] == mapped_product]
    online_offline = st.selectbox("Select Online/Offline", filtered_df_product["Offline/Online"].unique())

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

            # Create list of options - this time using simple key codes to avoid formatting issues
            # We'll use codes like "A", "B", etc. for the radio buttons
            prediction_pairs = [
                ("A", "Adjusted Mean – Smoothed Mean", adjusted_mean, smoothed_mean),
                ("B", "Adjusted Median – Smoothed Median", adjusted_median, smoothed_median),
                ("C", "Adjusted Mean – Adjusted Median", adjusted_mean, adjusted_median),
                ("D", "Smoothed Mean – Smoothed Median", smoothed_mean, smoothed_median),
            ]
            
            if predicted_mean is not None and predicted_median is not None:
                prediction_pairs.append(("E", "Predicted Mean – Predicted Median", predicted_mean, predicted_median))
            
            # Filter for unique ranges only
            unique_pairs = []
            seen_ranges = set()
            
            for label, desc, val1, val2 in prediction_pairs:
                # Sort values to ensure low-high order
                lo, hi = min(val1, val2), max(val1, val2)
                
                range_key = (round(lo, 2), round(hi, 2))
                if range_key not in seen_ranges:
                    seen_ranges.add(range_key)
                    unique_pairs.append((label, desc, lo, hi))
            
            st.session_state.prediction_pairs = unique_pairs
            st.session_state.selection_made = False
            st.session_state.selected_entry = None

    # Display price range options if available
    if "prediction_pairs" in st.session_state:
        st.subheader("Select Closest Price Range")
        
        # Create a list of simple codes for the radio button
        option_keys = [pair[0] for pair in st.session_state.prediction_pairs] + ["Other"]
        
        # Use a simple radio button with codes only
        selected_key = st.radio(
            "Choose range:",
            options=option_keys,
            index=None,
            label_visibility="collapsed"
        )
        
        # Display the formatted options separately as a reference table
        for label, desc, lo, hi in st.session_state.prediction_pairs:
            st.markdown(f"**{label}. ${lo:.2f} - ${hi:.2f}**")
        
        if selected_key:
            if selected_key == "Other":
                manual_entry = st.number_input("Enter your own predicted value:", min_value=0.0, format="%.2f")
                st.session_state.selection_made = True
                st.session_state.selected_entry = ("Manual", "Manual Entry", manual_entry, None)
            else:
                # Find the matching entry based on the selected key
                for label, desc, lo, hi in st.session_state.prediction_pairs:
                    if label == selected_key:
                        st.session_state.selection_made = True
                        st.session_state.selected_entry = (label, desc, lo, hi)
                        st.success(f"You selected: {label}. ${lo:.2f} - ${hi:.2f}")
                        break

    if st.session_state.get("selection_made", False) and st.button("Submit to Sheet"):
        label, desc, lo, hi = st.session_state.selected_entry
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
                # For manual entry, hi might be None
                hi_value = hi if hi is not None else ""
                
                submission_sheet.append_row([
                    mapped_type, mapped_product, online_offline,
                    label,
                    desc,
                    lo if label != "Manual" else manual_entry,
                    hi_value,
                    timestamp
                ])
                st.success("Your selected range has been recorded.")
                
        except Exception as e:
            st.error(f"Failed to record selection: {e}")

else:
    st.warning("No prediction file found. Run the pipeline first.")
