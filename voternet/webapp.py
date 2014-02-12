import os
import sys
import markdown
import yaml
import web
import json
import functools

from models import Place, Person
from forms import AddPeopleForm
import googlelogin
import account

urls = (
    "/", "index",
    "/login", "login",
    "/logout", "logout",
    "/login/oauth2callback", "oauth2callback",
    "/sudo", "sudo",
    "/users", "users",
    "/debug", "debug",
    "/([\w/]+)/delete", "delete_place",
    "/([\w/]+)/edit", "edit_place",
    "/([\w/]+)/info", "place_info",
    "/([\w/]+)/add-people", "add_people",
    "/([\w/]+)/people/(\d+)", "edit_person",
    "/([\w/]+)/links", "links",
    "/([\w/]+)", "place",
    "/(AC\d+/PB\d+)/(\d\d\d\d-\d\d-\d\d)", "coverage",
)

app = web.application(urls, globals())

def login_requrired(handler):
    if not web.ctx.path.startswith("/login") and web.ctx.path != "/logout":
        user = account.get_current_user()
        if not user:
            raise web.seeother("/login")
        elif not user.is_authorized():
            return render.permission_denied()
    return handler()

app.add_processor(login_requrired)

def placify(f=None, roles=None):
    """Decorator that converts the first argument from place code to place.
    Also makes sure if the current user has the specified permission.
    """
    if not f:
        return lambda f: placify(f=f, roles=roles)

    @functools.wraps(f)
    def g(self, code, *args):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()

        if roles:
            user = account.get_current_user()
            if not user or not place.writable_by(user, roles=roles):
                return render.permission_denied(user=user)
        return f(self, place, *args)
    return g

def input_class(input):
    if input.note:
        return "has-error"
    else:
        return ""

def plural(name):
    if name.endswith("y"):
        return name[:-1] + "ies"
    else:
        return name + 's'

def limitname(s, length=50):
    if len(s) > length:
        # show ... and last 5 characters and limit the total length
        # by slicing at the beginning
        return s[:length-8] + "..." + s[-5:]
    else:
        return s

def render_option(value, label, select_value):
    if value == select_value:
        return '<option value="%s" selected>%s</option>' % (value, label)
    else:
        return '<option value="%s">%s</option>' % (value, label)

tglobals = {
    "input_class": input_class, 
    "plural": plural,
    "markdown": markdown.markdown,
    "sum": sum,
    "json_encode": json.dumps,
    "get_current_user": account.get_current_user,
    "limitname": limitname,
    "render_option": render_option,

    # iter to count from 1
    "counter": lambda: iter(range(1, 100000)),
}

path = os.path.join(os.path.dirname(__file__), "templates")
render = web.template.render(path, base="site", globals=tglobals)

class index:
    def GET(self):
        raise web.redirect("/karnataka")

class place:
    @placify
    def GET(self, place):
        return render.place(place)

class delete_place:
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        return render.delete_place(place)

    def POST(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        elif not place.writable_by(account.get_current_user(), roles=['admin']):
            # only admins can delete places
            raise web.seeother(place.url)

        i = web.input(action=None)
        if i.action == "cancel":
            raise web.seeother(place.url)
        else:
            parent = place.parent
            place.delete()
            raise web.seeother(parent.url)

class edit_place:
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        return render.edit_place(place)

    def POST(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        elif not place.writable_by(account.get_current_user(), roles=['admin']):
            # only admins can edit places
            raise web.seeother("/users")
        i = web.input(places="")
        place.add_places(i.places)
        raise web.seeother(place.url)

class place_info:
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        i = web.input(m=None)
        if i.m == "edit":
            return render.edit_info(place)
        else:
            return render.place_info(place)

    def POST(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        i = web.input(info="")
        place.update_info(i.info)
        raise web.seeother(place.url + "/info")

class add_people:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        form = AddPeopleForm()
        return render.add_people(place, form)

    @placify(roles=['admin', 'coordinator'])
    def POST(self, place):
        i = web.input()
        form = AddPeopleForm()
        if form.validates(i):
            place.add_volunteer(i.name.strip(), i.email.strip(), i.phone.strip(), i.voterid.strip(), i.role.strip())
            raise web.seeother(place.url)
        else:
            return render.add_people(place, form)

class users:
    def GET(self):
        i = web.input(action="")
        place = Place.find(code="karnataka")

        form = AddPeopleForm()
        if i.action == "add":
            return render.add_people(place, form, add_users=True)
        else:
            roles = ['admin', 'user']
            users = place.get_people(roles)
            return render.users(place, users)

    def POST(self):
        place = Place.find(code="karnataka")
        if not place:
            raise web.notfound()
        elif not place.writable_by(account.get_current_user()):
            raise web.seeother("/users")

        i = web.input()
        form = AddPeopleForm()
        if form.validates(i):
            place.add_volunteer(i.name.strip(), i.email.strip(), i.phone.strip(), i.voterid.strip(), i.role.strip())
            raise web.redirect("/users")
        else:
            return render.add_people(place, form, add_users=True)

class edit_person:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place, id):
        person = Person.find(place_id=place.id, id=id)
        if not person:
            raise web.notfound()
        form = AddPeopleForm()
        form.fill(person)
        return render.person(person, form)

    @placify(roles=['admin', 'coordinator'])
    def POST(self, place, id):
        person = Person.find(place_id=place.id, id=id)
        if not person:
            raise web.notfound()

        i = web.input()
        if i.action == "save":
            person.update(dict(name=i.name, email=i.email, phone=i.phone, voterid=i.voterid, role=i.role))
        elif i.action == "delete":
            person.delete()
        raise web.seeother(place.url)

class coverage:
    def GET(self, code, date):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()

        user = account.get_current_user()
        if not place.writable_by(user, roles=['coordinator', 'volunteer', 'admin']):
            raise web.seeother(place.url)

        return render.coverage(place, date)

    def POST(self, code, date):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()

        user = account.get_current_user()
        if not place.writable_by(user, roles=['coordinator', 'volunteer', 'admin']):
            raise web.seeother(place.url)

        data = json.loads(web.data())['data']

        # skip empty rows
        data = [row for row in data if any(row)]

        place.add_coverage(date, data, account.get_current_user())
        web.header("content-type", "application/json")
        return '{"result": "ok"}'

class links:
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        user = account.get_current_user()
        if not place.writable_by(user, roles=['coordinator', 'admin']):
            raise web.seeother(place.url)
        return render.links(place)

    def POST(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        user = account.get_current_user()
        if not place.writable_by(user, roles=['coordinator', 'admin']):
            raise web.seeother(place.url)

        links = json.loads(web.data())['data']
        links = [link for link in links if link.get('url')]
        place.save_links(links)
        return '{"result": "ok"}'

class sudo:
    def GET(self):
        user = account.get_current_user()
        if not user or user.role != 'admin':
            return render.permission_denied()

        i = web.input(email=None)
        if i.email:
            account.set_login_cookie(i.email)
        raise web.seeother("/")

class debug:
    def GET(self):
        i = web.input(fail=None)
        if i.fail:
            raise Exception('failed')
        return "hello world!"

class login:
    def GET(self):
        google = googlelogin.GoogleLogin()
        return render.login(google.get_redirect_url())

class logout:
    def POST(self):
        account.logout()
        raise web.seeother("/")


class oauth2callback:
    def GET(self):
        i = web.input(code=None, error=None, state=None)
        if i.code:
            google = googlelogin.GoogleLogin()
            token = google.get_token(i.code)
            userinfo = google.get_userinfo(token.access_token)
            if userinfo:
                account.set_login_cookie(userinfo.email)
        raise web.seeother("/")

def load_config(configfile):
    web.config.update(yaml.load(open(configfile)))

def main():
    if "--config" in sys.argv:
        index = sys.argv.index("--config")
        configfile = sys.argv[index+1]
        sys.argv = sys.argv[:index] + sys.argv[index+2:]
        load_config(configfile)

    if web.config.get('error_email_recipients'):
        app.internalerror = web.emailerrors(
            web.config.error_email_recipients, 
            app.internalerror, 
            web.config.get('from_address'))

    app.run()

if __name__ == "__main__":
    main()