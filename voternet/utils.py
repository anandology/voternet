import web
import logging
import re
import datetime
import functools
from models import Thing, get_db
import envelopes 
import urllib
import subprocess
import sys

logger = logging.getLogger(__name__)

email_count = 0

def get_smtp_conn():
    if web.config.debug:
        return None

    return envelopes.conn.SMTP(
        host=web.config.smtp_server, 
        port=web.config.smtp_port,
        tls=web.config.smtp_starttls,
        login=web.config.smtp_username,
        password=web.config.smtp_password)

def get_unsubscribes():
    return set(row.email for row in get_db().select("unsubscribe"))

def send_email(to_addr, message, cc=None, bcc=None, conn=None, subject=None):
    global email_count
    email_count += 1
    if subject is None:
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
        return True
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
            return True
        except Exception:
            logger.error("failed to send email to {}".format(to_addr), exc_info=True)
            return False
        #web.sendmail(web.config.from_address, to_addr, subject, message, cc=cc, bcc=bcc)

def sendmail_batch(batch, async=False):
    """Starts sending all messages in the given batch.

    If async is True, a new process will be created for sending messages.
    """
    if async:
        python = sys.executable
        args = [
            python, "voternet/utils.py",
            "--config", web.config.configfile,
            "sendmail-batch", str(batch.id)]
        p = subprocess.Popen(args)
        return p
    messages = batch.get_messages(status='pending')
    conn = get_smtp_conn()
    unsubscribes = get_unsubscribes()

    for m in messages:
        if m.to_address in unsubscribes:
            m.set_status('unsubscribed')
            continue

        message = batch.message.replace('{name}', m.name).replace('{email}', m.to_address or "")
        success = send_email(m.to_address, message=message, subject=batch.subject, conn=conn)
        if success:
            m.set_status('sent')
        else:
            m.set_status('failed')

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

def notify_signup(volunteer):
    from webapp import xrender
    msg = xrender.email_volunteer_signup(volunteer)
    place = volunteer.place
    ward = place.get_parent("WARD")
    ac = place.get_parent("AC")
    pc = place.get_parent("PC")
    coordinators = (ward and ward.get_coordinators() or []) + ac.get_coordinators() + pc.get_coordinators()
    cc = [c.email for c in coordinators]
    send_email(volunteer.email, msg, cc=cc)

    send_sms([volunteer], msg.message)

    name = volunteer.name
    phone = volunteer.phone
    booth = place.code.lstrip("PB0")
    ward = ward or ac
    message2 = "You have a new volunteer Name {} & Mob {} registered under {} booth of {} ward.".format(name, phone, booth, ward.name)
    send_sms(msg.coordinators, message2)

@limit_once_per_day
def sendmail_voterid_pending(agent, conn=None):
    unsubscribes = get_unsubscribes()

    from webapp import xrender
    if agent.role == "pb_agent":
        msg = xrender.email_agent_voterid_pending(agent)
        if agent.email in unsubscribes:
            logger.warn("Ignoring %s as he unsubscribed", agent.email)
        else:
            send_email(agent.email, msg, conn=conn)

def process_phone(number):
    if not number:
        return
    number = web.re_compile("[^0-9]").sub("", number)
    # remove +91
    if len(number) == 12 and number.startswith("91"):
        number = number[2:]
    return number

def send_sms(agents, message):
    if not web.config.get('sms_url'):
        print >> web.debug, "To: {}".format(",".join(a.phone for a in agents))
        print >> web.debug, message
        return

    unsubscribes = get_unsubscribes()
    phones = [process_phone(a.phone) for a in agents if a.email not in unsubscribes]
    phones = set(p for p in phones if p and len(p) == 10)
    for chunk in web.group(phones, 300):
        phone_numbers = ",".join(chunk)
        url = web.config.sms_url.format(
            phone_numbers=urllib.quote_plus(phone_numbers), 
            message=urllib.quote_plus(message))
        response = urllib.urlopen(url)
        logger.info("sms response\n%s", response.read())
    return len(phones)

def main():
    import webapp
    from models import SendMailBatch
    webapp.check_config()
    cmd = sys.argv[1]
    if cmd == "sendmail-batch":
        batch_id = sys.argv[2]
        batch = SendMailBatch.find(batch_id)
        if batch:
            sendmail_batch(batch)
        else:
            print >> sys.stderr, "unknown batch", batch_id
    else:
        print >> sys.stderr, "unknown command", cmd

if __name__ == '__main__':
    main()
