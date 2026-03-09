import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import re
import os
import numpy as np

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

DATA_FILE = "contacts.xlsx"

# ---------- UI STYLE ----------
st.markdown("""
<style>

.stApp {
background: linear-gradient(120deg,#0f172a,#1e293b);
color:white;
}

.main-title{
text-align:center;
font-size:42px;
font-weight:bold;
color:#38bdf8;
}

.subtitle{
text-align:center;
color:#94a3b8;
margin-bottom:30px;
}

.contact-card{
background:#1e293b;
padding:18px;
border-radius:14px;
box-shadow:0 4px 12px rgba(0,0,0,0.35);
margin-bottom:12px;
}

.stButton>button{
background:#38bdf8;
color:black;
border-radius:10px;
font-weight:bold;
}

section[data-testid="stSidebar"]{
background:#020617;
}

</style>
""", unsafe_allow_html=True)

# ---------- HEADER ----------
st.markdown(
"<div class='main-title'>📇 AI Business Card Scanner</div>",
unsafe_allow_html=True
)

st.markdown(
"<div class='subtitle'>Scan cards → Extract contacts → Build your network</div>",
unsafe_allow_html=True
)

# ---------- MENU ----------
menu = st.sidebar.radio(
"Navigation",
["Scan Cards","Dashboard","Export","Raw Data"]
)

# ---------- LOAD OCR ----------
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

    keywords = ["inc","ltd","solutions","technologies","corp","company"]

    for line in text.split("\n"):

        for k in keywords:

            if k in line.lower():

                return line

    return ""

# ---------- LOAD CONTACTS ----------
def load_contacts():

    if os.path.exists(DATA_FILE):

        return pd.read_excel(DATA_FILE)

    return pd.DataFrame(
        columns=["Name","Company","Email","Phone","Website"]
    )

# ---------- SAVE CONTACT ----------
def save_contact(name,company,email,phones,website):

    df = load_contacts()

    new = pd.DataFrame([{
        "Name":name,
        "Company":company,
        "Email":email,
        "Phone":", ".join(phones),
        "Website":website
    }])

    df = pd.concat([df,new],ignore_index=True)

    df.to_excel(DATA_FILE,index=False)

# ---------- SCAN ----------
if menu == "Scan Cards":

    option = st.radio(
    "Input Method",
    ["Upload Image","Use Camera"]
    )

    images = []

    if option == "Upload Image":

        files = st.file_uploader(
        "Upload cards",
        type=["jpg","png","jpeg"],
        accept_multiple_files=True
        )

        if files:
            images = files

    if option == "Use Camera":

        cam = st.camera_input("Take photo")

        if cam:
            images = [cam]

    for i,file in enumerate(images):

        image = Image.open(file)

        st.image(image,use_column_width=True)

        text = extract_text(image)

        name = detect_name(text)
        email = detect_email(text)
        phones = detect_phones(text)
        website = detect_website(text)
        company = detect_company(text)

        st.markdown(
        f"""
        <div class='contact-card'>

        <h4>👤 {name}</h4>

        🏢 {company}  
        📧 {email}  
        📞 {", ".join(phones)}  
        🌐 {website}

        </div>
        """,
        unsafe_allow_html=True
        )

        save_contact(name,company,email,phones,website)

        st.download_button(
        "Download Contact",
        data=f"{name} {email}",
        file_name="contact.txt",
        key=f"download_{i}"
        )

        st.success("Contact saved!")

# ---------- DASHBOARD ----------
elif menu == "Dashboard":

    df = load_contacts()

    if not df.empty:

        col1,col2,col3 = st.columns(3)

        col1.metric("Total Contacts",len(df))
        col2.metric("Companies",df["Company"].nunique())
        col3.metric("Emails",df["Email"].count())

        search = st.text_input("Search")

        if search:

            df = df[
            df["Name"].str.contains(search,case=False,na=False) |
            df["Email"].str.contains(search,case=False,na=False)
            ]

        for _,row in df.iterrows():

            st.markdown(
            f"""
            <div class='contact-card'>

            <h4>👤 {row['Name']}</h4>

            🏢 {row['Company']}  
            📧 {row['Email']}  
            📞 {row['Phone']}  
            🌐 {row['Website']}

            </div>
            """,
            unsafe_allow_html=True
            )

        st.bar_chart(df["Company"].value_counts())

    else:

        st.warning("No contacts yet")

# ---------- EXPORT ----------
elif menu == "Export":

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

# ---------- RAW ----------
elif menu == "Raw Data":

    df = load_contacts()

    st.dataframe(df)
