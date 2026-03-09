import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import re
import os
import numpy as np
import cv2

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

FILE = "contacts.xlsx"
menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts"])

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

# -------- SIMPLE TEXT CLEANING (FIXED - minimal only) --------
def clean_ocr_text(text):
    # ONLY normalize spaces - no destructive substitutions
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# -------- TARGETED NORMALIZATION for extraction --------
def normalize_domains(text):
    # ONLY fix missing dots before common TLDs: gmailcom → gmail.com
    tlds = 'com|org|net|co|in|io|ai|uk|edu'
    text = re.sub(r'([a-z0-9]+)(?=' + tlds + r')', r'\1.\2', text, flags=re.IGNORECASE)
    # Fix spaces around @
    text = re.sub(r'\s*@\s*', '@', text)
    return text

# -------- PREPROCESS IMAGE (KEEP WORKING VERSION) --------
def preprocess_image(image):
    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    height, width = img.shape[:2]
    if width > 1200:
        scale = 1200 / width
        new_w, new_h = int(width * scale), int(height * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(blurred)
    binary = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    processed_rgb = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
    return binary, processed_rgb

# -------- OCR --------
def extract_text(image):
    binary, processed_rgb = preprocess_image(image)
    result = reader.readtext(binary, detail=0)
    text = " ".join(result)
    cleaned = clean_ocr_text(text)
    
    # Show comparison in sidebar (optional)
    st.sidebar.image(processed_rgb, caption="Processed", use_container_width=True)
    return cleaned

# -------- EMAIL (SIMPLE & ROBUST) --------
def extract_email(text):
    norm = normalize_domains(text)
    # Simple pattern that works
    pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    matches = re.findall(pattern, norm, re.IGNORECASE)
    return matches[0] if matches else ""

# -------- PHONE --------
def extract_phone(text):
    # Extract any 10+ digit sequence with common separators
    pattern = r'\+?[\d\s\-\(\)\.]{10,}'
    matches = re.findall(pattern, text)
    if matches:
        # Clean it up
        phone = re.sub(r'[^\d+]', '', matches[0])  # Keep only digits + +
        return phone
    return ""

# -------- WEBSITE --------
def extract_website(text):
    norm = normalize_domains(text)
    pattern = r'(?:www\.|https?://)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
    matches = re.findall(pattern, norm, re.IGNORECASE)
    if matches:
        site = matches[0]
        if not site.startswith(('http://', 'https://', 'www.')):
            site = 'www.' + site
        return site
    return ""

# -------- NAME --------
def extract_name(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines[:3]:
        words = line.split()
        if len(words) >= 2 and words[0][0].isupper() and words[1][0].isupper():
            return f"{words[0]} {words[1]}"
    return ""

# -------- OCCUPATION --------
def extract_occupation(text):
    keywords = ["manager","consultant","engineer","developer","designer","director","founder","ceo","cto"]
    for line in text.split('\n'):
        if any(kw in line.lower() for kw in keywords):
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
    elif option == "Use Camera":
        cam = st.camera_input("Take Photo")
        if cam:
            image = Image.open(cam)

    if image is not None:
        st.image(image, caption="Business Card", use_column_width=True)
        text = extract_text(image)
        
        st.subheader("Extracted Text")
        st.text_area("", text, height=120)

        # Extract details
        name = extract_name(text)
        email = extract_email(text)
        phone = extract_phone(text)
        website = extract_website(text)
        occupation = extract_occupation(text)

        st.subheader("Parsed Details")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**👤 Name:**", name)
            st.write("**💼 Occupation:**", occupation)
        with col2:
            st.write("**📧 Email:**", email)
            st.write("**📞 Phone:**", phone)
            st.write("**🌐 Website:**", website)

        # Save to Excel
        data = {
            "Name": [name], "Occupation": [occupation],
            "Email": [email], "Phone": [phone], "Website": [website]
        }
        df = pd.DataFrame(data)
        
        if os.path.exists(FILE):
            old_df = pd.read_excel(FILE)
            df = pd.concat([old_df, df], ignore_index=True)
        df.to_excel(FILE, index=False)
        st.success("✅ Saved to contacts.xlsx")

# -------- VIEW CONTACTS --------
elif menu == "View Contacts":
    st.title("Saved Contacts")
    if os.path.exists(FILE):
        df = pd.read_excel(FILE)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("👆 Scan a card first!")
