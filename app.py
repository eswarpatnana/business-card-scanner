import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import numpy as np
import re
import os
import cv2

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

EXCEL_FILE = "scanned_cards.xlsx"

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
        gray = cv2.GaussianBlur(gray,(5,5),0)

        thresh = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )

        result = reader.readtext(thresh, detail=0)

        text = " ".join(result)

        # -------- OCR FIXES (VERY IMPORTANT) --------

        text = text.replace(" com", ".com")
        text = text.replace(" .com", ".com")

        # Fix common email mistakes
        text = text.replace("emailcom", "email.com")

        # Fix common website mistakes
        text = text.replace("designscom", "designs.com")
        text = text.replace("wmichael", "www.michael")

        # Fix uppercase issues
        text = text.replace("WWW", "www")

        # Remove OCR punctuation issues
        text = text.replace(";", ".")

        st.subheader("Detected Text")
        st.write(text)

        # -------- EMAIL DETECTION --------

        email = ""
        email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

        email_match = re.search(email_pattern, text)

        if email_match:
            email = email_match.group()

        # -------- PHONE DETECTION --------

        phone = ""
        phone_pattern = r"\+?\d[\d\-\.\s]{7,}\d"

        phone_match = re.search(phone_pattern, text)

        if phone_match:
            phone = phone_match.group()

        # -------- WEBSITE DETECTION --------

        website = ""
        website_pattern = r"(www\.[A-Za-z0-9.-]+\.[A-Za-z]{2,}|[A-Za-z0-9.-]+\.com)"

        website_match = re.search(website_pattern, text)

        if website_match:
            website = website_match.group()

        # -------- NAME DETECTION --------

        name = ""
        words = text.split()

        for i in range(len(words)-1):
            if words[i].isalpha() and words[i+1].isalpha():
                if words[i][0].isupper() and words[i+1][0].isupper():
                    name = words[i] + " " + words[i+1]
                    break

        # -------- OCCUPATION DETECTION --------

        occupation = ""

        keywords = [
            "manager","consultant","engineer","developer",
            "designer","director","founder","marketing",
            "sales","graphic","ceo","analyst"
        ]

        for line in result:
            for k in keywords:
                if k in line.lower():
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

        if os.path.exists(EXCEL_FILE):

            old = pd.read_excel(EXCEL_FILE)

            new = pd.concat([old, df], ignore_index=True)

            new.to_excel(EXCEL_FILE, index=False)

        else:

            df.to_excel(EXCEL_FILE, index=False)

        st.success("Details saved to Excel!")

# ---------------- VIEW CONTACTS ----------------

if menu == "View Contacts":

    st.title("📂 Saved Contacts")

    if os.path.exists(EXCEL_FILE):

        data = pd.read_excel(EXCEL_FILE)

        st.dataframe(data)

    else:

        st.warning("No contacts saved yet.")
