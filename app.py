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

menu = st.sidebar.selectbox("Menu", ["Scan Card", "View Contacts", "Raw Data"])

# ---------------- OCR READER ----------------

@st.cache_resource
def load_reader():
reader = easyocr.Reader(['en'], gpu=False)
return reader

reader = load_reader()

# ---------------- OCCUPATION GROUPS ----------------

OCCUPATION_GROUPS = {
"👨‍💼 Management": ["manager","director","ceo","founder","president"],
"💻 Engineering": ["engineer","developer","software","programmer"],
"🎨 Design": ["designer","ui","ux","graphic"],
"📈 Sales & Marketing": ["sales","marketing","business development"],
"💼 Consulting": ["consultant","advisor","analyst"],
"🔬 Research": ["scientist","researcher"],
"🏥 Healthcare": ["doctor","nurse","physician"],
"🎓 Education": ["teacher","professor","trainer"],
"⚖️ Legal": ["lawyer","attorney"],
"🏦 Finance": ["accountant","finance","banker"],
"📊 Operations": ["operations","hr","admin"],
"🚀 Other": []
}

# ---------------- IMAGE PREPROCESS ----------------

def preprocess_image(image):

```
image = image.convert("RGB")
img = np.array(image)

height, width = img.shape[:2]

if width > 1200:
    scale = 1200 / width
    new_w = int(width * scale)
    new_h = int(height * scale)
    img = cv2.resize(img,(new_w,new_h))

return img
```

def enhance_for_handwriting(image):

```
img = np.array(image)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

blur = cv2.GaussianBlur(gray,(3,3),0)

kernel = np.array([
    [-1,-1,-1],
    [-1,9,-1],
    [-1,-1,-1]
])

sharp = cv2.filter2D(blur,-1,kernel)

thresh = cv2.adaptiveThreshold(
    sharp,255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,11,2
)

return thresh
```

# ---------------- OCR TEXT EXTRACTION ----------------

def extract_text(image):

```
normal = preprocess_image(image)
enhanced = enhance_for_handwriting(image)

text1 = reader.readtext(normal, detail=0)
text2 = reader.readtext(enhanced, detail=0)

all_text = list(set(text1 + text2))

text = "\n".join(all_text)

text = text.replace("|"," ")
text = text.replace("•"," ")

return text
```

# ---------------- NAME DETECTION ----------------

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

    clean = re.sub(r'[^A-Za-z\s.]','',line)
    words = clean.split()

    if len(words) < 2 or len(words) > 4:
        continue

    score = 0

    for w in words:

        wl = w.lower().replace(".","")

        if wl in titles:
            score += 2

        if w[0].isupper():
            score += 2

        if wl in ignore_words:
            score -= 3

        if w.isupper():
            score += 1

    if score >= 3:
        candidates.append((score," ".join(words)))

if candidates:
    candidates.sort(reverse=True)
    return candidates[0][1]

return "Name not found"
```

# ---------------- EMAIL ----------------

def extract_email(text):

```
pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
matches = re.findall(pattern,text)

if matches:
    return matches[0]

return ""
```

# ---------------- PHONE ----------------

def extract_phones(text):

```
pattern = r'\+?[\d\s\-\(\)]{8,}'
matches = re.findall(pattern,text)

phones = []

for p in matches:

    num = re.sub(r'[^\d+]','',p)

    if len(num) >= 10:
        phones.append(num)

return list(set(phones))
```

# ---------------- WEBSITE ----------------

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

# ---------------- OCCUPATION ----------------

def extract_occupation(text):

```
keywords = sum(OCCUPATION_GROUPS.values(),[])

for line in text.split("\n"):

    for k in keywords:

        if k in line.lower():
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

# ---------------- LOAD CONTACTS ----------------

def safe_load_contacts():

```
if not os.path.exists(FILE):
    return pd.DataFrame(columns=["Name","Occupation","Category","Email","Phone","Website"])

df = pd.read_excel(FILE)

if "Category" not in df.columns:
    df["Category"] = df["Occupation"].apply(categorize_occupation)

return df
```

# ---------------- SCAN CARD ----------------

if menu == "Scan Card":

```
st.title("AI Business Card Scanner")

uploaded = st.file_uploader("Upload Card",type=["jpg","png","jpeg"])

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
    occupation = extract_occupation(text)
    category = categorize_occupation(occupation)

    st.success(f"Name: {name}")
    st.write(f"Occupation: {occupation}")
    st.write(f"Category: {category}")
    st.write(f"Email: {email}")
    st.write(f"Website: {website}")

    for p in phones:
        st.write(f"Phone: {p}")

    if name != "Name not found":

        df = safe_load_contacts()

        new_row = pd.DataFrame([{
            "Name":name,
            "Occupation":occupation,
            "Category":category,
            "Email":email,
            "Phone":",".join(phones),
            "Website":website
        }])

        df = pd.concat([df,new_row],ignore_index=True)

        df.to_excel(FILE,index=False)

        st.success("Contact Saved")
```

# ---------------- VIEW CONTACTS ----------------

elif menu == "View Contacts":

```
st.title("Contacts")

df = safe_load_contacts()

if not df.empty:
    st.dataframe(df,use_container_width=True)
else:
    st.info("No contacts yet")
```

# ---------------- RAW DATA ----------------

elif menu == "Raw Data":

```
df = safe_load_contacts()

if not df.empty:
    st.dataframe(df)
else:
    st.warning("No data yet")
```
