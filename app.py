import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import re
import os
import numpy as np

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

FILE = "contacts.xlsx"

menu = st.sidebar.selectbox("Menu", ["Scan Card","View Contacts","Raw Data"])

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()


# ---------- IMAGE PREPROCESS ----------
def preprocess_image(image):

    image = image.convert("RGB")
    img = np.array(image)

    h,w = img.shape[:2]

    if w > 1200:
        scale = 1200 / w
        img = np.array(
            Image.fromarray(img).resize((int(w*scale), int(h*scale)))
        )

    return img


# ---------- OCR ----------
def extract_text(image):

    img = preprocess_image(image)

    result = reader.readtext(img, detail=0)

    return "\n".join(result)


# ---------- EMAIL ----------
def extract_email(text):

    match = re.findall(
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        text
    )

    return match[0] if match else ""


# ---------- PHONE ----------
def extract_phone(text):

    phones = re.findall(r'\+?\d[\d\s\-]{8,}', text)

    clean = []

    for p in phones:
        p = re.sub(r'[^\d+]', '', p)
        if len(p) >= 10:
            clean.append(p)

    return list(dict.fromkeys(clean))


# ---------- WEBSITE ----------
def extract_website(text):

    pattern = r'((?:www\.)?[a-zA-Z0-9-]+\.(?:com|org|net|co|in|io|ai))'

    match = re.findall(pattern, text)

    if match:

        site = match[0]

        if not site.startswith("www"):
            site = "www." + site

        return site

    return ""


# ---------- NAME ----------
def extract_name(text):

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for line in lines[:4]:

        words = line.split()

        if len(words) >= 2:

            if words[0][0].isupper() and words[1][0].isupper():

                return words[0] + " " + words[1]

    return "Name not found"


# ---------- COMPANY ----------
def extract_company(text):

    lines = text.split("\n")

    for line in lines:

        if any(word in line.lower() for word in
            ["inc","ltd","company","solutions","technologies","corp"]):

            return line

    return ""


# ---------- OCCUPATION ----------
def extract_occupation(text):

    keywords = [
        "manager","director","ceo","founder","engineer",
        "developer","designer","consultant","analyst",
        "sales","marketing","architect"
    ]

    for line in text.split("\n"):

        for k in keywords:

            if k in line.lower():

                return line

    return ""


# ---------- LOAD CONTACTS ----------
def load_contacts():

    if os.path.exists(FILE):

        return pd.read_excel(FILE)

    return pd.DataFrame(
        columns=["Name","Company","Occupation","Email","Phone","Website"]
    )


# ---------- SCAN CARD ----------
if menu == "Scan Card":

    st.title("AI Business Card Scanner")

    option = st.radio("Choose Input Method",["Upload Image","Use Camera"])

    image = None

    if option == "Upload Image":

        uploaded = st.file_uploader("Upload Card",type=["jpg","png","jpeg"])

        if uploaded:
            image = Image.open(uploaded)

    if option == "Use Camera":

        cam = st.camera_input("Take Photo")

        if cam:
            image = Image.open(cam)

    if image is not None:

        st.image(image,use_column_width=True)

        text = extract_text(image)

        st.subheader("Detected Text")

        st.text_area("",text,height=150)

        name = extract_name(text)
        email = extract_email(text)
        phones = extract_phone(text)
        website = extract_website(text)
        company = extract_company(text)
        occupation = extract_occupation(text)

        st.success(f"👤 {name}")

        st.write("🏢 Company:",company)
        st.write("💼 Occupation:",occupation)
        st.write("📧 Email:",email)
        st.write("🌐 Website:",website)

        for i,p in enumerate(phones,1):
            st.write(f"📞 Phone {i}:",p)

        if name != "Name not found":

            df = load_contacts()

            new = pd.DataFrame([{
                "Name":name,
                "Company":company,
                "Occupation":occupation,
                "Email":email,
                "Phone":", ".join(phones),
                "Website":website
            }])

            df = pd.concat([df,new],ignore_index=True)

            df.to_excel(FILE,index=False)

            st.success("Contact saved!")


# ---------- VIEW CONTACTS ----------
elif menu == "View Contacts":

    st.title("Contacts Dashboard")

    df = load_contacts()

    if not df.empty:

        st.metric("Total Contacts",len(df))

        st.dataframe(df)

        csv = df.to_csv(index=False)

        st.download_button(
            "Download Contacts CSV",
            csv,
            "contacts.csv",
            "text/csv"
        )

    else:

        st.warning("Scan cards first")


# ---------- RAW DATA ----------
elif menu == "Raw Data":

    st.title("Raw Data")

    df = load_contacts()

    st.dataframe(df)
