import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import re
import os
import numpy as np

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

FILE = "contacts.xlsx"
menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts"])

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

def preprocess_image(image):
    image = image.convert("RGB")
    img = np.array(image)
    height, width = img.shape[:2]
    if width > 1200:
        scale = 1200 / width
        new_w = int(width * scale)
        new_h = int(height * scale)
        img = np.array(Image.fromarray(img).resize((new_w, new_h)))
    return img

def extract_text(image):
    img = preprocess_image(image)
    result = reader.readtext(img, detail=0)
    return "\n".join(result)

# -------- IMPROVED NAME DETECTION --------
def extract_name(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    # Method 1: First line with 2+ capitalized words (most common)
    for line in lines[:5]:  # Check more lines
        words = line.split()
        caps_words = [w for w in words if w and w[0].isupper()]
        if len(caps_words) >= 2:
            return " ".join(caps_words[:2])
    
    # Method 2: Any line with 2+ words where first letters are uppercase
    for line in lines:
        words = line.split()
        if len(words) >= 2 and words[0][0].isupper() and words[1][0].isupper():
            return f"{words[0]} {words[1]}"
    
    # Method 3: First non-empty line with multiple words (fallback)
    for line in lines:
        words = line.split()
        if len(words) >= 2:
            return " ".join(words[:2])
    
    return "Name not found"

# Keep your working functions
def fix_domains(text):
    patterns = [
        (r'([a-z]+)com', r'\1.com'),
        (r'([a-z]+)org', r'\1.org'),
        (r'([a-z]+)net', r'\1.net'),
        (r'([a-z]+)co(?=[^a-z])', r'\1.co'),
        (r'([a-z]+)in(?=[^a-z])', r'\1.in'),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def extract_email(text):
    text = fix_domains(text)
    match = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text)
    return match[0] if match else ""

def extract_phone(text):
    match = re.findall(r'\+?[\d\s\-]{8,}', text)
    return match[0] if match else ""

def extract_website(text):
    text = fix_domains(text)
    match = re.findall(r'(?:www\.)?([A-Za-z0-9-]+\.(?:com|org|net|co|in|io|ai))', text)
    if match:
        site = match[0]
        if not site.startswith("www"):
            site = "www." + site
        return site
    return ""

def extract_occupation(text):
    keywords = ["manager","consultant","engineer","developer","designer","director","founder","marketing","sales","ceo","analyst"]
    for line in text.split("\n"):
        for key in keywords:
            if key in line.lower():
                return line.strip()
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
        st.text_area("", text, height=150)

        name = extract_name(text)
        email = extract_email(text)
        phone = extract_phone(text)
        website = extract_website(text)
        occupation = extract_occupation(text)

        st.subheader("Detected Details")
        col1, col2 = st.columns(2)
        with col1:
            st.success(f"👤 Name: **{name}**")
            st.write(f"💼 Occupation: {occupation}")
        with col2:
            st.write(f"📧 Email: {email}")
            st.write(f"📞 Phone: {phone}")
            st.write(f"🌐 Website: {website}")

        data = {"Name":[name], "Occupation":[occupation], "Email":[email], "Phone":[phone], "Website":[website]}
        df = pd.DataFrame(data)
        if os.path.exists(FILE):
            old = pd.read_excel(FILE)
            new = pd.concat([old, df], ignore_index=True)
            new.to_excel(FILE, index=False)
        else:
            df.to_excel(FILE, index=False)
        st.success("✅ Saved to Excel!")

if menu == "View Contacts":
    st.title("Saved Contacts")
    if os.path.exists(FILE):
        data = pd.read_excel(FILE)
        st.dataframe(data)
    else:
        st.warning("No contacts saved yet")
