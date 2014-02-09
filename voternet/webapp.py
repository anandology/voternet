import os
import sys
import markdown
import yaml
import web
import json

from models import Place
from forms import AddPeopleForm
import googlelogin
import account

urls = (
    "/", "index",
    "/login", "login",
    "/logout", "logout",
    "/login/oauth2callback", "oauth2callback",
    "/users", "users",
    "/([\w/]+)/delete", "delete_place",
    "/([\w/]+)/edit", "edit_place",
    "/([\w/]+)/info", "place_info",
    "/([\w/]+)/add-people", "add_people",
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


tglobals = {
    "input_class": input_class, 
    "plural": plural,
    "markdown": markdown.markdown,
    "sum": sum,
    "json_encode": json.dumps,
    "get_current_user": account.get_current_user,

    # iter to count from 1
    "counter": lambda: iter(range(1, 100000)),

}

path = os.path.join(os.path.dirname(__file__), "templates")
render = web.template.render(path, base="site", globals=tglobals)

class index:
    def GET(self):
        raise web.redirect("/karnataka")

class place:
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
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
    def GET(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        form = AddPeopleForm()
        return render.add_people(place, form)

    def POST(self, code):
        place = Place.find(code=code)
        if not place:
            raise web.notfound()
        elif not place.writable_by(account.get_current_user()):
            raise web.seeother(place.url)
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

        place.add_coverage(date, data)
        web.header("content-type", "application/json")
        return '{"result": "ok"}'

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

def main():
    if "--config" in sys.argv:
        index = sys.argv.index("--config")
        configfile = sys.argv[index+1]
        sys.argv = sys.argv[:index] + sys.argv[index+2:]
        web.config.update(yaml.load(open(configfile)))
    app.run()

if __name__ == "__main__":
    main()