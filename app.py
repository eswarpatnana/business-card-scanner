import streamlit as st
import pytesseract
from PIL import Image
import pandas as pd
import re
import os
import numpy as np
import cv2

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

file = "contacts.xlsx"

menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts"])

# -------- OCR FUNCTION --------
def extract_text(image):

    img = np.array(image)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    gray = cv2.adaptiveThreshold(
        gray,255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,2
    )

    text = pytesseract.image_to_string(gray)

    return text


# -------- EMAIL --------
def extract_email(text):

    email = re.findall(r'\S+@\S+', text)

    return email[0] if email else ""


# -------- PHONE --------
def extract_phone(text):

    phone = re.findall(r'\+?\d[\d\s\-]{8,}', text)

    return phone[0] if phone else ""


# -------- WEBSITE --------
def extract_website(text):

    website = re.findall(r'(www\.\S+|https?://\S+|\S+\.com)', text)

    return website[0] if website else ""


# -------- NAME --------
def extract_name(text):

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    return lines[0] if len(lines) > 0 else ""


# -------- OCCUPATION --------
def extract_occupation(text):

    keywords = [
        "manager","consultant","engineer","developer",
        "designer","director","founder","marketing",
        "sales","ceo","analyst"
    ]

    for line in text.split("\n"):

        for key in keywords:

            if key in line.lower():

                return line

    return ""


# -------- SCAN CARD --------
if menu == "Scan Card":

    st.title("AI Business Card Scanner")

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

        text = extract_text(image)

        st.subheader("Detected Text")

        st.write(text)

        name = extract_name(text)
        email = extract_email(text)
        phone = extract_phone(text)
        website = extract_website(text)
        occupation = extract_occupation(text)

        st.subheader("Detected Details")

        st.write("Name:", name)
        st.write("Occupation:", occupation)
        st.write("Email:", email)
        st.write("Phone:", phone)
        st.write("Website:", website)

        data = {
            "Name":[name],
            "Occupation":[occupation],
            "Email":[email],
            "Phone":[phone],
            "Website":[website]
        }

        df = pd.DataFrame(data)

        if os.path.exists(file):

            old = pd.read_excel(file)

            new = pd.concat([old, df], ignore_index=True)

            new.to_excel(file, index=False)

        else:

            df.to_excel(file, index=False)

        st.success("Details saved to Excel!")


# -------- VIEW CONTACTS --------
if menu == "View Contacts":

    st.title("Saved Contacts")

    if os.path.exists(file):

        data = pd.read_excel(file)

        st.dataframe(data)

    else:

        st.warning("No contacts saved yet")
