import web
import logging

logger = logging.getLogger(__name__)

def send_email(to_addr, message, cc=None, bcc=None):
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
        logger.info("sending email to {} with subject {!r}".format(to_addr, subject))
        web.sendmail(web.config.from_address, to_addr, subject, message, cc=cc, bcc=bcc)
