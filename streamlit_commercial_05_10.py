import streamlit as st
import pandas as pd
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup

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

st.title("Commercial Prediction Model (05/20/25)")
st.markdown("**Disclaimer:** Predicted pricing is based on a single parcel search.")

if not df.empty:
    mapped_type_options = list(df["Mapped Type"].unique()) + ["Other"]
    mapped_type = st.selectbox("Select Mapped Type", mapped_type_options)
    if mapped_type == "Other":
        mapped_type = st.text_input("Enter your Mapped Type:")

    mapped_product = st.selectbox("Select Mapped Product Ordered", list(product_hierarchy.keys()))
    online_offline = st.selectbox("Select Online/Offline", ["Online", "Ground"])

    if st.button("Predict Pricing"):
        filtered_df = df[
            (df["Mapped Type"] == mapped_type) &
            (df["Mapped Product Ordered"] == mapped_product) &
            (df["Offline/Online"] == online_offline)
        ]

        if not filtered_df.empty:
            row = filtered_df.iloc[0]

            adjusted_mean = row["Adjusted Forecasted Pricing (mean)"]
            adjusted_median = row["Adjusted Forecasted Pricing (median)"]
            smoothed_mean = row["Smoothed Forecasted Pricing (mean)"]
            smoothed_median = row["Smoothed Forecasted Pricing (median)"]
            predicted_mean = row.get("Predicted Forecasted Pricing (mean)")
            predicted_median = row.get("Predicted Forecasted Pricing (median)")

            prediction_options = {
                "A.": ("Adjusted Mean – Smoothed Mean", sorted([adjusted_mean, smoothed_mean])),
                "B.": ("Adjusted Median – Smoothed Median", sorted([adjusted_median, smoothed_median])),
                "C.": ("Adjusted Mean – Adjusted Median", sorted([adjusted_mean, adjusted_median])),
                "D.": ("Smoothed Mean – Smoothed Median", sorted([smoothed_mean, smoothed_median])),
            }

            if predicted_mean is not None and predicted_median is not None:
                prediction_options["E."] = ("Predicted Mean – Predicted Median", sorted([predicted_mean, predicted_median]))

            sorted_prediction_options = dict(sorted(prediction_options.items(), key=lambda item: item[1][0]))

            formatted_options = {}
            seen_ranges = set()

            for label, (desc, values) in sorted_prediction_options.items():
                lo, hi = [int(-(-x // 5) * 5) for x in values]
                range_key = (lo, hi)
                if range_key not in seen_ranges:
                    seen_ranges.add(range_key)
                    option_text = f"${lo:,} – ${hi:,}"
                    formatted_options[option_text] = (label, desc, lo, hi)

            st.session_state.prediction_choices = formatted_options
            st.session_state.selection_made = False
            st.session_state.selected_entry = None

        else:
            st.session_state.prediction_choices = {}  # Clear previous predictions
            manual_entry = st.number_input("No prediction found. Enter your own predicted value:", min_value=0, format="%d")
            st.session_state.selection_made = True
            st.session_state.selected_entry = ("Manual", "New Manual Entry", manual_entry, '')

if "prediction_choices" in st.session_state and st.session_state.prediction_choices:
    st.subheader("Select Closest Price Range")
    st.markdown("<style>div.row-widget.stRadio > div{flex-direction: column;}</style>", unsafe_allow_html=True)
    selected_text = st.radio(
        "Choose range:",
        options=sorted(list(st.session_state.prediction_choices.keys()), key=lambda x: int(x.strip('$').split('–')[0].replace(',', '').strip())) + ["Other (Enter manually)"],
        index=None,
        label_visibility="collapsed"
    )

    if selected_text:
        if selected_text == "Other (Enter manually)":
            manual_entry = st.number_input("Enter your own predicted value:", min_value=0, format="%d")
            st.session_state.selection_made = True
            st.session_state.selected_entry = ("Manual", "New Manual Entry", manual_entry, '')
        else:
            st.session_state.selection_made = True
            st.session_state.selected_entry = st.session_state.prediction_choices[selected_text]
            st.success(f"You selected: {selected_text}")

if st.session_state.get("selection_made", False) and st.button("Submit to Sheet"):
    label, desc, lo, hi = st.session_state.selected_entry
    timestamp = pd.Timestamp.now().strftime("%Y-%m-%d")
    sheet_name = "User Prediction Selections"

    try:
        try:
            submission_sheet = sheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            submission_sheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="20")

        expected_headers = [
            "Mapped Type", "Mapped Product Ordered", "Offline/Online",
            "Selection Label", "Selected Range", "Range Start", "Range End", "Timestamp"
        ]
        existing_data = submission_sheet.get_all_values()
        if not existing_data or existing_data[0] != expected_headers:
            submission_sheet.clear()
            submission_sheet.append_row(expected_headers)

        existing = submission_sheet.get_all_records()
        duplicate = any(
            row["Mapped Type"] == mapped_type and
            row["Mapped Product Ordered"] == mapped_product and
            row["Offline/Online"] == online_offline and
            row["Selection Label"] == label
            for row in existing
        )

        if duplicate:
            st.warning("You've already submitted this selection.")
        else:
            selected_range_text = f"${int(lo):,}" if hi == '' else f"${int(lo):,} – ${int(hi):,}"
            submission_sheet.append_row([
                mapped_type, mapped_product, online_offline,
                label,
                selected_range_text,
                int(lo),
                int(hi) if hi != '' else '',
                timestamp
            ])
            st.success("Your selected range has been recorded.")
    except Exception as e:
        st.error(f"Failed to record selection: {e}")
