import web
import logging

logger = logging.getLogger(__name__)

def send_email(to_addr, message, bcc=None):
    subject = message.subject.strip()
    message = web.safestr(message)
    if web.config.debug:
        print "To: ", to_addr
        print "Subject: ", subject
        print
        print message
    else:
        logger.info("sending email to {} with subject {!r}".format(to_addr, subject))
        web.sendmail(web.config.from_address, to_addr, subject, message, bcc=bcc)
