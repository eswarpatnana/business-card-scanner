import streamlit as st
from PIL import Image
import pytesseract
import pandas as pd
import re
import os

# Mobile friendly layout
st.set_page_config(
    page_title="AI Business Card Scanner",
    page_icon="📇",
    layout="centered"
)

st.title("📇 AI Business Card Scanner")

st.write(
"Scan business cards using your camera or upload an image to automatically extract contact details."
)

menu = st.sidebar.radio("Navigation", ["Scan Card", "View Contacts"])


# =========================
# SCAN CARD PAGE
# =========================

if menu == "Scan Card":

    st.header("Scan Business Card")

    camera_photo = st.camera_input("📷 Scan with Camera")

    uploaded_file = st.file_uploader(
        "📂 Upload Business Card Image",
        type=["png","jpg","jpeg"]
    )

    image = None

    if camera_photo is not None:
        image = Image.open(camera_photo)

    elif uploaded_file is not None:
        image = Image.open(uploaded_file)

    if image is not None:

        st.image(image, caption="Captured Card", use_column_width=True)

        text = pytesseract.image_to_string(image)

        st.subheader("Extracted Text")
        st.write(text)

        # Detect email
        email = re.findall(r'\S+@\S+', text)

        # Detect phone
        phone = re.findall(r'\+?\d[\d -]{8,12}\d', text)

        # Detect website
        website = re.findall(r'www\.\S+', text)

        lines = text.split("\n")

        name = ""
        occupation = ""

        for line in lines:

            if len(line.split()) == 2 and name == "":
                name = line

            if (
                "manager" in line.lower()
                or "consultant" in line.lower()
                or "designer" in line.lower()
                or "developer" in line.lower()
                or "engineer" in line.lower()
                or "sales" in line.lower()
            ):
                occupation = line

        st.markdown("### Contact Details")

        st.info(f"""
👤 Name: {name}

💼 Occupation: {occupation}

📧 Email: {email[0] if email else ""}

📞 Phone: {phone[0] if phone else ""}

🌐 Website: {website[0] if website else ""}
""")

        new_data = pd.DataFrame([{
            "Name": name,
            "Occupation": occupation,
            "Email": email[0] if email else "",
            "Phone": phone[0] if phone else "",
            "Website": website[0] if website else ""
        }])

        if os.path.exists("scanned_cards.xlsx"):

            saved_df = pd.read_excel("scanned_cards.xlsx")

            saved_df = pd.concat([saved_df, new_data], ignore_index=True)

            saved_df = saved_df.drop_duplicates(subset=["Email"], keep="first")

        else:

            saved_df = new_data

        saved_df.to_excel("scanned_cards.xlsx", index=False)

        st.success("Contact saved successfully!")


# =========================
# VIEW CONTACTS PAGE
# =========================

if menu == "View Contacts":

    if os.path.exists("scanned_cards.xlsx"):

        saved_df = pd.read_excel("scanned_cards.xlsx")

        st.subheader("Saved Contacts Database")

        st.write("Total Contacts:", len(saved_df))

        search = st.text_input("Search Contact")

        if search:

            filtered_df = saved_df[
                saved_df.apply(lambda row: search.lower() in str(row).lower(), axis=1)
            ]

            st.dataframe(filtered_df)

        else:

            st.dataframe(saved_df)

        with open("scanned_cards.xlsx","rb") as file:

            st.download_button(
                "Download Contacts Excel",
                file,
                "contacts_database.xlsx"
            )

        if st.button("Clear Database"):

            os.remove("scanned_cards.xlsx")

            st.success("Database cleared!")

    else:

        st.warning("No contacts saved yet.")