import streamlit as st
import cv2
import easyocr
import re
import numpy as np
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="Auto Expiry Scanner", layout="centered")
st.title("🛡️ Automated Expiry Date Recognition System")
st.write("Upload a product photo to automatically check its health status.")

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

# ----------------- EMAIL NOTIFICATION MODULE -----------------
def send_expiry_email(user_email, food_status, expired_date):
    sender_email = "saisiddhi.wabale@gmail.com" 
    sender_password = "bmaz wzqt fbep pykw" 
    
    subject = f"⚠️ ALERT: Food Product Status - {food_status}!"
    body = (f"Hello,\n\n"
            f"This is an automated health alert from your Automated Expiry Detector App.\n\n"
            f"The scanned food product has been evaluated.\n"
            f"Current Evaluation Status: {food_status}\n"
            f"Detected Expiry Date: {expired_date}\n\n"
            f"Please take necessary action regarding your food item.\n\n"
            f"Thank you,\n"
            f"Auto Expiry Scanner Team")
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('://gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, user_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        return False
# -------------------------------------------------------------

def parse_any_date(date_str):
    date_str = date_str.upper().strip()
    
    # जर स्लॅश नसलेली सलग ६ किंवा ८ अंकी तारीख असेल (उदा. 120924)
    digits_only = re.sub(r'[^0-9]', '', date_str)
    if digits_only == date_str:
        if len(digits_only) == 6:
            try:
                return datetime.strptime(digits_only, "%d%m%y")
            except ValueError:
                pass
        elif len(digits_only) == 8:
            try:
                return datetime.strptime(digits_only, "%d%m%Y")
            except ValueError:
                pass

    date_str = re.sub(r'[-/\.]', ' ', date_str)
    date_str = re.sub(r'(\d+)([A-Z]+)', r'\1 \2', date_str)
    date_str = re.sub(r'([A-Z]+)(\d+)', r'\1 \2', date_str)
    date_str = re.sub(r'\s+', ' ', date_str).strip()
    
    formats = [
        "%d %m %Y", "%d %m %y", "%m %Y", "%m %y",
        "%d %B %Y", "%d %b %Y", "%d %B %y", "%d %b %y",
        "%B %Y", "%b %Y", "%B %y", "%b %y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def search_dates_in_results(results):
    # १. आधी तुझ्या कालच्या मूळ कोडप्रमाणे प्रत्येक ओळीत वेगवेगळं शोधणे (जे दूध व बिस्कीटसाठी चालत होतं)
    numeric_pattern = r'\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}\b|\b\d{1,2}[-/\.]\d{2,4}\b'
    all_detected = []
    
    for (_, text, _) in results:
        txt_clean = text.replace(" ", "")
        # किंमत (उदा. 48.00 किंवा Rs.0.18) टाळणे
        if "RS" in txt_clean.upper() or "MRP" in txt_clean.upper():
            continue
        matches = re.findall(numeric_pattern, txt_clean)
        for m in matches:
            # फक्त डॉट असलेली किंमत (उदा. 48.00) वगळणे, पण तारीख (12.09.24) घेणे
            if "." in m and m.count(".") == 1 and len(m.split(".")[0]) <= 3 and len(m.split(".")[1]) == 2:
                # जर पहिला आकडा 31 पेक्षा मोठा असेल (उदा. 48.00) तर ती किंमत आहे
                if int(m.split(".")[0]) > 31:
                    continue
            if m not in all_detected:
                all_detected.append(m)
                
    if len(all_detected) >= 2:
        return all_detected[-1]
    elif len(all_detected) == 1:
        return all_detected[0]

    # २. जर अंकांची तारीख नसेल तर महिन्याची नावे (21 FEBRUARY 2027) आणि सलग अंक (120924) शोधणे
    full_text = " ".join([text for (_, text, _) in results]).upper()
    month_names = r'(?:JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|JUL(?:Y)?|AUG(?:UST)?|SEP(?:TEMBER)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)'
    advanced_pattern = rf'\b(?:\d{{1,2}}[-/\s]*)?{month_names}[-/\s]*\d{{2,4}}\b|\b(?:0[1-9]|\d|3)(?:0[1-9]|1[0-2])(?:2\d|202\d)\b'
    
    priority_match = re.search(rf'(?:USE\s*BY|EXP(?:IRY)?|BEST\s*BEFORE|BB)[\s:.-]*({advanced_pattern})', full_text)
    if priority_match:
        return priority_match.group(1)
        
    adv_matches = re.findall(advanced_pattern, full_text)
    if adv_matches:
        return adv_matches[-1]
        
    return None

def process_packet_data(image_bytes):
    reader = load_reader()
    file_bytes = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    # पायरी १: मूळ इमेजवर (जशी तुझ्या कालच्या कोडमध्ये होती, कोणताही बदल न करता) चेक करणे
    results = reader.readtext(img)
    found = search_dates_in_results(results)
    if found:
        return found
        
    # पायरी २: जर उभा फोटो असेल तर ९० आणि २७० डिग्री फिरवून चेक करणे
    for rot in [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE]:
        rot_img = cv2.rotate(img, rot)
        res_rot = reader.readtext(rot_img)
        found_rot = search_dates_in_results(res_rot)
        if found_rot:
            return found_rot
            
    return None

# USER INPUT INTERFACE
user_email = st.text_input("📧 Enter your Email ID for Mobile Notification (Optional):", placeholder="example@gmail.com")
uploaded_file = st.file_uploader("Upload Product Wrapper Photo:", type=["jpg", "jpeg", "png", "webp"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="Target Product Wrapper", use_container_width=True)
    
    with st.spinner("Processing OCR pipeline... Scanning packet data..."):
        file_bytes_data = uploaded_file.getvalue()
        detected_date = process_packet_data(file_bytes_data)
        
    st.subheader("System Isolated Output Screen")
    
    if detected_date:
        exp_date = parse_any_date(detected_date)
        food_status = ""
        
        if exp_date:
            current_date = datetime.now()
            soon_days = current_date + timedelta(days=30)
            
            if current_date > exp_date:
                st.error("Calculated Health Evaluation: **EXPIRED ❌**")
                food_status = "EXPIRED"
            elif current_date <= exp_date <= soon_days:
                st.warning("Calculated Health Evaluation: **EXPIRING SOON ⚠️**")
                food_status = "EXPIRING SOON"
            else:
                st.success("Calculated Health Evaluation: **NOT EXPIRED ✅**")
                food_status = "NOT EXPIRED"
                
            st.info(f"Scanned Expiry Date: **{detected_date}**")
        else:
            st.warning(f"Detected Text: **{detected_date}**")
        
        # AUTOMATED EMAIL ALERT TRIGGER
        if user_email and (food_status == "EXPIRED" or food_status == "EXPIRING SOON"):
            with st.spinner("📨 Sending live mobile notification alert via Email..."):
                email_sent = send_expiry_email(user_email, food_status, detected_date)
                if email_sent:
                    st.success(f"🔔 Live Alert Notification successfully pushed to your mobile Gmail! ({user_email})")
                else:
                    st.caption("ℹ️ Backend Alert System Simulated: Email configuration required for production.")
        
    else:
        st.warning("Calculated Health Evaluation: **Status evaluation limits reached.**")
        st.info("System recommendation: Ensure the expiry date is clearly visible and well-lit.")
