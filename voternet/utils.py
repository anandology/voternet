import web

def send_email(to_addr, message):
    subject = message.subject.strip()
    message = web.safestr(message)
    if web.config.debug:
        print "To: ", to_addr
        print "Subject: ", subject
        print
        print message
    else:
        web.sendmail(web.config.from_address, to_addr, subject, message)
