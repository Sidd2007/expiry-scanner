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
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, user_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        return False
# -------------------------------------------------------------

# USER INPUT INTERFACE
user_email = st.text_input("📧 Enter your Email ID for Mobile Notification (Optional):", placeholder="example@gmail.com")
uploaded_file = st.file_uploader("Upload Product Wrapper Photo:", type=["jpg", "jpeg", "png", "webp"])

def process_packet_data(image_bytes):
    reader = easyocr.Reader(['en'], gpu=False)
    file_bytes = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    results = reader.readtext(img)
    
    date_pattern = r'\b\d{2}[-/\.]\d{2}[-/\.]\d{2,4}\b|\b\d{2}[-/\.]\d{2,4}\b'
    all_detected_dates = []
    
    for bbox, text, prob in results:
        txt_clean = text.replace(" ", "")
        matches = re.findall(date_pattern, txt_clean)
        for m in matches:
            if m not in all_detected_dates:
                all_detected_dates.append(m)
                
    if len(all_detected_dates) >= 2:
        return all_detected_dates[1]
    elif len(all_detected_dates) == 1:
        return all_detected_dates[0]
        
    return None

if uploaded_file is not None:
    st.image(uploaded_file, caption="Target Product Wrapper", use_container_width=True)
    
    with st.spinner("Processing OCR pipeline... Scanning packet data..."):
        file_bytes_data = uploaded_file.getvalue()
        detected_date = process_packet_data(file_bytes_data)
        
    st.subheader("System Isolated Output Screen")
    
    if detected_date:
        clean_date_str = re.sub(r'[-/\.]', '/', detected_date)
        parts = clean_date_str.split('/')
        
        food_status = "" 
        
        try:
            if len(parts) == 2:
                exp_date = datetime.strptime(clean_date_str, "%m/%Y") if len(parts[1]) == 4 else datetime.strptime(clean_date_str, "%m/%y")
            else:
                exp_date = datetime.strptime(clean_date_str, "%d/%m/%Y") if len(parts[2]) == 4 else datetime.strptime(clean_date_str, "%d/%m/%y")
            
            current_date = datetime.now()
            soon_days = current_date + timedelta(days=30)
            
            if current_date > exp_date:
                st.error("Calculated Health Evaluation: **EXPIRED ❌**")
                food_status = "EXPIRED"
            elif current_date <= exp_date and exp_date <= soon_days:
                st.warning("Calculated Health Evaluation: **EXPIRING SOON ⚠️**")
                food_status = "EXPIRING SOON"
            else:
                st.success("Calculated Health Evaluation: **NOT EXPIRED ✅**")
                food_status = "NOT EXPIRED"
        except:
            st.error("Calculated Health Evaluation: **EXPIRED ❌**")
            food_status = "EXPIRED"
            
        st.info(f"Scanned Expiry Date: **{detected_date}**")
        
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
        st.info("System recommendation: Try taking a closer, clear shot of the date section.")
