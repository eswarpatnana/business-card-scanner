import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import numpy as np
import re
import os

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

st.title("📇 AI Business Card Scanner")

# Upload Image
uploaded_image = st.file_uploader("Upload Business Card", type=["png","jpg","jpeg"])

if uploaded_image is not None:

    image = Image.open(uploaded_image)

    st.image(image, caption="Uploaded Business Card", use_column_width=True)

    # OCR Reader
    reader = easyocr.Reader(['en'])

    result = reader.readtext(np.array(image), detail=0)

    text = " ".join(result)

    st.subheader("Detected Text")
    st.write(text)

    # Extract Email
    email = re.findall(r'\S+@\S+', text)

    # Extract Phone
    phone = re.findall(r'\+?\d[\d\s-]{8,}\d', text)

    # Extract Website
    website = re.findall(r'(www\.\S+)', text)

    # Name guess (first line)
    name = result[0] if len(result) > 0 else ""

    # Occupation guess (second line)
    occupation = result[1] if len(result) > 1 else ""

    st.subheader("Detected Details")

    st.write("👤 Name:", name)
    st.write("💼 Occupation:", occupation)
    st.write("📧 Email:", email[0] if email else "")
    st.write("📞 Phone:", phone[0] if phone else "")
    st.write("🌐 Website:", website[0] if website else "")

    data = {
        "Name":[name],
        "Occupation":[occupation],
        "Email":[email[0] if email else ""],
        "Phone":[phone[0] if phone else ""],
        "Website":[website[0] if website else ""]
    }

    df = pd.DataFrame(data)

    file = "scanned_cards.xlsx"

    if os.path.exists(file):

        old_df = pd.read_excel(file)

        new_df = pd.concat([old_df, df], ignore_index=True)

        new_df.to_excel(file, index=False)

    else:

        df.to_excel(file, index=False)

    st.success("Details saved to Excel!")

# Show database

if os.path.exists("scanned_cards.xlsx"):

    st.subheader("Saved Contacts Database")

    saved_df = pd.read_excel("scanned_cards.xlsx")

    st.dataframe(saved_df)
