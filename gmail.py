import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Email credentials
EMAIL_ADDRESS = "0720293455enok@gmail.com"
EMAIL_PASSWORD = "ixkz kygv elcs slvg"  

# Email details
TO_EMAIL = "enckopmedia@gmail.com"
SUBJECT = "Hello"
BODY = "Hello Test,\n\nPlease find the attached link.\n\n https://meet.google.com/zhm-huxm-yea"

# File to attach
FILE_PATH = "enok_marendi.pdf"  #file path

# email message
msg = MIMEMultipart()
msg["From"] = EMAIL_ADDRESS
msg["To"] = TO_EMAIL
msg["Subject"] = SUBJECT
msg.attach(MIMEText(BODY, "plain"))

# Attach file logics
if os.path.exists(FILE_PATH):
    attachment = open(FILE_PATH, "rb")
    part = MIMEBase("application", "octet-stream")
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(FILE_PATH)}")
    msg.attach(part)
    attachment.close()
else:
    print(f"Error: File {FILE_PATH} not found!")

# Send email
try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.sendmail(EMAIL_ADDRESS, TO_EMAIL, msg.as_string())
    server.quit()
    print("✅ Email sent successfully!")
except Exception as e:
    print(f"❌ Error sending email: {e}")
