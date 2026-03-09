import streamlit as st
import easyocr
from PIL import Image, ImageEnhance, ImageFilter
import pandas as pd
import re
import os
import numpy as np
import cv2

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

FILE = "contacts.xlsx"
menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts", "Raw Data"])

@st.cache_resource
def load_reader():
return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

OCCUPATION_GROUPS = {
"👨‍💼 Management": ["manager","director","ceo","cto","cfo","founder","president","vp","head","executive"],
"💻 Engineering": ["engineer","developer","software","devops","architect","programmer"],
"🎨 Design": ["designer","ui","ux","graphic","creative"],
"📈 Sales & Marketing": ["sales","marketing","business development","account","growth"],
"💼 Consulting": ["consultant","advisor","analyst"],
"🔬 Research": ["scientist","researcher"],
"🏥 Healthcare": ["doctor","nurse","physician"],
"📱 Product": ["product manager","pm"],
"🎓 Education": ["teacher","professor","trainer"],
"⚖️ Legal": ["lawyer","attorney"],
"🏦 Finance": ["accountant","finance","banker"],
"📊 Operations": ["operations","hr","human resources","admin"],
"🚀 Other": []
}

def preprocess_image(image):
image = image.convert("RGB")
img = np.array(image)
height, width = img.shape[:2]

```
if width > 1200:
    scale = 1200 / width
    new_w = int(width * scale)
    new_h = int(height * scale)
    img = np.array(Image.fromarray(img).resize((new_w, new_h)))

return img
```

def enhance_for_handwriting(image):

```
img_array = np.array(image)
img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

height, width = img_cv.shape[:2]

if width < 1200:
    scale = 1200 / width
    new_width = int(width * scale)
    new_height = int(height * scale)
    img_cv = cv2.resize(img_cv, (new_width, new_height))

gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray,(3,3),0)

kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
sharpened = cv2.filter2D(blur,-1,kernel)

thresh = cv2.adaptiveThreshold(
    sharpened,255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,11,2)

return Image.fromarray(thresh)
```

def extract_text(image):

```
normal_img = preprocess_image(image)
enhanced_img = enhance_for_handwriting(image)

normal = reader.readtext(normal_img, detail=0)
enhanced = reader.readtext(np.array(enhanced_img), detail=0)

text = list(set(normal + enhanced))
text = "\n".join(text)

text = text.replace("|"," ")
text = text.replace("•"," ")

return text
```

# ---------------- STRONG NAME DETECTION ----------------

def extract_name(text):

```
lines = [l.strip() for l in text.split("\n") if l.strip()]

titles = ["mr","mrs","ms","dr","prof","eng","sir"]
ignore_words = [
    "phone","mobile","email","mail","www","http",
    "street","road","avenue","company","solutions",
    "technologies","services","ltd","limited",
    "pvt","inc","corporation"
]

candidates = []

for line in lines[:8]:

    clean_line = re.sub(r'[^A-Za-z\s.]','',line)
    words = clean_line.split()

    if len(words) < 2 or len(words) > 4:
        continue

    score = 0

    for w in words:

        wl = w.lower().replace('.','')

        if wl in titles:
            score += 2

        if w[0].isupper():
            score += 2

        if wl in ignore_words:
            score -= 3

        if len(w) > 1 and w.isupper():
            score += 1

    if score >= 3:
        candidates.append((score," ".join(words)))

if candidates:
    candidates.sort(reverse=True)
    return candidates[0][1]

return "Name not found"
```

# -------------------------------------------------------

def extract_email(text):

```
pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
matches = re.findall(pattern,text)

if matches:
    return matches[0]

return ""
```

def extract_phones(text):

```
pattern = r'\+?[\d\s\-\(\)]{8,}'
phones = re.findall(pattern,text)

cleaned = []

for p in phones:
    num = re.sub(r'[^\d+]','',p)

    if len(num) >= 10:
        cleaned.append(num)

return list(set(cleaned))
```

def extract_website(text):

```
pattern = r'(?:www\.|https?://)?[a-zA-Z0-9-]+\.(?:com|org|net|co|in|io)'
matches = re.findall(pattern,text)

if matches:
    site = matches[0]

    if not site.startswith("www"):
        site = "www." + site

    return site

return ""
```

def extract_occupation(text):

```
keywords = sum(OCCUPATION_GROUPS.values(),[])

for line in text.split("\n"):

    for key in keywords:

        if key in line.lower():
            return line

return ""
```

def categorize_occupation(occ):

```
if not occ:
    return "🚀 Other"

occ = occ.lower()

for cat,words in OCCUPATION_GROUPS.items():

    for w in words:

        if w in occ:
            return cat

return "🚀 Other"
```

def safe_load_contacts():

```
if not os.path.exists(FILE):
    return pd.DataFrame(columns=['Name','Occupation','Category','Email','Phone','Website'])

df = pd.read_excel(FILE)

if 'Category' not in df.columns:
    df['Category'] = df['Occupation'].apply(categorize_occupation)

return df
```

# ------------------ SCAN CARD ------------------

if menu == "Scan Card":

```
st.title("AI Business Card Scanner")

uploaded = st.file_uploader("Upload Business Card",type=["jpg","png","jpeg"])

if uploaded:

    image = Image.open(uploaded)

    st.image(image,use_column_width=True)

    text = extract_text(image)

    st.subheader("Detected Text")
    st.text_area("",text,height=200)

    name = extract_name(text)
    email = extract_email(text)
    phones = extract_phones(text)
    website = extract_website(text)
    occ = extract_occupation(text)
    cat = categorize_occupation(occ)

    st.success(f"Name: {name}")
    st.write(f"Occupation: {occ}")
    st.write(f"Category: {cat}")
    st.write(f"Email: {email}")
    st.write(f"Website: {website}")

    for p in phones:
        st.write(f"Phone: {p}")

    if name != "Name not found":

        df = safe_load_contacts()

        new = pd.DataFrame([{
            "Name":name,
            "Occupation":occ,
            "Category":cat,
            "Email":email,
            "Phone":",".join(phones),
            "Website":website
        }])

        df = pd.concat([df,new],ignore_index=True)
        df.to_excel(FILE,index=False)

        st.success("Contact saved")
```

# ------------------ VIEW CONTACTS ------------------

elif menu == "View Contacts":

```
st.title("Contacts")

df = safe_load_contacts()

if not df.empty:

    st.dataframe(df,use_container_width=True)

else:

    st.info("No contacts yet")
```

# ------------------ RAW DATA ------------------

elif menu == "Raw Data":

```
df = safe_load_contacts()

if not df.empty:

    st.dataframe(df)

else:

    st.warning("No data yet")
```
