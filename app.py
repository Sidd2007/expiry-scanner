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
st.write("Upload a full product photo — works with cropped, uncropped, rotated, and all date formats!")

# EasyOCR मॉडेल कॅश करणे (जेणेकरून Streamlit सर्व्हर क्रॅश होणार नाही)
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

# अंक (02, 03), महिन्यांची नावे (FEB, FEBRUARY, MARCH) आणि सलग तारीख (120924) ओळखणारे फंक्शन
def parse_any_date(date_str):
    date_str = date_str.upper().strip()
    
    # जर स्लॅश नसलेली सलग ६ किंवा ८ अंकी तारीख असेल (उदा. 120924 किंवा 12092024)
    if date_str.isdigit():
        if len(date_str) == 6:
            try:
                return datetime.strptime(date_str, "%d%m%y")
            except ValueError:
                pass
        elif len(date_str) == 8:
            try:
                return datetime.strptime(date_str, "%d%m%Y")
            except ValueError:
                pass

    # तारखेतील -, /, . काढून स्पेस टाकणे
    date_str = re.sub(r'[-/\.]', ' ', date_str)
    # जर '21FEB2027' असं सलग चिकटून आलं असेल तर अंक आणि अक्षरांमध्ये स्पेस टाकणे
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

# सरळ, पूर्ण आणि उभा (Rotated) सर्व प्रकारचे फोटो वाचणारे फंक्शन
def process_packet_data(image_bytes):
    reader = load_reader()
    file_bytes = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    
    # १. पूर्ण फोटोतील लहान अक्षरे स्पष्ट वाचण्यासाठी Image Upscaling
    height, width = img.shape[:2]
    if width < 1200:
        scale = 1200 / width
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # २. अक्षरांचा कॉन्ट्रास्ट वाढवणे (CLAHE टेक्निक)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced_img = clahe.apply(gray)
    
    # ३. सर्व प्रकारच्या तारखांचा पॅटर्न (महिन्याचे नाव, स्लॅश असलेली तारीख आणि सलग ६-८ अंकी तारीख)
    month_names = r'(?:JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|JUL(?:Y)?|AUG(?:UST)?|SEP(?:TEMBER)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)'
    date_pattern = rf'\b(?:\d{{1,2}}[-/\s]*)?{month_names}[-/\s]*\d{{2,4}}\b|\b\d{{1,2}}[-/]\d{{1,2}}[-/]\d{{2,4}}\b|\b\d{{1,2}}[-/]\d{{2,4}}\b|\b(?:0[1-9]|[12]\d|3[01])(?:0[1-9]|1[0-2])\d{{2,4}}\b'

    # ४. फोटो सरळ तसेच ९० आणि २७० डिग्री फिरवून चेक करणे (उभ्या अक्षरांसाठी)
    rotations = [
        enhanced_img,
        cv2.rotate(enhanced_img, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(enhanced_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    ]
    
    for current_img in rotations:
        results = reader.readtext(current_img)
        full_text = " ".join([text for (_, text, _) in results]).upper()
        
        # आधी 'USE BY', 'EXP', 'BEST BEFORE' कीवर्डच्या जवळची तारीख शोधणे
        priority_match = re.search(rf'(?:USE\s*BY|EXP(?:IRY)?|BEST\s*BEFORE|BB)[\s:.-]*({date_pattern})', full_text)
        if priority_match:
            return priority_match.group(1)
            
        # कीवर्ड न सापडल्यास सापडलेल्या सर्व तारखांमधून शेवटची तारीख (जी सहसा Expiry असते) घेणे
        all_matches = re.findall(date_pattern, full_text)
        if all_matches:
            return all_matches[-1]
            
    return None

# USER INPUT INTERFACE
user_email = st.text_input("📧 Enter your Email ID for Mobile Notification (Optional):", placeholder="example@gmail.com")
uploaded_file = st.file_uploader("Upload Product Wrapper Photo:", type=["jpg", "jpeg", "png", "webp"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="Uploaded Product Image", use_container_width=True)
    
    with st.spinner("Scanning full packet... Detecting expiry date..."):
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
            st.warning(f"Detected Text: **{detected_date}** (Could not verify exact date format)")
        
        # AUTOMATED EMAIL ALERT TRIGGER
        if user_email and (food_status == "EXPIRED" or food_status == "EXPIRING SOON"):
            with st.spinner("📨 Sending live mobile notification alert via Email..."):
                email_sent = send_expiry_email(user_email, food_status, detected_date)
                if email_sent:
                    st.success(f"🔔 Live Alert Notification successfully pushed to your mobile Gmail! ({user_email})")
                else:
                    st.caption("ℹ️ Backend Alert System Simulated: Email configuration required for production.")
        
    else:
        st.warning("Calculated Health Evaluation: **Could not detect a clear expiry date.**")
        st.info("System recommendation: Ensure the 'Use By' or 'Expiry Date' area on the packet is clearly visible and well-lit.")
