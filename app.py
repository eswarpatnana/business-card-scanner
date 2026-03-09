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
    "👨‍💼 Management": ["manager", "director", "ceo", "cto", "cfo", "founder", "president", "vp", "head", "executive", "principal"],
    "💻 Engineering": ["engineer", "developer", "software", "devops", "architect", "programmer", "backend", "frontend", "fullstack", "data engineer"],
    "🎨 Design": ["designer", "ui", "ux", "graphic", "creative", "product designer", "visual"],
    "📈 Sales & Marketing": ["sales", "marketing", "business development", "account", "digital marketing", "growth"],
    "💼 Consulting": ["consultant", "advisor", "analyst", "strategy", "management consultant"],
    "🔬 Research": ["scientist", "researcher"],
    "🏥 Healthcare": ["doctor", "nurse", "physician", "dentist", "surgeon"],
    "📱 Product": ["product manager", "pm", "product owner"],
    "🎓 Education": ["teacher", "professor", "trainer", "coach"],
    "⚖️ Legal": ["lawyer", "attorney", "legal"],
    "🏦 Finance": ["accountant", "finance", "banker", "investor"],
    "📊 Operations": ["operations", "hr", "human resources", "admin"],
    "🚀 Other": []
}

def categorize_occupation(occupation):
    if not occupation or pd.isna(occupation):
        return "🚀 Other"
    occ_lower = str(occupation).lower()
    for category, keywords in OCCUPATION_GROUPS.items():
        for keyword in keywords:
            if keyword in occ_lower:
                return category
    return "🚀 Other"

def clean_email(email):
    if not email:
        return ""
    # Remove markdown links and www from domain
    email = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', email)
    email = re.sub(r'www\.([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'\1', email)
    email = re.sub(r'<[^>]+>', '', email)
    return email.strip()

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
        if 'Email' in df.columns:
            df['Email'] = df['Email'].astype(str).apply(clean_email)
        df = df.dropna(subset=['Name'])
        return df
    except:
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
    # 🎯 MINIMAL domain fixes only - won't break emails
    patterns = [
        (r'([a-z]+)(com|org|net|co|in|io|ai|uk|edu)(?=\s|$)', r'\1.\2', re.IGNORECASE),
    ]
    for pattern, repl, flags in patterns:
        text = re.sub(pattern, repl, text, flags=flags)
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
    # 🎯 STRAIGHTFORWARD EMAIL - NO WEBSITE INTERFERENCE
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        return clean_email(matches[0])
    return ""

 def extract_website(text):
    # KEEP WORKING WEBSITE LOGIC
    text = re.sub(r'(www)([a-zA-Z0-9]+)\s+([a-zA-Z]{2,})', r'\1.\2.\3', text, flags=re.IGNORECASE)
    text = re.sub(r'(www)([a-zA-Z0-9]+)(com|org|net|co|in|io|ai)', r'\1.\2.\3', text, flags=re.IGNORECASE)
    patterns = [
        r'(?:www\.|https?://)?([a-zA-Z0-9-]+\.(?:com|org|net|co|in|io|ai|edu|gov))',
        r'www\.([a-zA-Z0-9-]+\.[a-zA-Z]{2,})',
        r'([a-zA-Z0-9-]+\.(?:com|org|net|co|in|io|ai))'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            site = matches[0]
            if not site.startswith(('http://', 'https://', 'www.')):
                site = 'www.' + site
            return site
    return ""

def extract_occupation(text):
    keywords = sum(OCCUPATION_GROUPS.values(), [])
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
            st.markdown(f"📧 **{email}**")
            st.markdown(f"🌐 **{website}**")

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

# [Keep View Contacts and Raw Data sections exactly the same as previous version]
elif menu == "View Contacts":
    st.title("🎯 Contacts Dashboard")
    df = safe_load_contacts()
    
    if not df.empty:
        df_unique = df.drop_duplicates(subset=['Name', 'Email'], keep='first')
        
        st.sidebar.subheader("🔍 Search")
        search_term = st.sidebar.text_input("Search names/emails:")
        
        st.sidebar.subheader("🏷️ Category Filter")
        categories = sorted(df_unique['Category'].unique())
        selected_category = st.sidebar.selectbox("Category:", ["All"] + list(categories))
        
        filtered_df = df_unique
        
        if search_term:
            mask = (
                df_unique['Name'].str.contains(search_term, case=False, na=False) |
                df_unique['Email'].str.contains(search_term, case=False, na=False)
            )
            filtered_df = filtered_df[mask]
        
        if selected_category != "All":
            filtered_df = filtered_df[filtered_df['Category'] == selected_category]
        
        col_stats1, col_stats2 = st.columns(2)
        with col_stats1:
            st.metric("📊 Total Contacts", len(df_unique))
        with col_stats2:
            st.metric("🔍 Filtered Results", len(filtered_df))
        
        if not filtered_df.empty:
            cat_counts = filtered_df['Category'].value_counts()
            st.subheader("📈 Contacts by Category")
            
            col1, col2 = st.columns(2)
            with col1:
                for cat, count in cat_counts.head(6).items():
                    st.markdown(f"**{cat}**: {count}")
            with col2:
                remaining = len(filtered_df) - cat_counts.head(6).sum()
                if remaining > 0:
                    st.markdown(f"**Others**: {remaining}")
            
            for _, row in filtered_df.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**👤 {row['Name']}**")
                    st.caption(f"💼 {row['Occupation']} | 🏷️ {row['Category']}")
                    st.caption(f"📧 {row['Email']}")
                with col2:
                    phones_count = len(str(row['Phone']).split(', '))
                    st.caption(f"📞 **{phones_count}** phones")
                st.markdown("─" * 50)
        else:
            st.info("🔍 No matches found")
    else:
        st.warning("👆 Scan some cards first!")

elif menu == "Raw Data":
    st.title("📋 Raw Data")
    df = safe_load_contacts()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No data yet")

