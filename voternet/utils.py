import web

def send_email(to_addr, message):
    if web.config.debug:
        print "To: ", to_addr
        print "Subject: ", message.subject
        print
        print message
    else:
        web.sendmail(web.config.from_address, to_addr, message.subject, web.safestr(message))
