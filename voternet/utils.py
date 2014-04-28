import web
import logging
import re
import datetime
import functools
from models import Thing, get_db
import envelopes 
import urllib, urllib2

logger = logging.getLogger(__name__)

email_count = 0

def get_smtp_conn():
    return envelopes.conn.SMTP(
        host=web.config.smtp_server, 
        port=web.config.smtp_port,
        tls=web.config.smtp_starttls,
        login=web.config.smtp_username,
        password=web.config.smtp_password)

def get_unsubscribes():
    return set(row.email for row in get_db().select("unsubscribe"))

def send_email(to_addr, message, cc=None, bcc=None, conn=None):
    global email_count
    email_count += 1
    subject = message.subject.strip()
    message = web.safestr(message)
    cc = cc or []
    bcc = bcc or web.config.get("email_bcc_address") or []

    if web.config.debug:
        print "To: ", to_addr
        print "Subject: ", subject
        if cc:
            print "Cc: ", cc
        if bcc:
            print "Bcc: ", bcc
        print
        print message
    elif not web.config.get('smtp_server'):
        web.sendmail(
            from_address=web.config.from_address, 
            to_address=to_addr, 
            subject=subject, 
            message=message,
            cc=cc,
            bcc=bcc)
    else:
        logger.info("{}: sending email to {} with subject {!r}".format(email_count, to_addr, subject))
        envelope = envelopes.Envelope(    
            from_addr=web.config.from_address,
            to_addr=to_addr,
            subject=subject,
            text_body=message,
            cc_addr=cc,
            bcc_addr=bcc)
        conn = conn or get_smtp_conn()
        try:
            conn.send(envelope)
        except Exception:
            logger.error("failed to send email to {}".format(to_addr), exc_info=True)
        #web.sendmail(web.config.from_address, to_addr, subject, message, cc=cc, bcc=bcc)

def parse_datetime(value):
    """Creates datetime object from isoformat.

        >>> t = '2008-01-01T01:01:01.010101'
        >>> parse_datetime(t).isoformat()
        '2008-01-01T01:01:01.010101'
    """
    if isinstance(value, datetime.datetime):
        return value
    else:
        tokens = re.split('-|T|:|\.| ', value)
        return datetime.datetime(*map(int, tokens))        

def limit_once(f):
    """Decorator to call the function only once.
    """
    @functools.wraps(f)    
    def g(agent, *a, **kw):
        key = f.__name__ + "/" + agent.email
        if not Thing.find(key):
            f(agent, *a, **kw)
            Thing(key=key, type="email", sent_on=datetime.datetime.utcnow().isoformat()).save()
        else:
            logger.info("Already sent {} email to {}. Ignoring...".format(f.__name__, agent.email))
    return g

def limit_once_per_day(f):
    """Decorator to call the function at most once a day.
    """
    @functools.wraps(f)
    def g(agent, *a, **kw):
        if not agent.email:
            return
        key = f.__name__ + "/" + agent.email
        t = Thing.find(key) or Thing(key=key, type="email", sent_on="2000-01-02T03:04:05")
        if parse_datetime(t.sent_on) < datetime.datetime.utcnow()-datetime.timedelta(days=1):
            f(agent, *a, **kw)
            t.sent_on = datetime.datetime.utcnow().isoformat()
            t.save()
        else:
            logger.info("Already sent {} email to {} once today. Ignoring...".format(f.__name__, agent.email))
    return g

@limit_once
def sendmail_voterid_added(agent, conn=None):
    from webapp import xrender
    if agent.role == "pb_agent":
        msg = xrender.email_agent_voterid_added(agent)
        place = agent.place
        ward = place.get_parent("WARD")
        ac = place.get_parent("AC")
        coordinators = (ward and ward.get_coordinators()) or ac.get_coordinators()
        cc = [c.email for c in coordinators]
        send_email(agent.email, msg, cc=cc, conn=conn)

@limit_once_per_day
def sendmail_voterid_pending(agent, conn=None):
    unsubscribes = get_unsubscribes()

    from webapp import xrender
    if agent.role == "pb_agent":
        msg = xrender.email_agent_voterid_pending(agent)
        if agent.email in unsubscribes:
            logger.ward("Ignoring %s as he unsubscribed", agent.email)
        else:
            send_email(agent.email, msg, conn=conn)

lsp_email_template = """$def with (agent, coordinators)
Dear $agent.name,
$ ac = agent.place.get_ac()

Thank you for offering to be our polling day volunteer.

You have signed up with the following details:

Name: $agent.name
Phone: $agent.phone
Email: $agent.email
Voter ID: $agent.get('voterid', 'not provided')

$if agent.place.type == "PB":
    Based on your voterid, you are assigned to
    $agent.place.name booth
    in $ac.name assembly constituency.
$else:
    Based on your locality, you are assigned to
    $ac.name assembly constituency.
$""
Our coordinators from this constituency are:

  $for c in coordinators:
      $c.name
      $c.phone
      $c.email

They will contact you shortly. Please feel free to reach out to them so you can immediately get included in the team.

Thank you
Loksatta Team
"""

@limit_once
def lsp_sendmail(agent):
    url = "https://win.loksatta.org/agentemail"
    place = agent.place.get_ac()

    def process_person(p):
        name = p.name.strip("*")
        return web.storage(name=name, email=p.email, phone=p.phone)

    coordinators = [process_person(p) for p in place.get_coordinators() if p.name.endswith("*")]
    coordinator_emails = ", ".join("{} <{}>".format(p.name, p.email) for p in coordinators if p.email)

    t = web.template.Template(lsp_email_template)
    msg = web.safestr(t(agent, coordinators))

    params = {
        "secret_token": web.config.lsp_email_secret_key,
        "from": "Loksatta Party <info@loksattaparty.com>",
        "to": agent.email,
        "cc": coordinator_emails,
        "reply_to": coordinator_emails, 
        "subject": "Thank you for signup of as polling day volunteer",
        "message": msg
    }
    if web.config.get("lsp_email_bcc"):
        params['bcc'] = web.config.lsp_email_bcc

    print "sending email to", agent.email
    x = urllib2.urlopen(url, urllib.urlencode(params)).read()
    with open("/tmp/a.html", "w") as f:
        f.write(x)

def process_phone(number):
    if not number:
        return
    number = web.re_compile("[^0-9]").sub("", number)
    # remove +91
    if len(number) == 12 and number.startswith("91"):
        number = number[2:]
    return number

def send_sms(agents, message):
    phones = [process_phone(a.phone) for a in agents]
    phones = set(p for p in phones if p and len(p) == 10)
    for chunk in web.group(phones, 300):
        phone_numbers = ",".join(chunk)
        url = web.config.sms_url.format(
            phone_numbers=urllib.quote_plus(phone_numbers), 
            message=urllib.quote_plus(message))
        response = urllib.urlopen(url)
        logger.info("sms response\n%s", response.read())
    return len(phones)