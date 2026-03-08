import streamlit as st
from google.cloud import vision
from PIL import Image
import pandas as pd
import re
import os
import io

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

EXCEL_FILE = "scanned_cards.xlsx"

menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts"])


# ---------- GOOGLE VISION OCR ----------
def google_ocr(image):

    client = vision.ImageAnnotatorClient.from_service_account_file(
        "second-lodge-489610-k2-da8eba.json"
    )

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")

    content = img_byte_arr.getvalue()

    vision_image = vision.Image(content=content)

    response = client.text_detection(image=vision_image)

    texts = response.text_annotations

    if texts:
        return texts[0].description

    return ""


# ---------- EMAIL ----------
def extract_email(text):

    patterns = [
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+com'
    ]

    for p in patterns:
        match = re.search(p, text)
        if match:
            email = match.group()
            email = email.replace("com", ".com") if "emailcom" in email else email
            return email

    return ""


# ---------- PHONE ----------
def extract_phone(text):

    match = re.search(r'\+?\d[\d\s\-]{7,}', text)

    if match:
        return match.group()

    return ""


# ---------- WEBSITE ----------
def extract_website(text):

    patterns = [
        r'www\.[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        r'[A-Za-z0-9.-]+\.com',
        r'https?://[A-Za-z0-9.-]+'
    ]

    for p in patterns:
        match = re.search(p, text)
        if match:
            site = match.group()

            if not site.startswith("www"):
                site = "www." + site

            return site

    return ""


# ---------- NAME ----------
def extract_name(text):

    words = text.split()

    for i in range(len(words)-1):
        if words[i].istitle() and words[i+1].istitle():
            return words[i] + " " + words[i+1]

    return ""


# ---------- OCCUPATION ----------
def extract_occupation(text):

    keywords = [
        "manager","consultant","engineer","developer",
        "designer","director","founder","marketing",
        "sales","graphic","ceo","analyst"
    ]

    for k in keywords:
        if k in text.lower():
            return k.title()

    return ""


# ---------- SCAN CARD ----------
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

        text = google_ocr(image)

        st.subheader("Detected Text")
        st.write(text)

        email = extract_email(text)
        phone = extract_phone(text)
        website = extract_website(text)
        name = extract_name(text)
        occupation = extract_occupation(text)

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


# ---------- VIEW CONTACTS ----------
if menu == "View Contacts":

    st.title("📂 Saved Contacts")

    if os.path.exists(EXCEL_FILE):

        data = pd.read_excel(EXCEL_FILE)

        st.dataframe(data)

    else:

        st.warning("No contacts saved yet.")
