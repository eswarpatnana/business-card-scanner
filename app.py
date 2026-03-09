import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import re
import os
import numpy as np


 

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

DATA_FILE = "contacts.xlsx"

menu = st.sidebar.selectbox(
    "Navigation",
    [
        "Scan Cards",
        "Contacts Dashboard",
        "Analytics",
        "Export Data",
        "Raw Database"
    ]
)

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
def detect_email(text):

    match = re.findall(
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        text
    )

    return match[0] if match else ""


# ---------- PHONE ----------
def detect_phones(text):

    phones = re.findall(r'\+?\d[\d\s\-]{8,}', text)

    clean = []

    for p in phones:

        p = re.sub(r'[^\d+]', '', p)

        if len(p) >= 10:
            clean.append(p)

    return list(dict.fromkeys(clean))


# ---------- WEBSITE ----------
def detect_website(text):

    pattern = r'((?:www\.)?[a-zA-Z0-9-]+\.(?:com|org|net|co|in|io|ai))'

    match = re.findall(pattern, text)

    if match:

        site = match[0]

        if not site.startswith("www"):
            site = "www." + site

        return site

    return ""


# ---------- LINKEDIN ----------
def detect_linkedin(text):

    match = re.findall(
        r'(linkedin\.com\/[A-Za-z0-9\/\-]+)',
        text,
        re.IGNORECASE
    )

    if match:
        return "https://" + match[0]

    return ""


# ---------- ADDRESS ----------
def detect_address(text):

    for line in text.split("\n"):

        if re.search(r'\d{5,6}', line):
            return line

    return ""


# ---------- NAME ----------
def detect_name(text):

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for line in lines[:4]:

        words = line.split()

        if len(words) >= 2:

            if words[0][0].isupper() and words[1][0].isupper():

                return words[0] + " " + words[1]

    return "Unknown"


# ---------- COMPANY ----------
def detect_company(text):

    keywords = [
        "inc","ltd","solutions",
        "technologies","company","corp"
    ]

    for line in text.split("\n"):

        for k in keywords:

            if k in line.lower():

                return line

    return ""


# ---------- CONTACT SUMMARY ----------
def contact_summary(name, company, email, phones, website):

    return f"""
Name: {name}
Company: {company}

Email: {email}
Phone: {", ".join(phones)}

Website: {website}
"""


# ---------- VCARD ----------
def generate_vcard(name, phone, email, company):

    return f"""
BEGIN:VCARD
VERSION:3.0
FN:{name}
ORG:{company}
TEL:{phone}
EMAIL:{email}
END:VCARD
"""


# ---------- LOAD DATABASE ----------
def load_contacts():

    if os.path.exists(DATA_FILE):

        return pd.read_excel(DATA_FILE)

    return pd.DataFrame(
        columns=[
            "Name","Company",
            "Email","Phone","Website"
        ]
    )


# ---------- DUPLICATE CHECK ----------
def is_duplicate(df,name,email):

    if df.empty:
        return False

    mask = (
        (df["Name"].str.lower()==name.lower()) &
        (df["Email"].str.lower()==email.lower())
    )

    return mask.any()


# ---------- SAVE CONTACT ----------
def save_contact(name,company,email,phones,website):

    df = load_contacts()

    if not is_duplicate(df,name,email):

        new = pd.DataFrame([{
            "Name":name,
            "Company":company,
            "Email":email,
            "Phone":", ".join(phones),
            "Website":website
        }])

        df = pd.concat([df,new],ignore_index=True)

        df.to_excel(DATA_FILE,index=False)

        return True

    return False


# ---------- SCAN CARDS ----------
if menu == "Scan Cards":

    st.title("AI Business Card Scanner")

    option = st.radio(
        "Input Method",
        ["Upload Images","Use Camera"]
    )

    images = []

    if option == "Upload Images":

        files = st.file_uploader(
            "Upload Cards",
            type=["jpg","png","jpeg"],
            accept_multiple_files=True
        )

        if files:
            images = files

    if option == "Use Camera":

        cam = st.camera_input("Take Photo")

        if cam:
            images = [cam]

    for file in images:

        image = Image.open(file)

        st.image(image,use_column_width=True)

        text = extract_text(image)

        st.text_area("Detected Text",text)

        name = detect_name(text)
        email = detect_email(text)
        phones = detect_phones(text)
        website = detect_website(text)
        company = detect_company(text)
        linkedin = detect_linkedin(text)
        address = detect_address(text)

        st.success(f"👤 {name}")

        st.write("🏢",company)
        st.write("📧",email)
        st.write("🌐",website)
        st.write("🔗",linkedin)
        st.write("📍",address)

        for p in phones:
            st.write("📞",p)

        summary = contact_summary(name,company,email,phones,website)

        st.subheader("Contact Summary")

        st.text(summary)

        vcard = generate_vcard(name,", ".join(phones),email,company)

        st.download_button(
            "Download Contact",
            vcard,
            file_name="contact.vcf"
        )

        saved = save_contact(name,company,email,phones,website)

        if saved:
            st.success("Contact saved!")
        else:
            st.warning("Duplicate contact")


# ---------- DASHBOARD ----------
elif menu == "Contacts Dashboard":

    st.title("Contacts Dashboard")

    df = load_contacts()

    if not df.empty:

        st.metric("Total Contacts",len(df))

        search = st.sidebar.text_input("Search")

        if search:

            df = df[
                df["Name"].str.contains(search,case=False,na=False) |
                df["Email"].str.contains(search,case=False,na=False)
            ]

        st.dataframe(df)

    else:

        st.warning("No contacts yet")


# ---------- ANALYTICS ----------
elif menu == "Analytics":

    st.title("Contact Analytics")

    df = load_contacts()

    if not df.empty:

        st.bar_chart(df["Company"].value_counts())

        st.line_chart(df.index)

    else:

        st.warning("No data")


# ---------- EXPORT ----------
elif menu == "Export Data":

    st.title("Export Contacts")

    df = load_contacts()

    if not df.empty:

        csv = df.to_csv(index=False)

        st.download_button(
            "Download CSV",
            csv,
            "contacts.csv"
        )

    else:

        st.warning("No contacts")


# ---------- RAW DATABASE ----------
elif menu == "Raw Database":

    st.title("Raw Data")

    df = load_contacts()

    st.dataframe(df)


