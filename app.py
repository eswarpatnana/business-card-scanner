import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import re
import os
import numpy as np

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

FILE = "contacts.xlsx"
menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts", "Raw Data"])

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

OCCUPATION_GROUPS = {
    "👨‍💼 Management": ["manager", "director", "ceo", "cto", "founder", "president", "vp", "head"],
    "💻 Engineering": ["engineer", "developer", "software", "devops", "architect", "programmer"],
    "🎨 Design": ["designer", "ui", "ux", "graphic", "creative"],
    "📈 Sales & Marketing": ["sales", "marketing", "business development", "account"],
    "💼 Consulting": ["consultant", "advisor", "analyst"],
    "🔬 Research": ["scientist", "researcher"],
    "📱 Other": []
}

def categorize_occupation(occupation):
    if not occupation or pd.isna(occupation):
        return "📱 Other"
    occ_lower = str(occupation).lower()
    for category, keywords in OCCUPATION_GROUPS.items():
        for keyword in keywords:
            if keyword in occ_lower:
                return category
    return "📱 Other"

def safe_load_contacts():
    if not os.path.exists(FILE):
        return pd.DataFrame(columns=['Name', 'Occupation', 'Category', 'Email', 'Phone', 'Website'])
    
    try:
        df = pd.read_excel(FILE)
        required_cols = ['Name', 'Occupation', 'Email', 'Phone', 'Website']
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""
        if 'Category' not in df.columns:
            df['Category'] = df['Occupation'].apply(categorize_occupation)
        df = df.dropna(subset=['Name'])
        return df
    except:
        st.error("❌ Corrupted file. Starting fresh.")
        return pd.DataFrame(columns=['Name', 'Occupation', 'Category', 'Email', 'Phone', 'Website'])

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
        (r'([a-z]+)com', r'\1.com'), (r'([a-z]+)org', r'\1.org'),
        (r'([a-z]+)net', r'\1.net'), (r'([a-z]+)co(?=[^a-z])', r'\1.co'),
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
    return list(dict.fromkeys(cleaned_phones))

def extract_name(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        words = line.split()
        caps_words = [w for w in words if w and w[0].isupper()]
        if len(caps_words) >= 2:
            return " ".join(caps_words[:2])
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

        name = extract_name(text)
        email = extract_email(text)
        phones = extract_phones(text)
        website = extract_website(text)
        raw_occupation = extract_occupation(text)
        category = categorize_occupation(raw_occupation)

        col1, col2 = st.columns(2)
        with col1:
            st.success(f"👤 **{name}**")
            st.write(f"💼 {raw_occupation}")
            st.info(f"🏷️ {category}")
        with col2:
            st.write(f"📧 {email}")
            st.write(f"🌐 {website}")

        st.subheader("📞 Phones")
        for i, phone in enumerate(phones, 1):
            st.success(f"Phone {i}: `{phone}`")

        if name != "Name not found" and phones:
            df = safe_load_contacts()
            mask = (df['Name'].str.lower() == name.lower()) & (df['Email'].str.lower() == email.lower())
            if df.empty or not mask.any():
                new_row = pd.DataFrame([{
                    'Name': name, 'Occupation': raw_occupation, 'Category': category,
                    'Email': email, 'Phone': ', '.join(phones), 'Website': website
                }])
                df_final = pd.concat([df, new_row], ignore_index=True)
                df_final.to_excel(FILE, index=False)
                st.success(f"✅ Saved **{name}** ({category})")
            else:
                st.info(f"ℹ️ **{name}** exists!")

# -------- VIEW CONTACTS --------
elif menu == "View Contacts":
    st.title("🎯 Contacts by Occupation")
    df = safe_load_contacts()
    
    if not df.empty:
        df_unique = df.drop_duplicates(subset=['Name', 'Email'], keep='first')
        
        st.sidebar.subheader("🔍 Filter")
        categories = sorted(df_unique['Category'].unique().tolist())
        selected_category = st.sidebar.selectbox("Category:", ["All"] + categories)
        
        if selected_category == "All":
            st.dataframe(df_unique, use_container_width=True)
            st.success(f"📊 {len(df_unique)} unique contacts")
        else:
            filtered = df_unique[df_unique['Category'] == selected_category]
            if not filtered.empty:
                st.success(f"👥 {len(filtered)} {selected_category} contacts")
                for _, row in filtered.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**👤 {row['Name']}** - {row['Occupation']}")
                        st.caption(f"📧 {row['Email']}")
                    with col2:
                        st.caption(f"📞 {len(str(row['Phone']).split(', '))} phones")
                    st.markdown("─" * 50)
            else:
                st.info("No contacts found")
    else:
        st.warning("👆 Scan some cards first!")

# -------- RAW DATA --------
elif menu == "Raw Data":
    st.title("📋 Raw Data")
    df = safe_load_contacts()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No data yet")
