import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import re
import os
import numpy as np
import cv2
import math

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

FILE = "contacts.xlsx"

menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts"])

# -------- LOAD OCR MODEL --------
@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

# -------- CLEAN OCR TEXT (ENHANCED with confusion fixes) --------
def clean_ocr_text(text):
    # Common OCR confusions for business cards [web:3][web:19]
    substitutions = {
        # Letters/Numbers
        r'I': '1',  # I → 1
        r'l': '1',  # l → 1
        r'O': '0',  # O → 0
        r'o': '0',  # o → 0
        r'S': '5',  # S → 5
        r's': '5',
        r'Z': '2',  # Z → 2
        r'z': '2',
        r'B': '8',  # B → 8
        r'8': 'B',  # Sometimes reverse
        # Phone/Email specific
        r'\s': '',   # Remove spaces in numbers/emails temporarily for matching
        # Dots/spaces in domains
    }
    
    # Normalize spaces first
    text = re.sub(r'\s+', ' ', text)
    
    # Apply substitutions selectively (avoid over-substitution)
    for wrong, right in substitutions.items():
        text = re.sub(wrong, right, text, flags=re.IGNORECASE)
    
    return text.strip()

# More targeted post-processing for domains/emails
def normalize_for_extraction(text):
    norm = text
    # Fix common domain issues: gmailcom → gmail.com, hotmailco → hotmail.co
    norm = re.sub(r'([a-z]+)(com|org|net|co|in|io|ai|uk|edu)', r'\1.\2', norm, flags=re.IGNORECASE)
    # Space around @: john @ doe → john@doe
    norm = re.sub(r'(\w)\s*@\s*(\w)', r'\1@\2', norm)
    # Phone: remove non-digits temporarily if needed
    return norm

# -------- PREPROCESS IMAGE --------
def preprocess_image(image):
    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    height, width = img.shape[:2]
    if width > 1200:
        scale = 1200 / width
        new_w = int(width * scale)
        new_h = int(height * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(blurred)
    binary = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    # Deskew
    coords = np.column_stack(np.where(binary > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) > 0.5:
        (h, w) = binary.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        binary = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    processed_rgb = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
    st.sidebar.image([np.array(image), processed_rgb], caption=["Original", "Processed"], use_container_width=True)
    
    return binary

# -------- OCR --------
def extract_text(image):
    img = preprocess_image(image)
    result = reader.readtext(img, detail=0)
    raw_text = " ".join(result)
    cleaned = clean_ocr_text(raw_text)
    st.sidebar.subheader("Raw vs Cleaned Text")
    st.sidebar.text_area("Raw:", raw_text, height=100)
    st.sidebar.text_area("Cleaned:", cleaned, height=100)
    return cleaned

# -------- EMAIL (USE NORMALIZED) --------
def extract_email(text):
    norm_text = normalize_for_extraction(text)
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+[a-zA-Z0-9]+(?:\.[a-zA-Z]{2,})?'
    matches = re.findall(pattern, norm_text, re.IGNORECASE)
    return matches[0] if matches else ""

# -------- PHONE (IMPROVED with confusion handling) --------
def extract_phone(text):
    # First clean numbers specifically
    num_text = re.sub(r'[^\d+()-]', '', text)  # Keep only digits, +, -, ()
    pattern = r'\+?[\d\s\-\(\)]{10,}'
    matches = re.findall(pattern, num_text)
    return matches[0].strip() if matches else ""

# -------- WEBSITE --------
def extract_website(text):
    norm_text = normalize_for_extraction(text)
    pattern = r'(?:www\.|https?://)?([a-zA-Z0-9-]+\.(?:com|org|net|co|in|io|ai|uk|edu)(?:\.[a-zA-Z]{2,})?)'
    matches = re.findall(pattern, norm_text, re.IGNORECASE)
    if matches:
        site = matches[0]
        if not site.startswith(('http://', 'https://', 'www.')):
            site = 'www.' + site
        return site
    return ""

# -------- NAME (IMPROVED: avoid number confusions) --------
def extract_name(text):
    lines = [l.strip() for l in re.split(r'\n|;', text) if l.strip()]  # Split on ; too
    for line in lines[:3]:
        words = line.split()
        if len(words) >= 2:
            # Check first two words start with uppercase letters (not digits)
            if (words[0][0].isupper() and words[0][0].isalpha() and
                words[1][0].isupper() and words[1][0].isalpha()):
                return words[0] + " " + words[1]
    return ""

# -------- OCCUPATION --------
def extract_occupation(text):
    keywords = [
        "manager","consultant","engineer","developer",
        "designer","director","founder","marketing",
        "sales","ceo","analyst","manager","cto"
    ]
    lines = re.split(r'\n|;', text)
    for line in lines:
        line_lower = line.lower()
        for key in keywords:
            if key in line_lower:
                return line.strip()
    return ""

# Rest of the code remains the same...
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
        st.image(image, caption="Business Card (Original)", use_column_width=True)
        
        text = extract_text(image)

        st.subheader("Detected Text")
        st.text_area("Extracted:", text, height=150)

        name = extract_name(text)
        email = extract_email(text)
        phone = extract_phone(text)
        website = extract_website(text)
        occupation = extract_occupation(text)

        st.subheader("Detected Details")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👤 Name", name)
            st.metric("💼 Occupation", occupation)
        with col2:
            st.metric("📧 Email", email)
            st.metric("📞 Phone", phone)
            st.metric("🌐 Website", website)

        data = {
            "Name": [name],
            "Occupation": [occupation],
            "Email": [email],
            "Phone": [phone],
            "Website": [website]
        }
        df = pd.DataFrame(data)

        if os.path.exists(FILE):
            old = pd.read_excel(FILE)
            new = pd.concat([old, df], ignore_index=True)
            new.to_excel(FILE, index=False)
        else:
            df.to_excel(FILE, index=False)

        st.success("Details saved to Excel!")

if menu == "View Contacts":
    st.title("Saved Contacts")
    if os.path.exists(FILE):
        data = pd.read_excel(FILE)
        st.dataframe(data)
    else:
        st.warning("No contacts saved yet")
