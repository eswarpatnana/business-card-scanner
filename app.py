import streamlit as st
from google.cloud import vision
from PIL import Image
import pandas as pd
import re
import os
import io

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

excel_file = "contacts.xlsx"

menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts"])


# -------- GOOGLE VISION OCR --------
def google_ocr(image):

    client = vision.ImageAnnotatorClient.from_service_account_file(
        "second-lodge-489610-k2-da8eba67b46c.json"
    )

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')

    content = img_byte_arr.getvalue()

    vision_image = vision.Image(content=content)

    response = client.text_detection(image=vision_image)

    texts = response.text_annotations

    if texts:
        return texts[0].description
    else:
        return ""


# -------- EMAIL --------
def extract_email(text):

    pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'

    match = re.search(pattern, text)

    if match:
        return match.group()

    return ""


# -------- PHONE --------
def extract_phone(text):

    pattern = r'\+?\d[\d\s\-]{8,}\d'

    match = re.search(pattern, text)

    if match:
        return match.group()

    return ""


# -------- WEBSITE --------
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


# -------- NAME --------
def extract_name(text):

    words = text.split()

    for i in range(len(words)-1):

        if words[i].istitle() and words[i+1].istitle():

            return words[i] + " " + words[i+1]

    return ""


# -------- OCCUPATION --------
def extract_occupation(text):

    jobs = [
        "manager","consultant","engineer","developer",
        "designer","director","founder","marketing",
        "sales","ceo","analyst"
    ]

    for j in jobs:

        if j in text.lower():

            return j.title()

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

        text = google_ocr(image)

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

        if os.path.exists(excel_file):

            old = pd.read_excel(excel_file)

            new = pd.concat([old, df], ignore_index=True)

            new.to_excel(excel_file, index=False)

        else:

            df.to_excel(excel_file, index=False)

        st.success("Details saved to Excel")


# -------- VIEW CONTACTS --------
if menu == "View Contacts":

    st.title("Saved Contacts")

    if os.path.exists(excel_file):

        data = pd.read_excel(excel_file)

        st.dataframe(data)

    else:

        st.warning("No contacts saved yet")
