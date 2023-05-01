import imaplib
import base64
import email
import urllib
import urllib.request
import json
import time
import datetime
from bs4 import BeautifulSoup

# This script fetches the last few days of emails, extracts a relatively cleanish plaintext body from each,
# and writes them into files in the emails/ directory (which had better exist!)
# Reads various files from the sensitive/ directory.

DAYS_AGO_TO_FETCH_BACK_TO = 5

# The URL root for accessing Google Accounts.
GOOGLE_ACCOUNTS_BASE_URL = 'https://accounts.google.com'

def AccountsUrl(command):
  return '%s/%s' % (GOOGLE_ACCOUNTS_BASE_URL, command)

def RefreshToken(client_id, client_secret, refresh_token):
  """Obtains a new token given a refresh token.

  See https://developers.google.com/accounts/docs/OAuth2InstalledApp#refresh

  Args:
    client_id: Client ID obtained by registering your app.
    client_secret: Client secret obtained by registering your app.
    refresh_token: A previously-obtained refresh token.
  Returns:
    The decoded response from the Google Accounts server, as a dict. Expected
    fields include 'access_token', 'expires_in', and 'refresh_token'.
  """
  params = {}
  params['client_id'] = client_id
  params['client_secret'] = client_secret
  params['refresh_token'] = refresh_token
  params['grant_type'] = 'refresh_token'
  request_url = AccountsUrl('o/oauth2/token')

  response = urllib.request.urlopen(request_url, urllib.parse.urlencode(params).encode("utf-8")).read()
  return json.loads(response)


def GenerateOAuth2String(username, access_token, base64_encode=False):
  """Generates an IMAP OAuth2 authentication string.

  See https://developers.google.com/google-apps/gmail/oauth2_overview

  Args:
    username: the username (email address) of the account to authenticate
    access_token: An OAuth2 access token.
    base64_encode: Whether to base64-encode the output.

  Returns:
    The SASL argument for the OAuth2 mechanism.
  """
  auth_string = 'user=%s\1auth=Bearer %s\1\1' % (username, access_token)
  if base64_encode:
    auth_string = base64.b64encode(auth_string)
  return auth_string



def dropEmailThreadHistory(body):
  on_ind = body.find('On ')
  if on_ind == -1:
    return body
  while on_ind != -1:
    atsym_ind = body.find('@', on_ind)
    if atsym_ind == -1:
      return body
    if atsym_ind > on_ind + 120:
      on_ind = body.find('On ', on_ind + 3)
      continue
    comma_count = 0
    for i in range(on_ind+3, atsym_ind):
      if body[i] == ',':
        comma_count += 1
    if comma_count < 2:
      on_ind = body.find('On ', on_ind + 3)
      continue
    wrote_ind = body.find('wrote:', atsym_ind)
    if wrote_ind == -1:
      return body
    if wrote_ind > atsym_ind + 100:
      on_ind = body.find('On ', on_ind + 3)
      continue
    return body[:on_ind]

def dropHugeCharacterBlobs(body):
  cur_ind = 0
  last_good_ind = 0
  body_len = len(body)
  new_body = ''
  while cur_ind != -1:
    new_ind = body.find(' ', cur_ind+1)
    if new_ind - cur_ind > 40 or (new_ind == -1 and body_len - cur_ind > 40):
      new_body += body[last_good_ind:cur_ind]
      last_good_ind = new_ind
    cur_ind = new_ind
  new_body += body[last_good_ind:]
  return new_body


imap_conn = imaplib.IMAP4_SSL('imap.gmail.com')
imap_conn.debug = 0 #4

access_token = ''
try:
  with open('/tmp/llamiku_last_gmail_access_token.txt', 'r') as file:
    access_token = file.read().strip()
except:
  with open('/tmp/llamiku_last_gmail_access_token.txt', 'w') as file:
    file.write('none')

with open('sensitive/emailaddr.txt', 'r') as file:
  SECRET_emailaddr = file.read().strip()

with open('sensitive/client_secret.txt', 'r') as file:
  SECRET_client_secret = file.read().strip()

with open('sensitive/refreshtoken.txt', 'r') as file:
  SECRET_refreshtoken = file.read().strip()

with open('sensitive/app_url.txt', 'r') as file:
  SECRET_app_url = file.read().strip()

oauth2_string = GenerateOAuth2String(SECRET_emailaddr, access_token)

authd = False
try:
  imap_conn.authenticate('XOAUTH2', lambda x: oauth2_string)
  authd = True
except:
  response = RefreshToken(SECRET_app_url, SECRET_client_secret, SECRET_refreshtoken)
  access_token = response['access_token']

if not authd:
  oauth2_string = GenerateOAuth2String(SECRET_emailaddr, access_token)
  imap_conn.authenticate('XOAUTH2', lambda x: oauth2_string)
  with open('/tmp/llamiku_last_gmail_access_token.txt', 'w') as file:
    file.write(access_token)

# Select only emails marked with the 'p' label. This is just a random custom label
# I defined a gmail filter rule to mark all new primary tab messages with, as a way
# to expose gmail's primary tab categorization magic to IMAP.
imap_conn.select('p') # INBOX
#typ, data = imap_conn.search(None, 'ALL')
datesince = (datetime.date.today() - datetime.timedelta(days=DAYS_AGO_TO_FETCH_BACK_TO)).strftime("%d-%b-%Y")
typ, data = imap_conn.search(None, '(ALL)', f'(SENTSINCE {datesince})')

# at this point, print(data) looks like [b'1 2 3 4 5 6 7 8 9 10 11 12 13']

sanity_count = 0
for cur_email_id in data[0].split():
  typ, data = imap_conn.fetch(cur_email_id, '(RFC822)')
  if typ is None or data is None:
    break

  msg_encoding = 'utf-8'
  message = email.message_from_string(data[0][1].decode(msg_encoding))

  if message.is_multipart() == False:
    #single = bytearray(message.get_payload(), msg_encoding)
    #body = single.decode(encoding = msg_encoding)
    body = message.get_payload()
  else:
    body = ''
    for part in message.walk():
      if part.get_content_type() == 'text/plain':
        body = body + part.get_payload()
      elif part.get_content_type() == 'text/html':
        soup = BeautifulSoup(part.get_payload(), features='html.parser')
        # kill all script and style elements
        for script in soup(["script", "style"]):
          script.extract()    # rip it out
        text = soup.get_text()
        # break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        body += text

  body = body.replace('=', ' ')
  body = body.replace('\n', ' ')
  body = ' '.join(body.split())
  body = dropHugeCharacterBlobs(dropEmailThreadHistory(body)).strip()


  DEBUGGING_PRINT_ONLY = False
  if DEBUGGING_PRINT_ONLY:
    print("\n\n")
    print(str(cur_email_id))
    from_addr = message['From']
    from_addr = from_addr[from_addr.find('<')+1 : from_addr.find('>')]
    print("From: " + from_addr)
    print("Subject: " + message['Subject'])
    print(body)
  else:
    ms_since_epoch = time.time_ns() // 1000000
    ofile_name = str(ms_since_epoch) + '.txt'
    with open('emails/'+ofile_name, 'w') as file:
      file.write(body)

  sanity_count = sanity_count + 1
  if sanity_count > 50:
    break

imap_conn.close()
imap_conn.logout()
