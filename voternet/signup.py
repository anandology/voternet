import web
import os
from wtforms import Form, StringField, HiddenField, validators, ValidationError
from models import Place
import webapp
import utils
import logging

urls = (
    "/(.?.?)", "signup",
    "/unsubscribe", "unsubscribe",
    "/wards.js", "wards_js"
)
app = web.application(urls, globals())
path = os.path.join(os.path.dirname(__file__), "templates/signup")
render = web.template.render(path, base="site")
xrender = web.template.render(path)

db = None

@web.memoize
def get_db():
    return web.database(**web.config.db_parameters)

class MultiDict(web.storage):
    def getall(self, name):
        if name in self:
            return [self[name]]
        else:
            return []

class BaseForm(Form):
    def __init__(self, formdata=None, **kwargs):
        formdata = formdata and MultiDict(formdata)
        Form.__init__(self, formdata, **kwargs)

class SignupForm(BaseForm):
    name = StringField('Name', [validators.Required()])
    phone = StringField('Phone Number', [
        validators.Required(), 
        validators.Regexp(r'^\+?[0-9 -]{10,}$', message="That doesn't like a valid phone number.")])
    email = StringField('Email Address', [validators.Required(), validators.Email()])
    voterid = StringField('Voter ID')
    address = StringField('Locality', [validators.Required()])
    ward = HiddenField()

    def validate_address(self, field):
        if not self.ward.data:
            raise ValidationError("Please select a place from the dropdown.")
        place = Place.find(self.ward.data)
        if not place:
            raise ValidationError("Please select a place from the dropdown.")

class UnsubscribeForm(BaseForm):
    email = StringField('E-mail Address', [validators.Email(), validators.Required()])

class signup:
    def GET(self, source):
        form = SignupForm()
        return render.signup(form)

    def POST(self, source):
        i = web.input()
        form = SignupForm(i)
        if form.validate():
            notes = "signup"
            if source:
                notes = notes + " " + source
            place = Place.find(i.ward)
            agent = place.add_volunteer(
                name=i.name, 
                phone=i.phone,
                email=i.email,
                voterid=i.voterid,
                role='pb_agent',
                notes=notes)
            agent.populate_voterid_info()
            if agent.get_voterid_info():
                utils.sendmail_voterid_added(agent)
            else:
                utils.sendmail_voterid_pending(agent)
            return render.thankyou(place, agent)
        else:
            return render.signup(form)

class unsubscribe:
    def GET(self):
        form = UnsubscribeForm()
        return render.unsubscribe(form)

    def POST(self):
        i = web.input()
        form = UnsubscribeForm(i)
        if form.validate():
            db = get_db()
            if not db.where("unsubscribe", email=i.email):
                db.insert("unsubscribe", email=i.email)
            return render.unsubscribe(form, done=True)
        else:
            return render.unsubscribe(form)

class wards_js:
    def GET(self):
        accept_encoding = web.ctx.environ.get("HTTP_ACCEPT_ENCODING", "")
        if 'gzip' not in accept_encoding:
            raise web.seeother("/static/wards.js")
        web.header("Content-Encoding", "gzip")
        web.header("Content-Type", "application/x-javascript")
        oneyear = 365 * 24 * 3600
        web.header("Cache-Control", "Public, max-age=%d" % oneyear)
        return open("static/wards.js.gz")

def main():
    FORMAT = "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)

    webapp.check_config()
    if web.config.get('error_email_recipients'):
        app.internalerror = web.emailerrors(
            web.config.error_email_recipients,
            app.internalerror,
            web.config.get('from_address'))
    logger = logging.getLogger(__name__)
    logger.info("starting the signup app")
    app.run()

if __name__ == '__main__':
    main()
