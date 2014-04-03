import web
import logging
import re
import datetime
import functools
from models import Thing

logger = logging.getLogger(__name__)

email_count = 0

def send_email(to_addr, message, cc=None, bcc=None):
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
    else:
        logger.info("{}: sending email to {} with subject {!r}".format(email_count, to_addr, subject))
        web.sendmail(web.config.from_address, to_addr, subject, message, cc=cc, bcc=bcc)

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
    def g(agent):
        key = f.__name__ + "/" + agent.email
        if not Thing.find(key):
            f(agent)
            Thing(key=key, type="email", sent_on=datetime.datetime.utcnow().isoformat()).save()
        else:
            logger.info("Already sent {} email to {}. Ignoring...".format(f.__name__, agent.email))
    return g

def limit_once_per_day(f):
    """Decorator to call the function at most once a day.
    """
    @functools.wraps(f)
    def g(agent):
        if not agent.email:
            return
        key = f.__name__ + "/" + agent.email
        t = Thing.find(key) or Thing(key=key, type="email", sent_on="2000-01-02T03:04:05")
        if parse_datetime(t.sent_on) < datetime.datetime.utcnow()-datetime.timedelta(days=1):
            f(agent)
            t.sent_on = datetime.datetime.utcnow().isoformat()
            t.save()
        else:
            logger.info("Already sent {} email to {} once today. Ignoring...".format(f.__name__, agent.email))
    return g

@limit_once
def sendmail_voterid_added(agent):
    from webapp import xrender
    if agent.role == "pb_agent":
        msg = xrender.email_agent_voterid_added(agent)
        place = agent.place
        ward = place.get_parent("WARD")
        ac = place.get_parent("AC")
        coordinators = (ward and ward.get_coordinators()) or ac.get_coordinators()
        cc = [c.email for c in coordinators]
        send_email(agent.email, msg, cc=cc)

@limit_once_per_day
def sendmail_voterid_pending(agent):
    from webapp import xrender
    if agent.role == "pb_agent":
        msg = xrender.email_agent_voterid_pending(agent)
        send_email(agent.email, msg)
