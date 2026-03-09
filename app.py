import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import re
import os
import numpy as np
import spacy

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

FILE = "contacts.xlsx"

menu = st.sidebar.selectbox(
    "Menu",
    ["Scan Card", "View Contacts", "Raw Data"]
)

# -------- LOAD OCR --------
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

# -------- LOAD NLP --------
@st.cache_resource
def load_nlp():
    return spacy.load("en_core_web_sm")

nlp = load_nlp()

# -------- OCCUPATION GROUPS --------
OCCUPATION_GROUPS = {
    "👨‍💼 Management": ["manager","director","ceo","cto","founder","president"],
    "💻 Engineering": ["engineer","developer","software","architect"],
    "🎨 Design": ["designer","ui","ux","graphic"],
    "📈 Sales & Marketing": ["sales","marketing","growth"],
    "💼 Consulting": ["consultant","advisor","analyst"],
    "🏥 Healthcare": ["doctor","nurse","physician"],
    "📱 Product": ["product manager"],
    "🎓 Education": ["teacher","professor","trainer"],
    "⚖️ Legal": ["lawyer","attorney"],
    "🏦 Finance": ["accountant","finance","banker"],
    "📊 Operations": ["operations","hr"],
    "🚀 Other": []
}

def categorize_occupation(occupation):

    if not occupation:
        return "🚀 Other"

    occ = occupation.lower()

    for cat, keywords in OCCUPATION_GROUPS.items():
        for k in keywords:
            if k in occ:
                return cat

    return "🚀 Other"

# -------- IMAGE PREPROCESS --------
def preprocess_image(image):

    image = image.convert("RGB")
    img = np.array(image)

    h, w = img.shape[:2]

    if w > 1200:
        scale = 1200 / w
        img = np.array(
            Image.fromarray(img).resize((int(w*scale), int(h*scale)))
        )

    return img

# -------- OCR --------
def extract_text(image):

    img = preprocess_image(image)

    result = reader.readtext(img, detail=0)

    return "\n".join(result)

# -------- EMAIL --------
def extract_email(text):

    match = re.findall(
        r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        text
    )

    return match[0] if match else ""

# -------- PHONE --------
def extract_phone(text):

    phones = re.findall(r'\+?\d[\d\s\-]{8,}', text)

    clean = []

    for p in phones:
        p = re.sub(r'[^\d+]', '', p)
        if len(p) >= 10:
            clean.append(p)

    return list(dict.fromkeys(clean))

# -------- WEBSITE --------
def extract_website(text):

    pattern = r'((?:www\.)?[a-zA-Z0-9-]+\.(?:com|org|net|co|in|io|ai))'

    match = re.findall(pattern, text)

    if match:

        site = match[0]

        if not site.startswith("www"):
            site = "www." + site

        return site

    return ""

# -------- LINKEDIN --------
def extract_linkedin(text):

    match = re.findall(
        r'(linkedin\.com\/[A-Za-z0-9\/\-]+)',
        text,
        re.IGNORECASE
    )

    if match:
        return "https://" + match[0]

    return ""

# -------- ADDRESS --------
def extract_address(text):

    lines = text.split("\n")

    for line in lines:

        if re.search(r'\d{5,6}', line):
            return line

    return ""

# -------- NAME (NLP) --------
def extract_name(text):

    doc = nlp(text)

    for ent in doc.ents:

        if ent.label_ == "PERSON":

            return ent.text

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for line in lines[:3]:

        words = line.split()

        if len(words) >= 2:
            return words[0] + " " + words[1]

    return "Name not found"

# -------- COMPANY --------
def extract_company(text):

    doc = nlp(text)

    for ent in doc.ents:

        if ent.label_ == "ORG":

            return ent.text

    return ""

# -------- OCCUPATION --------
def extract_occupation(text):

    keywords = sum(OCCUPATION_GROUPS.values(), [])

    for line in text.split("\n"):
        for k in keywords:
            if k in line.lower():
                return line

    return ""

# -------- LOAD CONTACTS --------
def load_contacts():

    if os.path.exists(FILE):
        return pd.read_excel(FILE)

    return pd.DataFrame(
        columns=["Name","Company","Occupation","Category","Email","Phone","Website"]
    )

# -------- SCAN CARD --------
if menu == "Scan Card":

    st.title("AI Business Card Scanner")

    option = st.radio(
        "Choose Input Method",
        ["Upload Image","Use Camera"]
    )

    image = None

    if option == "Upload Image":

        uploaded = st.file_uploader(
            "Upload Business Card",
            type=["jpg","png","jpeg"]
        )

        if uploaded:
            image = Image.open(uploaded)

    if option == "Use Camera":

        cam = st.camera_input("Take Photo")

        if cam:
            image = Image.open(cam)

    if image is not None:

        st.image(image, use_column_width=True)

        text = extract_text(image)

        st.subheader("Detected Text")

        st.text_area("", text, height=150)

        name = extract_name(text)
        email = extract_email(text)
        phones = extract_phone(text)
        website = extract_website(text)
        linkedin = extract_linkedin(text)
        address = extract_address(text)
        company = extract_company(text)

        occupation = extract_occupation(text)

        category = categorize_occupation(occupation)

        st.success(f"👤 {name}")

        st.write("🏢 Company:", company)
        st.write("💼 Occupation:", occupation)
        st.write("🏷️ Category:", category)
        st.write("📧 Email:", email)
        st.write("🌐 Website:", website)
        st.write("🔗 LinkedIn:", linkedin)
        st.write("📍 Address:", address)

        for i, p in enumerate(phones,1):
            st.write(f"📞 Phone {i}:", p)

        if name != "Name not found":

            df = load_contacts()

            new_row = pd.DataFrame([{
                "Name":name,
                "Company":company,
                "Occupation":occupation,
                "Category":category,
                "Email":email,
                "Phone":", ".join(phones),
                "Website":website
            }])

            df = pd.concat([df,new_row],ignore_index=True)

            df.to_excel(FILE,index=False)

            st.success("Contact saved!")

# -------- VIEW CONTACTS --------
elif menu == "View Contacts":

    st.title("Contacts Dashboard")

    df = load_contacts()

    if not df.empty:

        st.metric("Total Contacts",len(df))

        cat_counts = df["Category"].value_counts()

        st.bar_chart(cat_counts)

        search = st.sidebar.text_input("Search")

        if search:
            df = df[df["Name"].str.contains(search,case=False,na=False)]

        for i,row in df.iterrows():

            st.markdown(f"### 👤 {row['Name']}")

            st.write("🏢",row["Company"])
            st.write("💼",row["Occupation"])
            st.write("📧",row["Email"])
            st.write("📞",row["Phone"])
            st.write("🌐",row["Website"])

            if st.button(f"Delete {row['Name']}"):
                df = df[df["Name"] != row["Name"]]
                df.to_excel(FILE,index=False)
                st.experimental_rerun()

        csv = df.to_csv(index=False)

        st.download_button(
            "Download Contacts CSV",
            csv,
            "contacts.csv",
            "text/csv"
        )

    else:

        st.warning("Scan cards first")

# -------- RAW DATA --------
elif menu == "Raw Data":

    st.title("Raw Data")

    df = load_contacts()

    st.dataframe(df)
