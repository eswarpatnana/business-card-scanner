import streamlit as st
import easyocr
from PIL import Image, ImageOps
import pandas as pd
import re
import os
import numpy as np
import cv2
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

DATA_FILE = "contacts.xlsx"

COLUMNS = [
"Name","Designation","Company","Email","Phones",
"Website","LinkedIn","Address","OCR_Text","Source","Created_At"
]

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+.[A-Za-z]{2,}")
PHONE_REGEX = re.compile(r"(?:+?\d[\d\s().-]{7,}\d)")
WEB_REGEX = re.compile(r"(?:https?://)?(?:www.)?[A-Za-z0-9.-]+.[A-Za-z]{2,}",re.I)

TITLE_HINTS = [
"engineer","developer","manager","director","founder","ceo","cto",
"designer","consultant","analyst","marketing","sales","architect"
]

ADDRESS_HINTS = [
"street","road","avenue","sector","suite","building","city","zip"
]

# ---------------- OCR ----------------

@st.cache_resource
def load_reader():
return easyocr.Reader(['en'],gpu=False)

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

# ---------------- LAYOUT OCR ----------------

def run_layout_ocr(image):

```
results = reader.readtext(image)

data=[]

for box,text,conf in results:

    x = int(box[0][0])
    y = int(box[0][1])

    data.append({
    "text":text,
    "x":x,
    "y":y,
    "conf":conf
    })

df=pd.DataFrame(data)

if not df.empty:
    df=df.sort_values(by=["y","x"])

return df
```

# ---------------- TEXT HELPERS ----------------

def normalize_text(lines):

```
lines=[re.sub(r"\s+"," ",l).strip() for l in lines if l.strip()]

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
m=WEB_REGEX.findall(text)

if m:

    site=m[0]

    if not site.startswith("http"):
        site="https://"+site

    return site

return ""
```

# ---------------- LAYOUT NAME DETECTION ----------------

def detect_name(layout_df):

```
if layout_df.empty:
    return "Unknown"

top_area = layout_df[layout_df["y"] < layout_df["y"].median()]

for _,row in top_area.iterrows():

    line=row["text"]

    if 2<=len(line.split())<=4 and not re.search(r"\d",line):

        return line

return "Unknown"
```

# ---------------- DESIGNATION ----------------

def detect_designation(lines):

```
for l in lines:

    low=l.lower()

    for t in TITLE_HINTS:

        if t in low:

            return l

return ""
```

# ---------------- COMPANY ----------------

def detect_company(layout_df,name):

```
if layout_df.empty:
    return ""

for _,row in layout_df.iterrows():

    text=row["text"]

    if text!=name and len(text.split())<=5:

        if text.isupper():

            return text

return ""
```

# ---------------- ADDRESS ----------------

def detect_address(lines):

```
for l in lines:

    if any(a in l.lower() for a in ADDRESS_HINTS):

        return l

return ""
```

# ---------------- LLM STYLE PARSER ----------------

def smart_parse(layout_df):

```
if layout_df.empty:
    return {}

lines=layout_df["text"].tolist()

text="\n".join(lines)

name=detect_name(layout_df)

designation=detect_designation(lines)

company=detect_company(layout_df,name)

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

# ---------------- OCR PIPELINE ----------------

def extract_text_from_bytes(file_bytes):

```
image = Image.open(BytesIO(file_bytes))

processed = preprocess_image(image)

best_df=None
best_score=-1

for angle in (0,90,180,270):

    rotated=np.rot90(processed,angle//90)

    try:

        df=run_layout_ocr(rotated)

        text="\n".join(df["text"].tolist())

        score=len(text)

        if detect_email(text):
            score+=50

        if detect_phones(text):
            score+=40

        if score>best_score:

            best_score=score
            best_df=df

    except:
        pass

return best_df,image
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

        layout_df,image=extract_text_from_bytes(bytes)

        st.image(image,use_container_width=True)

        if layout_df is None or layout_df.empty:

            st.warning("No text detected")
            continue

        parsed=smart_parse(layout_df)

        st.subheader("Detected Text")

        st.text_area(
        "OCR Output",
        normalize_text(layout_df["text"].tolist()),
        height=200
        )

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

    st.warning("No contacts saved yet")

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
