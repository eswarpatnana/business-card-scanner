import streamlit as st
import easyocr
from PIL import Image
import pandas as pd
import numpy as np
import re
import os

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

# Sidebar Menu
menu = st.sidebar.selectbox(
    "Menu",
    ["Scan Card", "View Contacts"]
)

file = "scanned_cards.xlsx"

# -------------------- SCAN CARD --------------------

if menu == "Scan Card":

    st.title("📇 AI Business Card Scanner")

    option = st.radio(
        "Choose Input Method",
        ["Upload Image", "Use Camera"]
    )

    image = None

    if option == "Upload Image":
        uploaded = st.file_uploader("Upload Business Card", type=["jpg","png","jpeg"])
        if uploaded:
            image = Image.open(uploaded)

    if option == "Use Camera":
        camera_image = st.camera_input("Take a photo")
        if camera_image:
            image = Image.open(camera_image)

    if image is not None:

        st.image(image, caption="Business Card", use_column_width=True)

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

        # Detect Name (First line usually)
        name = ""
        for line in result:
            if not re.search(r'\d', line):
                name = line
                break

        # Detect Occupation
        occupation = ""
        if len(result) > 1:
            occupation = result[1]

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

        if os.path.exists(file):

            old = pd.read_excel(file)

            new = pd.concat([old, df], ignore_index=True)

            new.to_excel(file, index=False)

        else:

            df.to_excel(file, index=False)

        st.success("Details saved to Excel!")

# -------------------- VIEW CONTACTS --------------------

if menu == "View Contacts":

    st.title("📂 Saved Contacts")

    if os.path.exists(file):

        df = pd.read_excel(file)

        st.dataframe(df)

    else:

        st.warning("No contacts saved yet.")
