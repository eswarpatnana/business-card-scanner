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

menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts"])

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

# ---------------- SCAN CARD ----------------

if menu == "Scan Card":

    st.title("📇 AI Business Card Scanner")

    option = st.radio("Choose Input Method", ["Upload Image", "Use Camera"])

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

        img = np.array(image)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        gray = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )

        result = reader.readtext(gray, detail=0)

        text = " ".join(result)

        # Fix common OCR mistakes
        text = text.replace(" com", ".com")
        text = text.replace(" .com", ".com")
        text = text.replace("WWW", "www")
        text = text.replace(";", ".")

        st.subheader("Detected Text")
        st.write(text)

        # -------- Extract Email --------
        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        email = email_match.group() if email_match else ""

        # -------- Extract Phone --------
        phone_match = re.search(r"\+?\d[\d\-\.\s]{7,}\d", text)
        phone = phone_match.group() if phone_match else ""

        # -------- Extract Website --------
        website_match = re.search(r"(www\.[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
        website = website_match.group() if website_match else ""

        # -------- Detect Name --------
        name = ""
        words = text.split()

        for i in range(len(words)-1):
            if words[i].isalpha() and words[i+1].isalpha():
                if words[i][0].isupper() and words[i+1][0].isupper():
                    name = words[i] + " " + words[i+1]
                    break

        # -------- Detect Occupation --------
        occupation_keywords = [
            "manager","consultant","engineer","developer",
            "designer","director","founder","marketing",
            "sales","graphic","ceo","analyst"
        ]

        occupation = ""

        for line in result:
            lower = line.lower()
            for key in occupation_keywords:
                if key in lower:
                    occupation = line
                    break

        st.subheader("Detected Details")

        st.write("👤 Name:", name)
        st.write("💼 Occupation:", occupation)
        st.write("📧 Email:", email)
        st.write("📞 Phone:", phone)
        st.write("🌐 Website:", website)

        data = {
            "Name":[name],
            "Occupation":[occupation],
            "Email":[email],
            "Phone":[phone],
            "Website":[website]
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
