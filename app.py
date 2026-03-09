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

def extract_phones(text):
    pattern = r'\+?[\d\s\-\(\)\.]{8,}'
    all_phones = re.findall(pattern, text)
    cleaned_phones = []
    
    for phone in all_phones:
        clean_phone = re.sub(r'[^\d+]', '', phone)
        if len(clean_phone) >= 10:
            cleaned_phones.append(clean_phone)
    
    return list(dict.fromkeys(cleaned_phones))  # Remove duplicates

def extract_name(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    for line in lines[:5]:
        words = line.split()
        caps_words = [w for w in words if w and w[0].isupper()]
        if len(caps_words) >= 2:
            return " ".join(caps_words[:2])
    
    for line in lines:
        words = line.split()
        if len(words) >= 2 and words[0][0].isupper() and words[1][0].isupper():
            return f"{words[0]} {words[1]}"
    
    for line in lines:
        words = line.split()
        if len(words) >= 2:
            return " ".join(words[:2])
    
    return "Name not found"

def extract_email(text):
    text = fix_domains(text)
    matches = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text)
    return matches[0] if matches else ""

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

        # Extract details ONCE
        name = extract_name(text)
        email = extract_email(text)
        phones = extract_phones(text)
        website = extract_website(text)
        occupation = extract_occupation(text)

        st.subheader("Detected Details")
        col1, col2 = st.columns(2)
        with col1:
            st.success(f"👤 Name: **{name}**")
            st.write(f"💼 Occupation: {occupation}")
        with col2:
            st.write(f"📧 Email: {email}")
            st.write(f"🌐 Website: {website}")
        
        # Show phones
        st.subheader("📞 Phone Numbers")
        for i, phone in enumerate(phones, 1):
            st.success(f"Phone {i}: `{phone}`")

        # 🎯 FIXED: Create ONE row with ALL phones comma-separated
        if name != "Name not found" and phones:
            phone_column = ", ".join(phones)  # Phone 1, Phone 2 in ONE cell
            
            data = {
                "Name": [name],
                "Occupation": [occupation],
                "Email": [email],
                "Phone": [phone_column],  # ALL phones together
                "Website": [website]
            }
            df_new = pd.DataFrame(data)
            
            # Check existing file and avoid duplicates
            if os.path.exists(FILE):
                df_old = pd.read_excel(FILE)
                # Check if this exact contact (name+email) already exists
                mask = (df_old['Name'].str.lower() == name.lower()) & (df_old['Email'].str.lower() == email.lower())
                if not mask.any():
                    df_final = pd.concat([df_old, df_new], ignore_index=True)
                    df_final.to_excel(FILE, index=False)
                    st.success(f"✅ Saved **{name}** with {len(phones)} phones! (1 row)")
                else:
                    st.warning(f"⚠️ **{name}** already exists in contacts!")
            else:
                df_new.to_excel(FILE, index=False)
                st.success(f"✅ First contact saved: **{name}** with {len(phones)} phones!")
        else:
            st.error("❌ Missing name or phones - cannot save")

if menu == "View Contacts":
    st.title("Saved Contacts")
    if os.path.exists(FILE):
        data = pd.read_excel(FILE)
        st.dataframe(data, use_container_width=True)
    else:
        st.warning("No contacts saved yet")
