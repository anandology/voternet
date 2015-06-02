import random
import hmac
import web
import datetime, time
import models

def get_secret_key():
    return web.config.secret_key

def generate_salted_hash(text, salt=None, separator='$'):
    secret_key = get_secret_key()
    salt = salt or hmac.HMAC(secret_key, str(random.random())).hexdigest()[:5]
    hash = hmac.HMAC(secret_key, web.utf8(salt) + web.utf8(text)).hexdigest()
    return '%s%s%s' % (salt, separator, hash)

def check_salted_hash(text, salted_hash, separator='$'):
    if salted_hash and separator in salted_hash:
        salt, hash = salted_hash.split(separator, 1)
        return generate_salted_hash(text, salt) == salted_hash
    else:
        return False

def set_login_cookie(email):
    t = datetime.datetime(*time.gmtime()[:6]).isoformat()
    text = "%s,%s" % (email, t)
    text += "," + generate_salted_hash(text)
    web.setcookie("session", text)

def logout():
    web.setcookie("session", "", expires=-1)

def get_current_user():
    if "current_user" not in web.ctx:
        web.ctx.current_user = _get_current_user()
    return web.ctx.current_user

def _get_current_user():   
    session = web.cookies(session="").session
    try:
        email, login_time, digest = session.split(',')
    except ValueError:
        return
    if check_salted_hash(email + "," + login_time, digest):
        return models.Person.find(email=email) or models.DummyPerson(email)

def login(user, password):
    if check_salted_hash(password, user.get_encrypted_password()):
        set_login_cookie(user.email)
        return True

def set_password(user, password):
    user.set_encrypted_password(generate_salted_hash(password))

def user2token(user):
    """Token contains 4 parts.

    userid, timestamp, salt, hash
    """
    return _hash_userid(user.id)

def _hash_userid(userid, timestamp=None, salt=None):
    t = timestamp or int(time.time())
    message = "{:x}-{:x}".format(userid, t)
    h = generate_salted_hash(message, salt=salt, separator='-')
    return "{}-{}".format(message, h)

def token2user(token):
    useridx, tx, salt, digest = token.split("-")
    userid = int(useridx, 16)
    t = int(tx, 16)
    tnow = int(time.time())

    # Token is valid only for 1 hour
    if tnow - t > 3600:
        return None

    if _hash_userid(userid, timestamp=t, salt=salt) == token:
        return models.Person.find(id=userid)
