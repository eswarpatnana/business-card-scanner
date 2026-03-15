import streamlit as st
import easyocr
from PIL import Image, ImageOps, ImageEnhance
import pandas as pd
import re
import os
import numpy as np
import cv2
from io import BytesIO
from datetime import datetime

# Optional NLP

try:
import spacy
nlp = spacy.load("en_core_web_sm")
NLP_AVAILABLE = True
except:
NLP_AVAILABLE = False

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

DATA_FILE = "contacts.xlsx"

DATA_COLUMNS = [
"Name","Designation","Category","Company","Email",
"Phones","Website","LinkedIn","Address","OCR_Text",
"Source","Created_At"
]

# ---------------- REGEX ----------------

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+.[A-Za-z]{2,}")
PHONE_REGEX = re.compile(r"(?:+?\d[\d\s().-]{7,}\d)")
WEBSITE_REGEX = re.compile(r"(?:https?://)?(?:www.)?[A-Za-z0-9.-]+.[A-Za-z]{2,}",re.I)
LINKEDIN_REGEX = re.compile(r"(?:https?://)?(?:www.)?linkedin.com/[^\s]+",re.I)

# ---------------- CONTACT CATEGORIES ----------------

CATEGORY_RULES = {
"Engineering":["engineer","developer","software","programmer","architect"],
"Management":["manager","director","ceo","cto","founder","vp"],
"Design":["designer","ui","ux","graphic"],
"Marketing":["marketing","sales","growth","business development"],
"Finance":["finance","accountant","banker"],
"Healthcare":["doctor","physician","nurse"],
"Education":["teacher","professor","trainer"]
}

# ---------------- OCR ----------------

@st.cache_resource
def load_reader():
return easyocr.Reader(['en'], gpu=False)

reader = load_reader()

# ---------------- IMAGE PREPROCESS ----------------

def preprocess_image(image):

```
image = ImageOps.exif_transpose(image).convert("RGB")
img = np.array(image)

gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray,(3,3),0)

thresh = cv2.adaptiveThreshold(
    blur,255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,11,2
)

return thresh
```

# ---------------- LOGO DETECTION ----------------

def detect_logo_region(image):

```
img = np.array(image)
gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

edges = cv2.Canny(gray,50,150)

contours,_ = cv2.findContours(edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

h,w = gray.shape
logo_boxes=[]

for c in contours:

    x,y,wc,hc = cv2.boundingRect(c)

    area = wc*hc

    if area > 1000 and wc < w*0.5 and hc < h*0.5:

        logo_boxes.append((x,y,wc,hc))

return logo_boxes
```

# ---------------- TEXT UTIL ----------------

def normalize_text(text):

```
text=str(text or "").replace("\r","\n")

lines=[]

for line in text.split("\n"):

    line=re.sub(r"\s+"," ",line).strip(" ,;|")

    if line:
        lines.append(line)

return "\n".join(lines)
```

# ---------------- DETECTORS ----------------

def detect_email(text):

```
m=EMAIL_REGEX.findall(text)

return m[0] if m else ""
```

def detect_phones(text):

```
phones=[]

for p in PHONE_REGEX.findall(text):

    digits=re.sub(r"\D","",p)

    if 7<=len(digits)<=15 and digits not in phones:

        phones.append(digits)

return phones
```

def detect_website(text):

```
m=WEBSITE_REGEX.findall(text)

if m:

    site=m[0]

    if not site.startswith("http"):

        site="https://"+site

    return site

return ""
```

def detect_linkedin(text):

```
m=LINKEDIN_REGEX.search(text)

if m:

    url=m.group(0)

    if not url.startswith("http"):

        url="https://"+url

    return url

return ""
```

# ---------------- NAME DETECTION ----------------

def detect_name(text):

```
if NLP_AVAILABLE:

    doc = nlp(text)

    for ent in doc.ents:

        if ent.label_ == "PERSON":

            return ent.text

lines=text.split("\n")

for line in lines[:6]:

    if 2<=len(line.split())<=4 and not re.search(r"\d",line):

        return line

return "Unknown"
```

# ---------------- DESIGNATION ----------------

def detect_designation(text):

```
lines=text.split("\n")

for line in lines:

    low=line.lower()

    for words in CATEGORY_RULES.values():

        for w in words:

            if w in low:

                return line

return ""
```

# ---------------- CATEGORY ----------------

def detect_category(designation):

```
low=str(designation).lower()

for cat,words in CATEGORY_RULES.items():

    for w in words:

        if w in low:

            return cat

return "Other"
```

# ---------------- COMPANY ----------------

def detect_company(text,name,designation):

```
lines=text.split("\n")

for line in lines[:8]:

    if line not in (name,designation):

        if len(line.split())<=5:

            return line

return ""
```

# ---------------- ADDRESS ----------------

def detect_address(text):

```
lines=text.split("\n")

for line in lines:

    if re.search(r"\d{5,6}",line):

        return line

return ""
```

# ---------------- PARSE CONTACT ----------------

def parse_contact(text):

```
name = detect_name(text)

designation = detect_designation(text)

category = detect_category(designation)

company = detect_company(text,name,designation)

return {

    "Name":name,

    "Designation":designation,

    "Category":category,

    "Company":company,

    "Email":detect_email(text),

    "Phones":", ".join(detect_phones(text)),

    "Website":detect_website(text),

    "LinkedIn":detect_linkedin(text),

    "Address":detect_address(text)

}
```

# ---------------- OCR PIPELINE ----------------

def extract_text_from_bytes(file_bytes):

```
image=Image.open(BytesIO(file_bytes))

base=preprocess_image(image)

best_text=""
best_score=-1

for angle in (0,90,180,270):

    rotated=np.rot90(base,angle//90)

    try:

        result=reader.readtext(rotated,detail=0)

        text=normalize_text("\n".join(result))

        score=len(text)

        if detect_email(text):
            score+=80

        if detect_phones(text):
            score+=50

        if score>best_score:

            best_score=score
            best_text=text

    except:
        pass

return best_text,image
```

# ---------------- DATABASE ----------------

def load_contacts():

```
if os.path.exists(DATA_FILE):

    return pd.read_excel(DATA_FILE)

return pd.DataFrame(columns=DATA_COLUMNS)
```

def save_contacts(df):

```
df.to_excel(DATA_FILE,index=False)
```

def save_contact(contact):

```
df=load_contacts()

row={col:contact.get(col,"") for col in DATA_COLUMNS}

row["Created_At"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")

df=pd.concat([df,pd.DataFrame([row])],ignore_index=True)

save_contacts(df)
```

# ---------------- UI ----------------

menu = st.sidebar.selectbox("Navigation",["Scan Cards","Dashboard"])

if menu=="Scan Cards":

```
st.title("AI Business Card Scanner")

files = st.file_uploader(
    "Upload business cards",
    type=["jpg","png","jpeg"],
    accept_multiple_files=True
)

if files:

    for file in files:

        bytes=file.getvalue()

        text,image = extract_text_from_bytes(bytes)

        contact = parse_contact(text)

        st.image(image,use_container_width=True)

        st.text_area("OCR Text",text,height=200)

        # Logo detection
        boxes = detect_logo_region(image)

        if boxes:

            st.success(f"Logo region detected: {len(boxes)} area(s)")

        for k,v in contact.items():

            contact[k]=st.text_input(k,v)

        if st.button("Save Contact"):

            save_contact(contact)

            st.success("Contact saved")
```

elif menu=="Dashboard":

```
df=load_contacts()

if df.empty:

    st.warning("No contacts yet")

else:

    st.metric("Total Contacts",len(df))

    st.dataframe(df,use_container_width=True)
```
