import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import numpy as np
import re
import os
import cv2

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

FILE_NAME = "scanned_cards.xlsx"

menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts"])

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

# ---------- TEXT CLEANING ----------
def clean_text(text):
    text = text.replace("..", ".")
    text = text.replace(" .", ".")
    text = text.replace("email..com", "email.com")
    text = text.replace("emailcom", "email.com")
    text = text.replace("WWW", "www")

    # Fix websites like wmichaeldesigns.com → www.michaeldesigns.com
    text = re.sub(r'\bw([a-zA-Z0-9]+\.(com|org|net|co))', r'www.\1', text)

    return text


# ---------- EXTRACT EMAIL ----------
def extract_email(text):
    matches = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text)
    if matches:
        return matches[0]
    return ""


# ---------- EXTRACT PHONE ----------
def extract_phone(text):
    matches = re.findall(r'\+?\d[\d\s\-]{7,}', text)
    if matches:
        return matches[0]
    return ""


# ---------- EXTRACT WEBSITE ----------
def extract_website(text):
    matches = re.findall(r'(www\.[A-Za-z0-9.-]+\.[A-Za-z]{2,})', text)
    if matches:
        return matches[0]
    return ""


# ---------- SCAN CARD ----------
if menu == "Scan Card":

    st.title("📇 AI Business Card Scanner")

    option = st.radio("Choose Input Method", ["Upload Image", "Use Camera"])

    image = None

    if option == "Upload Image":
        uploaded = st.file_uploader("Upload Business Card", type=["jpg", "png", "jpeg"])
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
        gray = cv2.GaussianBlur(gray, (5,5), 0)

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

        # ---------- NAME ----------
        name = ""
        words = text.split()
        for i in range(len(words)-1):
            if words[i].istitle() and words[i+1].istitle():
                name = words[i] + " " + words[i+1]
                break

        # ---------- OCCUPATION ----------
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

        df = pd.DataFrame({
            "Name":[name],
            "Occupation":[occupation],
            "Email":[email],
            "Phone":[phone],
            "Website":[website]
        })

        if os.path.exists(FILE_NAME):
            old = pd.read_excel(FILE_NAME)
            new = pd.concat([old, df], ignore_index=True)
            new.to_excel(FILE_NAME, index=False)
        else:
            df.to_excel(FILE_NAME, index=False)

        st.success("Details saved to Excel!")


# ---------- VIEW CONTACTS ----------
if menu == "View Contacts":

    st.title("📂 Saved Contacts")

    if os.path.exists(FILE_NAME):
        data = pd.read_excel(FILE_NAME)
        st.dataframe(data)
    else:
        st.warning("No contacts saved yet.")
