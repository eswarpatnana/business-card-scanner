import streamlit as st
import easyocr
from PIL import Image, ImageOps, ImageEnhance
import pandas as pd
import numpy as np
import cv2
import re
import os
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

DATA_FILE = "contacts.xlsx"

COLUMNS = [
"Name","Designation","Company","Email","Phones",
"Website","Address","OCR_Text","Created_At"
]

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+.[A-Za-z]{2,}")
PHONE_REGEX = re.compile(r"(?:+?\d[\d\s().-]{7,}\d)")
WEB_REGEX = re.compile(r"(?:https?://)?(?:www.)?[A-Za-z0-9.-]+.[A-Za-z]{2,}",re.I)

TITLE_HINTS = [
"engineer","developer","manager","director","founder",
"designer","consultant","analyst","marketing","sales"
]

ADDRESS_HINTS = [
"street","road","avenue","sector","suite","building","city"
]

@st.cache_resource
def load_reader():
return easyocr.Reader(['en'],gpu=False)

reader = load_reader()

# ---------------- IMAGE PREPROCESS METHODS ----------------

def preprocess_methods(image):

```
image = ImageOps.exif_transpose(image).convert("RGB")
img = np.array(image)

gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

# method1 normal gray
m1 = gray

# method2 threshold
m2 = cv2.adaptiveThreshold(
    gray,255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,11,2
)

# method3 sharpen
kernel = np.array([
    [-1,-1,-1],
    [-1,9,-1],
    [-1,-1,-1]
])
m3 = cv2.filter2D(gray,-1,kernel)

# method4 contrast boost
pil = Image.fromarray(gray)
pil = ImageEnhance.Contrast(pil).enhance(1.8)
m4 = np.array(pil)

return [m1,m2,m3,m4]
```

# ---------------- MULTI PASS OCR ----------------

def run_best_ocr(image):

```
methods = preprocess_methods(image)

best_text=""
best_conf=0

for img in methods:

    try:

        result = reader.readtext(img)

        texts=[]
        confs=[]

        for box,text,conf in result:

            texts.append(text)
            confs.append(conf)

        if not texts:
            continue

        text="\n".join(texts)

        confidence=sum(confs)/len(confs)

        if confidence>best_conf:

            best_conf=confidence
            best_text=text

    except:
        pass

return best_text,best_conf
```

# ---------------- DETECTION ----------------

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
m=WEB_REGEX.findall(text)

if m:
    site=m[0]
    if not site.startswith("http"):
        site="https://"+site
    return site

return ""
```

def detect_name(lines):

```
for l in lines[:6]:

    if 2<=len(l.split())<=4 and not re.search(r"\d",l):

        return l

return "Unknown"
```

def detect_designation(lines):

```
for l in lines:

    low=l.lower()

    for t in TITLE_HINTS:

        if t in low:
            return l

return ""
```

def detect_company(lines,name):

```
for l in lines:

    if l!=name and l.isupper() and len(l.split())<=5:
        return l

return ""
```

def detect_address(lines):

```
for l in lines:

    for a in ADDRESS_HINTS:

        if a in l.lower():
            return l

return ""
```

# ---------------- PARSER ----------------

def parse_contact(text):

```
lines=[re.sub(r"\s+"," ",l).strip() for l in text.split("\n") if l.strip()]

name=detect_name(lines)

designation=detect_designation(lines)

company=detect_company(lines,name)

email=detect_email(text)

phones=detect_phones(text)

website=detect_website(text)

address=detect_address(lines)

return {
    "Name":name,
    "Designation":designation,
    "Company":company,
    "Email":email,
    "Phones":", ".join(phones),
    "Website":website,
    "Address":address
}
```

# ---------------- DATABASE ----------------

def load_contacts():

```
if os.path.exists(DATA_FILE):

    return pd.read_excel(DATA_FILE)

return pd.DataFrame(columns=COLUMNS)
```

def save_contact(contact):

```
df=load_contacts()

contact["Created_At"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")

df=pd.concat([df,pd.DataFrame([contact])],ignore_index=True)

df.to_excel(DATA_FILE,index=False)
```

# ---------------- UI ----------------

menu = st.sidebar.selectbox(
"Menu",
["Scan Cards","Dashboard","Export"]
)

# ---------------- SCAN ----------------

if menu=="Scan Cards":

```
st.title("AI Business Card Scanner")

files = st.file_uploader(
"Upload business cards",
type=["jpg","jpeg","png"],
accept_multiple_files=True
)

if files:

    for f in files:

        bytes=f.getvalue()

        image = Image.open(BytesIO(bytes))

        st.image(image,use_container_width=True)

        with st.spinner("Running multi-pass OCR..."):

            text,conf = run_best_ocr(image)

        st.success(f"OCR Confidence Score: {round(conf,2)}")

        st.text_area("Detected Text",text,height=200)

        parsed=parse_contact(text)

        for k,v in parsed.items():

            parsed[k]=st.text_input(k,v)

        if st.button("Save Contact"):

            save_contact(parsed)

            st.success("Contact saved")
```

# ---------------- DASHBOARD ----------------

elif menu=="Dashboard":

```
df=load_contacts()

if df.empty:

    st.warning("No contacts yet")

else:

    st.metric("Total Contacts",len(df))

    st.dataframe(df,use_container_width=True)
```

# ---------------- EXPORT ----------------

elif menu=="Export":

```
df=load_contacts()

if not df.empty:

    st.download_button(
    "Download CSV",
    df.to_csv(index=False),
    file_name="contacts.csv"
    )
```
