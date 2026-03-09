import streamlit as st
import easyocr
from PIL import Image, ImageEnhance, ImageFilter
import pandas as pd
import re
import os
import numpy as np
import cv2
import math

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

def enhance_for_handwriting(image):
    img_array = np.array(image)
    img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    height, width = img_cv.shape[:2]
    if width < 1200:
        scale = 1200 / width
        new_width = int(width * scale)
        new_height = int(height * scale)
        img_cv = cv2.resize(img_cv, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    denoised = cv2.medianBlur(denoised, 3)
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)
    thresh = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    kernel = np.ones((2,2), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
    coords = np.column_stack(np.where(cleaned > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = cleaned.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    deskewed = cv2.warpAffine(cleaned, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(deskewed)

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
    email = re.sub(r'[([^]]+)]([^)]+)', r'\u0001', email)
    email = re.sub(r'www.([a-zA-Z0-9.-]+.[a-zA-Z]{2,})', r'\u0001', email)
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

def extract_text(image):
    normal_img = preprocess_image(image)
    enhanced_img = enhance_for_handwriting(image)
    normal_result = reader.readtext(normal_img, detail=0)
    enhanced_result = reader.readtext(np.array(enhanced_img), detail=0)
    all_text = list(set(normal_result + enhanced_result))
      return "
".join(all_text)

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

def extract_phones(text):
    pattern = r'+?[ds-().]{8,}'
    all_phones = re.findall(pattern, text)
    cleaned_phones = []
    for phone in all_phones:
        clean_phone = re.sub(r'[^d+]', '', phone)
        if len(clean_phone) >= 10:
            cleaned_phones.append(clean_phone)
    return list(dict.fromkeys(cleaned_phones))

def extract_name(text):
    lines = [l.strip() for l in text.split("
") if l.strip() and len(l.strip()) > 1]
    
    # Method 1: Look for lines with 2+ capitalized words (most common name pattern)
    for line in lines[:8]:  # Check first 8 lines
        words = line.split()
        caps_words = [w for w in words if w and w[0].isupper() and len(w) > 1]
        # If line has 2-4 capitalized words and total length reasonable for name
        if 2 <= len(caps_words) <= 4 and len(line) <= 50:
            # Clean up the name
            name_candidate = " ".join(caps_words[:3])
            if not any(skip in name_candidate.lower() for skip in ['inc', 'llc', 'corp', 'ltd', 'www', 'com']):
                return name_candidate
    
    # Method 2: Single line with multiple capital letters (John Smith style)
    for line in lines[:5]:
        upper_count = sum(1 for c in line if c.isupper())
        total_letters = sum(1 for c in line if c.isalpha())
        if total_letters > 0 and upper_count / total_letters >= 0.25 and len(line.split()) >= 2:
            words = line.split()
            caps_words = [w for w in words if w[0].isupper()]
            if len(caps_words) >= 2:
                return " ".join(caps_words[:3])
    
    # Method 3: First line with highest capitalization ratio
    best_line = None
    best_ratio = 0
    
    for line in lines[:6]:
        upper_count = sum(1 for c in line if c.isupper())
        total_letters = sum(1 for c in line if c.isalpha())
        if total_letters > 5:  # Line must be substantial enough
            ratio = upper_count / total_letters
            if ratio > best_ratio and ratio > 0.2:
                best_ratio = ratio
                best_line = line
                if len(line.split()) >= 2:
                    break
    
    if best_line:
        words = best_line.split()
        caps_words = [w for w in words if w[0].isupper()]
        if len(caps_words) >= 2:
            return " ".join(caps_words[:3])
    
    # Method 4: Longest line in top 3 lines (names are often prominent)
    top_lines = lines[:3]
    if top_lines:
        longest_line = max(top_lines, key=len)
        words = longest_line.split()
        caps_words = [w for w in words if w[0].isupper()]
        if len(caps_words) >= 2:
            return " ".join(caps_words[:3])
    
    return "Name not found"

def extract_email(text):
    text = re.sub(r'[([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,})]([^)]*)', r'\u0001', text)
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        return clean_email(matches[0])
    return ""

def extract_website(text):
    text = re.sub(r'(www)([a-zA-Z0-9]+)s+([a-zA-Z]{2,})', r'\u0001.\u0002.\u0003', text, flags=re.IGNORECASE)
    text = re.sub(r'(www)([a-zA-Z0-9]+)(com|org|net|co|in|io|ai)', r'\u0001.\u0002.\u0003', text, flags=re.IGNORECASE)
    patterns = [
        r'(?:www.|https?://)?([a-zA-Z0-9-]+.(?:com|org|net|co|in|io|ai|edu|gov))',
        r'www.([a-zA-Z0-9-]+.[a-zA-Z]{2,})',
        r'([a-zA-Z0-9-]+.(?:com|org|net|co|in|io|ai))'
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
    for line in text.split("
"):
        for key in keywords:
            if key in line.lower():
                return line.strip()
    return ""

# -------- SCAN CARD --------
if menu == "Scan Card":
    st.title("✨ AI Business Card Scanner - Handwriting Optimized")
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
        col1, col2 = st.columns(2)
        with col1:
            st.image(image, caption="📸 Original", use_column_width=True)
        with col2:
            enhanced = enhance_for_handwriting(image)
            st.image(enhanced, caption="🧠 Enhanced", use_column_width=True)
        
        text = extract_text(image)
        st.subheader("📄 Detected Text")
        st.text_area("", text, height=200)

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
            
            # 🔥 NEW BEAUTIFUL WEBSITE DISPLAY
            if website:
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 15px 25px; border-radius: 20px; margin: 10px 0; 
                            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4); 
                            border: 1px solid rgba(255,255,255,0.2);'>
                    <a href='https://{website}' target='_blank' 
                       style='color: white; text-decoration: none; font-weight: 700; 
                              font-size: 16px; display: flex; align-items: center;'>
                        🌐 <strong style='margin-left: 8px;'>{website}</strong> 
                        <span style='margin-left: auto; font-size: 20px;'>🔗</span>
                    </a>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                            padding: 15px 25px; border-radius: 20px; margin: 10px 0; 
                            box-shadow: 0 10px 30px rgba(245, 87, 108, 0.3); 
                            border: 1px solid rgba(255,255,255,0.2); color: white; text-align: center;'>
                    🌐 No website detected
                </div>
                """, unsafe_allow_html=True)

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
            mask = (df_unique['Name'].str.contains(search_term, case=False, na=False) | 
                    df_unique['Email'].str.contains(search_term, case=False, na=False))
            filtered_df = filtered_df[mask]
        if selected_category != "All":
            filtered_df = filtered_df[filtered_df['Category'] == selected_category]
        
        col_stats1, col_stats2 = st.columns(2)
        with col_stats1:
            st.metric("📊 Total Contacts", len(df_unique))
        with col_stats2:
            st.metric("🔍 Filtered Results", len(filtered_df))
        
        if not filtered_df.empty:
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

