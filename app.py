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

# -------- CLEAN OCR TEXT --------
def clean_text(text):
    text = text.replace("..", ".")
    text = text.replace(" .", ".")
    text = text.replace("emailcom", "email.com")
    text = text.replace("emaiicom", "email.com")
    text = text.replace("WWW", "www")

    # Fix websites like wwexamplecom
    text = re.sub(r'\bww([a-zA-Z0-9]+)com', r'www.\1.com', text)

    return text


# -------- EMAIL DETECTION --------
def extract_email(text):

    email_patterns = [
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+com'
    ]

    for pattern in email_patterns:
        match = re.search(pattern, text)
        if match:
            email = match.group()
            email = email.replace("com", ".com") if "@emailcom" in email else email
            return email

    return ""


# -------- PHONE DETECTION --------
def extract_phone(text):

    match = re.search(r'\+?\d[\d\s\-]{7,}', text)

    if match:
        return match.group()

    return ""


# -------- WEBSITE DETECTION --------
def extract_website(text):

    patterns = [
        r'www\.[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        r'[A-Za-z0-9.-]+\.com',
        r'www\.[A-Za-z0-9.-]+com'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            site = match.group()
            site = site.replace("com", ".com") if not site.endswith(".com") else site
            return site

    return ""


# -------- NAME DETECTION --------
def extract_name(text):

    words = text.split()

    for i in range(len(words)-1):
        if words[i].istitle() and words[i+1].istitle():
            return words[i] + " " + words[i+1]

    return ""


# -------- OCCUPATION DETECTION --------
def extract_occupation(lines):

    keywords = [
        "manager","consultant","engineer","developer",
        "designer","director","founder","marketing",
        "sales","graphic","ceo","analyst"
    ]

    for line in lines:
        for k in keywords:
            if k in line.lower():
                return line

    return ""


# -------- SCAN CARD --------

if menu == "Scan Card":

    st.title("📇 AI Business Card Scanner")

    option = st.radio("Choose Input Method", ["Upload Image", "Use Camera"])

    image = None

    if option == "Upload Image":

        uploaded = st.file_uploader("Upload Business Card", type=["jpg","png","jpeg"])

        if uploaded:
            image = Image.open(uploaded)

    if option == "Use Camera":

        cam = st.camera_input("Take Photo")

        if cam:
            image = Image.open(cam)

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

        text = clean_text(text)

        st.subheader("Detected Text")
        st.write(text)

        email = extract_email(text)
        phone = extract_phone(text)
        website = extract_website(text)
        name = extract_name(text)
        occupation = extract_occupation(result)

        st.subheader("Detected Details")

        st.write("👤 Name:", name)
        st.write("💼 Occupation:", occupation)
        st.write("📧 Email:", email)
        st.write("📞 Phone:", phone)
        st.write("🌐 Website:", website)

        df = pd.DataFrame({
            "Name":[name],
            "Occupation":[occupation],
            "Email":[email],
            "Phone":[phone],
            "Website":[website]
        })

        if os.path.exists(EXCEL_FILE):

            old = pd.read_excel(EXCEL_FILE)

            new = pd.concat([old, df], ignore_index=True)

            new.to_excel(EXCEL_FILE, index=False)

        else:

            df.to_excel(EXCEL_FILE, index=False)

        st.success("Details saved to Excel!")


# -------- VIEW CONTACTS --------

if menu == "View Contacts":

    st.title("📂 Saved Contacts")

    if os.path.exists(EXCEL_FILE):

        data = pd.read_excel(EXCEL_FILE)

        st.dataframe(data)

    else:

        st.warning("No contacts saved yet.")
