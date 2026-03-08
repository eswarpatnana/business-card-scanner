import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import numpy as np
import re
import os
import cv2

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

file = "scanned_cards.xlsx"

# Sidebar Menu
menu = st.sidebar.selectbox(
    "Menu",
    ["Scan Card", "View Contacts"]
)

# ---------------- SCAN CARD ----------------

if menu == "Scan Card":

    st.title("📇 AI Business Card Scanner")

    option = st.radio(
        "Choose Input Method",
        ["Upload Image", "Use Camera"]
    )

    image = None

    if option == "Upload Image":
        uploaded = st.file_uploader("Upload Business Card", type=["jpg","png","jpeg"])
        if uploaded:
            image = Image.open(uploaded)

    if option == "Use Camera":
        camera_image = st.camera_input("Take a photo")
        if camera_image:
            image = Image.open(camera_image)

    if image is not None:

        st.image(image, caption="Business Card", use_column_width=True)

        # Convert image for OpenCV
        img = np.array(image)

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Improve contrast
        gray = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )

        reader = easyocr.Reader(['en'])

        result = reader.readtext(gray, detail=0)

        text = " ".join(result)

        st.subheader("Detected Text")
        st.write(text)

        # Extract Email
        email = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)

        # Extract Phone
        phone = re.findall(r"\+?\d[\d\s\-]{7,15}", text)

        # Extract Website
        website = re.findall(r"(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", text)

        # Guess Name
        name = ""
        for line in result:
            if not re.search(r'\d', line) and len(line.split()) <= 3:
                name = line
                break

        # Guess Occupation
        occupation = ""
        if len(result) > 1:
            occupation = result[1]

        st.subheader("Detected Details")

        st.write("👤 Name:", name)
        st.write("💼 Occupation:", occupation)
        st.write("📧 Email:", email[0] if email else "")
        st.write("📞 Phone:", phone[0] if phone else "")
        st.write("🌐 Website:", website[0] if website else "")

        data = {
            "Name":[name],
            "Occupation":[occupation],
            "Email":[email[0] if email else ""],
            "Phone":[phone[0] if phone else ""],
            "Website":[website[0] if website else ""]
        }

        df = pd.DataFrame(data)

        if os.path.exists(file):

            old_df = pd.read_excel(file)

            new_df = pd.concat([old_df, df], ignore_index=True)

            new_df.to_excel(file, index=False)

        else:

            df.to_excel(file, index=False)

        st.success("Details saved to Excel!")

# ---------------- VIEW CONTACTS ----------------

if menu == "View Contacts":

    st.title("📂 Saved Contacts")

    if os.path.exists(file):

        saved_df = pd.read_excel(file)

        st.dataframe(saved_df)

    else:

        st.warning("No contacts saved yet.")

