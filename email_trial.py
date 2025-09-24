import smtplib, ssl, email.message, email.utils
from dotenv import load_dotenv, dotenv_values
from os import getenv



def asserted_env(key: str) -> str:
	value = getenv(key)
	assert value

	return value

load_dotenv()
# TODO RENAME CONSTANT SSL_PORT
EML_SSL_PORT = int(asserted_env("EML_SSL_PORT")) # SSL port is 465, TLS = 587. USING SSL flagged as policy restriction (thinks spam)
SMTP_SERV = asserted_env("SMTP_SERV")
EML_PASS = asserted_env("EML_PASS")
EML = asserted_env("EML")

test_send_to = asserted_env("TEST_SEND_TO")

context = ssl.create_default_context()

CONFIG = dotenv_values(".config")

msg = email.message.EmailMessage()
msg["From"] = email.utils.formataddr((CONFIG["EML_FRIENDLY_NAME"], EML)) # (Display Name, Email)
msg["To"] = test_send_to
msg["Subject"] = "Test Subject"
msg.set_content("Hello there, this was sent from python")
msg.add_alternative("""\
<!DOCTYPE html>
<html>
  <body style="font-family: Arial, sans-serif; margin:0; padding:1em;">
    <h1 style="color: #333;">Hello there 👋</h1>
    <p>This is an <b>HTML email</b> sent from Python.</p>
    <p style="font-size: 14px; color: #555;">
      It even supports <a href="https://example.com">links</a>!
    </p>
  </body>
</html>
""", subtype="html")


with smtplib.SMTP(SMTP_SERV, 587) as server:
	server.ehlo() # can be omitted, what is this?
	server.starttls(context = context)
	server.ehlo() # ..
	
	server.login(EML, EML_PASS)
	server.send_message(msg)

	# PLAIN TEXT
	#server.sendmail(EML, test_send_to, """\
#Subject: Test Subject

#Hello there, this was sent from python.""")

print("all done, left with clause.")

#with smtplib.SMTP_SSL(SMTP_SERV, EML_SSL_PORT, context = context) as server:
#	