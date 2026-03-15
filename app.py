import streamlit as st
import easyocr
from PIL import Image, ImageOps, ImageEnhance
import pandas as pd
import re
import os
import numpy as np
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="AI Business Card Scanner", layout="wide")

DATA_FILE = "contacts.xlsx"

DATA_COLUMNS = [
    "Name",
    "Designation",
    "Company",
    "Email",
    "Phones",
    "Website",
    "LinkedIn",
    "Address",
    "OCR_Text",
    "Source",
    "Created_At"
]

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_REGEX = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
WEBSITE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s]*)?",
    re.IGNORECASE
)
LINKEDIN_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s]+",
    re.IGNORECASE
)

NAME_PREFIXES = {
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "dr", "dr.", "prof", "prof."
}

TITLE_HINTS = [
    "engineer", "manager", "director", "founder", "co-founder",
    "ceo", "cto", "cfo", "coo", "developer", "designer",
    "consultant", "analyst", "president", "vice president", "vp",
    "head", "lead", "specialist", "sales", "marketing", "hr",
    "human resources", "product", "project", "operations",
    "business development", "administrator", "architect"
]

COMPANY_HINTS = [
    "inc", "llc", "ltd", "limited", "pvt", "private", "corp",
    "corporation", "company", "co.", "group", "solutions",
    "technologies", "technology", "systems", "software", "labs",
    "lab", "services", "industries", "studio", "consulting",
    "digital", "media", "associates", "partners", "enterprises"
]

ADDRESS_HINTS = [
    "street", "st", "road", "rd", "avenue", "ave", "floor", "fl",
    "suite", "ste", "building", "bldg", "block", "sector", "park",
    "plaza", "city", "state", "zip", "postal", "po box",
    "boulevard", "blvd", "lane", "ln", "drive", "dr"
]

FREE_EMAIL_BASES = {
    "gmail", "yahoo", "outlook", "hotmail", "icloud",
    "protonmail", "aol", "live", "msn"
}

menu = st.sidebar.selectbox(
    "Navigation",
    [
        "Scan Cards",
        "Contacts Dashboard",
        "Analytics",
        "Export Data",
        "Raw Database"
    ]
)


@st.cache_resource
def load_reader():
    return easyocr.Reader(["en"], gpu=False)


reader = load_reader()


# ---------------- UTILITIES ----------------
def normalize_text(text):
    text = str(text or "").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip(" \t,;|")
        if line:
            lines.append(line)

    dedup = []
    for line in lines:
        if not dedup or dedup[-1].lower() != line.lower():
            dedup.append(line)

    return "\n".join(dedup)


def clean_lines(text):
    return [line for line in normalize_text(text).split("\n") if line.strip()]


def normalize_case(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.title() if text.isupper() else text


def contains_keyword(text, keywords):
    low = str(text or "").lower()
    for k in keywords:
        if len(k) <= 3:
            if re.search(rf"\b{re.escape(k)}\b", low):
                return True
        else:
            if k in low:
                return True
    return False


def slugify(value):
    value = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "")).strip("_").lower()
    return value or "contact"


def split_phones(value):
    if not value:
        return []
    return [p.strip() for p in str(value).split(",") if p.strip()]


def normalize_phone(value):
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not 7 <= len(digits) <= 15:
        return ""
    return f"+{digits}" if raw.startswith("+") else digits


def ensure_columns(df):
    df = df.copy()
    for col in DATA_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[DATA_COLUMNS].fillna("")


def get_email_domain(email):
    email = str(email or "").strip().lower()
    if "@" not in email:
        return ""
    return email.split("@", 1)[1]


def infer_company_from_domain(email, website):
    domain = ""

    if website:
        domain = re.sub(r"^https?://(www\.)?", "", website.strip(), flags=re.I)
        domain = domain.split("/")[0].lower()
    elif email and "@" in email:
        domain = email.split("@", 1)[1].lower()

    if not domain:
        return ""

    base = domain.split(".")[0]
    if base in FREE_EMAIL_BASES:
        return ""

    return base.replace("-", " ").replace("_", " ").title()


# ---------------- DETECTION ----------------
def detect_email(text):
    matches = EMAIL_REGEX.findall(str(text or ""))
    return matches[0].lower() if matches else ""


def detect_phones(text):
    text = str(text or "")
    candidates = PHONE_REGEX.findall(text)
    phones = []

    for raw in candidates:
        cleaned = normalize_phone(raw)
        if cleaned and cleaned not in phones:
            phones.append(cleaned)

    return phones


def detect_website(text):
    text = str(text or "")

    for match in WEBSITE_REGEX.finditer(text):
        site = match.group(0).rstrip(".,;)")
        start = match.start()

        if start > 0 and text[start - 1] == "@":
            continue

        if "linkedin.com" in site.lower():
            continue

        if not site.lower().startswith(("http://", "https://")):
            site = "https://" + site

        return site

    return ""


def detect_linkedin(text):
    text = str(text or "")
    match = LINKEDIN_REGEX.search(text)

    if match:
        url = match.group(0).rstrip(".,;)")
        if not url.lower().startswith(("http://", "https://")):
            url = "https://" + url
        return url

    return ""


def is_contact_line(line):
    low = str(line or "").lower()
    return bool(
        detect_email(line)
        or detect_website(line)
        or detect_phones(line)
        or "linkedin.com" in low
    )


def looks_like_address(line):
    if is_contact_line(line):
        return False

    score = 0

    if re.search(r"\b\d{5,6}\b", line):
        score += 2
    if re.search(r"\d", line):
        score += 1
    if contains_keyword(line, ADDRESS_HINTS):
        score += 2
    if "," in line:
        score += 1

    return score >= 2


def detect_address(text):
    lines = clean_lines(text)
    candidates = []

    for i, line in enumerate(lines):
        if looks_like_address(line):
            score = 0
            if re.search(r"\b\d{5,6}\b", line):
                score += 2
            if contains_keyword(line, ADDRESS_HINTS):
                score += 2
            if "," in line:
                score += 1
            candidates.append((score, i, line))

    if not candidates:
        return ""

    candidates.sort(reverse=True)
    _, idx, best_line = candidates[0]

    result = [best_line]
    if idx + 1 < len(lines):
        next_line = lines[idx + 1]
        if not is_contact_line(next_line) and (
            looks_like_address(next_line) or re.search(r"\b\d{5,6}\b", next_line)
        ):
            result.append(next_line)

    return ", ".join(dict.fromkeys(result))


def looks_like_name(line):
    if not line or is_contact_line(line):
        return False

    if re.search(r"\d", line):
        return False

    if contains_keyword(line, COMPANY_HINTS):
        return False

    if contains_keyword(line, TITLE_HINTS):
        return False

    if contains_keyword(line, ADDRESS_HINTS):
        return False

    words = [w.strip(".,") for w in line.split() if w.strip(".,")]
    words = [w for w in words if w.lower() not in NAME_PREFIXES]

    if not (2 <= len(words) <= 4):
        return False

    valid_words = 0
    for w in words:
        if re.fullmatch(r"[A-Za-z][A-Za-z'’-]*", w):
            valid_words += 1
        elif len(w) == 1 and w.isalpha():
            valid_words += 1

    return valid_words >= 2


def normalize_name(line):
    words = [w.strip(".,") for w in line.split() if w.strip(".,")]
    words = [w for w in words if w.lower() not in NAME_PREFIXES]
    name = " ".join(words)
    return name.title() if name.isupper() else name


def detect_name(text):
    lines = clean_lines(text)
    candidates = []

    for idx, line in enumerate(lines[:8]):
        if looks_like_name(line):
            score = 10 - idx
            if len(line.split()) in (2, 3):
                score += 2
            if line.isupper():
                score += 1
            candidates.append((score, normalize_name(line)))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]

    return "Unknown"


def detect_designation(text):
    lines = clean_lines(text)
    candidates = []

    for idx, line in enumerate(lines[:8]):
        if is_contact_line(line):
            continue
        if contains_keyword(line, TITLE_HINTS):
            score = 10 - idx
            candidates.append((score, normalize_case(line)))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]

    return ""


def detect_company(text, name="", designation=""):
    lines = clean_lines(text)
    candidates = []

    for idx, line in enumerate(lines[:10]):
        low = line.lower()

        if not line:
            continue
        if normalize_case(line) == normalize_case(name):
            continue
        if normalize_case(line) == normalize_case(designation):
            continue
        if is_contact_line(line):
            continue
        if looks_like_address(line):
            continue

        score = 0

        if contains_keyword(low, COMPANY_HINTS):
            score += 5
        if idx < 3:
            score += 3
        if line.isupper():
            score += 2
        if 1 <= len(line.split()) <= 6:
            score += 1
        if not contains_keyword(line, TITLE_HINTS):
            score += 1

        if score > 0:
            candidates.append((score - idx * 0.2, normalize_case(line)))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]

    return ""


def parse_contact(text):
    text = normalize_text(text)

    email = detect_email(text)
    phones = detect_phones(text)
    website = detect_website(text)
    linkedin = detect_linkedin(text)
    designation = detect_designation(text)
    name = detect_name(text)
    company = detect_company(text, name=name, designation=designation)
    address = detect_address(text)

    if not company:
        company = infer_company_from_domain(email, website)

    return {
        "Name": name,
        "Designation": designation,
        "Company": company,
        "Email": email,
        "Phones": ", ".join(phones),
        "Website": website,
        "LinkedIn": linkedin,
        "Address": address,
    }


# ---------------- OCR ----------------
def preprocess_image(image):
    image = ImageOps.exif_transpose(image).convert("RGB")

    max_width = 1600
    if image.width > max_width:
        scale = max_width / image.width
        image = image.resize(
            (int(image.width * scale), int(image.height * scale))
        )

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.3)
    gray = ImageEnhance.Sharpness(gray).enhance(1.4)

    return gray


def score_ocr_text(text):
    score = len(text)

    if detect_email(text):
        score += 80
    if detect_phones(text):
        score += 50
    if detect_website(text):
        score += 30
    if detect_linkedin(text):
        score += 20
    if detect_name(text) != "Unknown":
        score += 10

    return score


@st.cache_data(show_spinner=False)
def extract_text_from_bytes(file_bytes):
    image = Image.open(BytesIO(file_bytes))
    base = preprocess_image(image)

    best_text = ""
    best_score = -1

    for angle in (0, 90, 180, 270):
        rotated = base.rotate(angle, expand=True)

        try:
            result = reader.readtext(np.array(rotated), detail=0, paragraph=False)
            text = normalize_text("\n".join(result))
            score = score_ocr_text(text)

            if score > best_score:
                best_score = score
                best_text = text
        except Exception:
            continue

    return best_text


# ---------------- VCARD / EXPORT ----------------
def vcard_escape(value):
    value = str(value or "")
    value = value.replace("\\", "\\\\")
    value = value.replace(";", r"\;")
    value = value.replace(",", r"\,")
    value = value.replace("\n", r"\n")
    return value


def generate_vcard(contact):
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{vcard_escape(contact.get('Name', ''))}",
    ]

    if contact.get("Company"):
        lines.append(f"ORG:{vcard_escape(contact['Company'])}")

    if contact.get("Designation"):
        lines.append(f"TITLE:{vcard_escape(contact['Designation'])}")

    for phone in split_phones(contact.get("Phones", "")):
        lines.append(f"TEL;TYPE=CELL:{vcard_escape(phone)}")

    if contact.get("Email"):
        lines.append(f"EMAIL;TYPE=INTERNET:{vcard_escape(contact['Email'])}")

    if contact.get("Website"):
        lines.append(f"URL:{vcard_escape(contact['Website'])}")

    if contact.get("LinkedIn"):
        lines.append(
            f"X-SOCIALPROFILE;TYPE=linkedin:{vcard_escape(contact['LinkedIn'])}"
        )

    if contact.get("Address"):
        lines.append(f"ADR;TYPE=WORK:;;{vcard_escape(contact['Address'])};;;;")

    lines.append("END:VCARD")
    return "\n".join(lines)


def generate_all_vcards(df):
    cards = []
    for _, row in df.fillna("").iterrows():
        cards.append(generate_vcard(row.to_dict()))
    return "\n".join(cards)


def contact_summary(contact):
    parts = [
        ("Name", contact.get("Name", "")),
        ("Designation", contact.get("Designation", "")),
        ("Company", contact.get("Company", "")),
        ("Email", contact.get("Email", "")),
        ("Phones", contact.get("Phones", "")),
        ("Website", contact.get("Website", "")),
        ("LinkedIn", contact.get("LinkedIn", "")),
        ("Address", contact.get("Address", "")),
    ]
    return "\n".join([f"{k}: {v}" for k, v in parts if str(v).strip()])


def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        ensure_columns(df).to_excel(writer, index=False, sheet_name="Contacts")
    return output.getvalue()


# ---------------- DATABASE ----------------
def load_contacts():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_excel(DATA_FILE)
            return ensure_columns(df)
        except Exception:
            return pd.DataFrame(columns=DATA_COLUMNS)

    return pd.DataFrame(columns=DATA_COLUMNS)


def save_contacts_dataframe(df):
    df = ensure_columns(df)
    df.to_excel(DATA_FILE, index=False)


def duplicate_reason(df, contact):
    email = str(contact.get("Email", "")).strip().lower()
    phones = {
        normalize_phone(p)
        for p in split_phones(contact.get("Phones", ""))
        if normalize_phone(p)
    }
    name = str(contact.get("Name", "")).strip().lower()
    company = str(contact.get("Company", "")).strip().lower()

    for _, row in df.fillna("").iterrows():
        row_email = str(row.get("Email", "")).strip().lower()
        row_phones = {
            normalize_phone(p)
            for p in split_phones(row.get("Phones", ""))
            if normalize_phone(p)
        }
        row_name = str(row.get("Name", "")).strip().lower()
        row_company = str(row.get("Company", "")).strip().lower()

        if email and row_email and email == row_email:
            return "same email"

        if phones and row_phones and phones.intersection(row_phones):
            return "same phone"

        if name and company and name == row_name and company == row_company:
            return "same name + company"

    return ""


def save_contact(contact):
    df = load_contacts()
    reason = duplicate_reason(df, contact)

    if reason:
        return False, f"Duplicate contact detected ({reason})."

    row = {col: contact.get(col, "") for col in DATA_COLUMNS}
    row["Created_At"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_contacts_dataframe(df)

    return True, "Contact saved successfully."


# ---------------- UI: SCAN CARDS ----------------
if menu == "Scan Cards":
    st.title("AI Business Card Scanner")

    option = st.radio("Input Method", ["Upload Images", "Use Camera"])
    images = []

    if option == "Upload Images":
        files = st.file_uploader(
            "Upload business card images",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True
        )
        if files:
            images = files

    else:
        cam = st.camera_input("Take a photo")
        if cam:
            images = [cam]

    if not images:
        st.info("Upload or capture a business card to begin.")

    for idx, file in enumerate(images):
        st.divider()
        st.subheader(f"Card {idx + 1}")

        try:
            file_bytes = file.getvalue()
            image = Image.open(BytesIO(file_bytes))
        except Exception as e:
            st.error(f"Could not open image: {e}")
            continue

        source_name = getattr(file, "name", f"camera_card_{idx + 1}.jpg")

        st.image(image, caption=source_name, use_container_width=True)

        with st.spinner("Extracting details..."):
            text = extract_text_from_bytes(file_bytes)
            extracted = parse_contact(text)

        col1, col2 = st.columns(2)

        with col1:
            st.text_area(
                "Detected Text",
                text,
                height=240,
                key=f"ocr_text_{idx}"
            )

        with col2:
            name = st.text_input("Name", extracted["Name"], key=f"name_{idx}")
            designation = st.text_input(
                "Designation", extracted["Designation"], key=f"designation_{idx}"
            )
            company = st.text_input(
                "Company", extracted["Company"], key=f"company_{idx}"
            )
            email = st.text_input("Email", extracted["Email"], key=f"email_{idx}")
            phones = st.text_input(
                "Phone(s) - comma separated",
                extracted["Phones"],
                key=f"phones_{idx}"
            )
            website = st.text_input(
                "Website", extracted["Website"], key=f"website_{idx}"
            )
            linkedin = st.text_input(
                "LinkedIn", extracted["LinkedIn"], key=f"linkedin_{idx}"
            )
            address = st.text_area(
                "Address",
                extracted["Address"],
                height=80,
                key=f"address_{idx}"
            )

        current_contact = {
            "Name": name.strip() or "Unknown",
            "Designation": designation.strip(),
            "Company": company.strip(),
            "Email": email.strip(),
            "Phones": phones.strip(),
            "Website": website.strip(),
            "LinkedIn": linkedin.strip(),
            "Address": address.strip(),
            "OCR_Text": text,
            "Source": source_name,
        }

        st.caption("Review before saving")
        st.code(contact_summary(current_contact), language="text")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("Save Contact", key=f"save_{idx}"):
                ok, msg = save_contact(current_contact)
                if ok:
                    st.success(msg)
                else:
                    st.warning(msg)

        with c2:
            st.download_button(
                "Download vCard",
                generate_vcard(current_contact),
                file_name=f"{slugify(name)}.vcf",
                mime="text/vcard",
                key=f"vcf_{idx}"
            )


# ---------------- UI: DASHBOARD ----------------
elif menu == "Contacts Dashboard":
    st.title("Contacts Dashboard")

    df = load_contacts()

    if df.empty:
        st.warning("No contacts yet.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Contacts", len(df))
        c2.metric(
            "Unique Companies",
            df["Company"].replace("", pd.NA).dropna().nunique()
        )
        c3.metric(
            "With Email",
            (df["Email"].astype(str).str.strip() != "").sum()
        )
        c4.metric(
            "With Phone",
            (df["Phones"].astype(str).str.strip() != "").sum()
        )

        search = st.text_input(
            "Search by name, company, email, phone, website, LinkedIn or address"
        )

        filtered = df.copy()

        if search.strip():
            cols = [
                "Name", "Designation", "Company", "Email", "Phones",
                "Website", "LinkedIn", "Address"
            ]
            mask = filtered[cols].astype(str).apply(
                lambda s: s.str.contains(search, case=False, na=False, regex=False)
            )
            filtered = filtered[mask.any(axis=1)]

        filtered = filtered.sort_values(
            by="Created_At", ascending=False, na_position="last"
        )

        st.dataframe(filtered, use_container_width=True, hide_index=True)


# ---------------- UI: ANALYTICS ----------------
elif menu == "Analytics":
    st.title("Contact Analytics")

    df = load_contacts()

    if df.empty:
        st.warning("No data available.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Contacts", len(df))
        c2.metric("Unique Companies", df["Company"].replace("", pd.NA).dropna().nunique())
        c3.metric("Unique Email Domains", df["Email"].apply(get_email_domain).replace("", pd.NA).dropna().nunique())
        c4.metric("With LinkedIn", (df["LinkedIn"].astype(str).str.strip() != "").sum())

        company_counts = df["Company"].replace("", "Unknown").value_counts().head(10)
        st.subheader("Top Companies")
        st.bar_chart(company_counts)

        domain_counts = df["Email"].apply(get_email_domain)
        domain_counts = domain_counts.replace("", pd.NA).dropna().value_counts().head(10)
        if not domain_counts.empty:
            st.subheader("Top Email Domains")
            st.bar_chart(domain_counts)

        created = pd.to_datetime(df["Created_At"], errors="coerce").dt.date
        created_counts = created.value_counts().sort_index()
        if not created_counts.empty:
            st.subheader("Contacts Added Over Time")
            st.line_chart(created_counts)


# ---------------- UI: EXPORT ----------------
elif menu == "Export Data":
    st.title("Export Contacts")

    df = load_contacts()

    if df.empty:
        st.warning("No contacts to export.")
    else:
        csv_data = ensure_columns(df).to_csv(index=False).encode("utf-8")
        excel_data = to_excel_bytes(df)
        vcf_data = generate_all_vcards(df)

        st.download_button(
            "Download CSV",
            csv_data,
            file_name="contacts.csv",
            mime="text/csv"
        )

        st.download_button(
            "Download Excel",
            excel_data,
            file_name="contacts.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.download_button(
            "Download All vCards",
            vcf_data,
            file_name="contacts.vcf",
            mime="text/vcard"
        )


# ---------------- UI: RAW DATABASE ----------------
elif menu == "Raw Database":
    st.title("Raw Database")

    df = load_contacts()

    if df.empty:
        st.warning("Database is empty.")
    else:
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            key="raw_editor"
        )

        c1, c2 = st.columns(2)

        with c1:
            if st.button("Save Table Changes"):
                save_contacts_dataframe(edited_df)
                st.success("Database updated successfully.")

        with c2:
            options = {
                f"{i + 1}. {df.loc[i, 'Name']} | {df.loc[i, 'Email']}": i
                for i in df.index
            }

            selected = st.multiselect("Select rows to delete", list(options.keys()))

            if st.button("Delete Selected Rows"):
                if selected:
                    rows_to_delete = [options[item] for item in selected]
                    new_df = df.drop(rows_to_delete).reset_index(drop=True)
                    save_contacts_dataframe(new_df)
                    st.success("Selected rows deleted.")
                    st.rerun()
                else:
                    st.warning("Please select at least one row to delete.")
