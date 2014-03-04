import os
import sys
import markdown
import yaml
import web
import json
import functools
import datetime
from cStringIO import StringIO
import pytz

from models import Place, Person, get_all_coordinators_as_dataset
from forms import AddPeopleForm
import googlelogin
import account
import search

urls = (
    "/", "index",
    "/login", "login",
    "/logout", "logout",
    "/login/oauth2callback", "oauth2callback",
    "/sudo", "sudo",
    "/users", "users",
    "/debug", "debug",
    "/search", "do_search",    
    "/download/(.*)", "download",
    "/([\w/]+)/delete", "delete_place",
    "/([\w/]+)/edit", "edit_place",
    "/([\w/]+)/info", "place_info",
    "/([\w/]+)/booths", "pb_list",
    "/([\w/]+)/groups", "pb_groups",
    "/([\w/]+)/regions", "regions",
    "/([\w/]+)/add-people", "add_people",
    "/([\w/]+)/people/(\d+)", "edit_person",
    "/([\w/]+)/links", "links",
    "/([\w/]+)/coordinators.xls", "download_coordinators",
    "/([\w/]+)/activity", "activity",
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
        place = Place.find(key=code)
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

def limitname(s, length=50, suffixlength=5):
    if len(s) > length:
        # show ... and last 5 characters and limit the total length
        # by slicing at the beginning
        return s[:length-suffixlength-3] + "..." + s[-suffixlength:]
    else:
        return s

def render_option(value, label, select_value):
    if value == select_value:
        return '<option value="%s" selected>%s</option>' % (value, label)
    else:
        return '<option value="%s">%s</option>' % (value, label)

def get_timezone():
    return pytz.timezone(web.config.get("timezone", "UTC"))

def get_today():
    return datetime.datetime.now(get_timezone()).today()

def get_yesterday():
    return get_today() - datetime.timedelta(days=1)

def render_template(name, *args, **kwargs):
    t = getattr(xrender, name)
    return t(*args, **kwargs)

tglobals = {
    "str": str,
    "input_class": input_class, 
    "plural": plural,
    "markdown": markdown.markdown,
    "sum": sum,
    "json_encode": json.dumps,
    "get_current_user": account.get_current_user,
    "limitname": limitname,
    "render_option": render_option,
    "render_template": render_template,
    "config": web.config,
    "datestr": web.datestr,
    "commify": web.commify,
    "config": web.config,
    "get_site_title": lambda: web.config.get("site_title", "Your Favorite Party"),
    "get_today": get_today,
    "get_yesterday": get_yesterday,

    # iter to count from 1
    "counter": lambda: iter(range(1, 100000)),
}

path = os.path.join(os.path.dirname(__file__), "templates")
render = web.template.render(path, base="site", globals=tglobals)
xrender = web.template.render(path, globals=tglobals)

def get_state():
    return web.config.get("state", "karnataka")

class index:
    def GET(self):
        place = Place.find(key=get_state())
        raise web.seeother(place.url)

class place:
    @placify
    def GET(self, place):
        return render.place(place)

class delete_place:
    def GET(self, key):
        place = Place.find(key=key)
        if not place:
            raise web.notfound()
        return render.delete_place(place)

    def POST(self, code):
        place = Place.find(key=code)
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
        place = Place.find(key=code)
        if not place:
            raise web.notfound()
        return render.edit_place(place)

    def POST(self, code):
        place = Place.find(key=code)
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
        place = Place.find(key=code)
        if not place:
            raise web.notfound()
        i = web.input(m=None)
        if i.m == "edit":
            return render.edit_info(place)
        else:
            return render.place_info(place)

    def POST(self, code):
        place = Place.find(key=code)
        if not place:
            raise web.notfound()
        i = web.input(info="")
        place.update_info(i.info)
        raise web.seeother(place.url + "/info")

class pb_list:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        if place.type != "AC":
            raise web.notfound()
        return render.pb_list(place)

    @placify(roles=['admin', 'coordinator'])
    def POST(self, place):
        data = json.loads(web.data())['data']

        for row in data:
            code = place.code + "/" + row['code']
            pb = Place.find(code)

            if row['ward'] and row['ward'].strip():
                # Extract te group code from its name
                code = place.code + "/" + row['ward'].split("-")[0].strip()
                ward = Place.find(code)
                if pb.ward_id != ward.id:
                    pb.set_ward(ward)
            else:
                pb.set_ward(None)
        web.header("content-type", "application/json")
        return '{"result": "ok"}'

class pb_groups:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        if place.type != "AC":
            raise web.notfound()
        return render.pb_groups(place)

    @placify(roles=['admin', 'coordinator'])
    def POST(self, place):
        if place.type != "AC":
            raise web.notfound()

        i = web.input(action="")
        if i.action == "new-group":
            place.add_group(i.name)
        elif i.action == "update-group":
            group = place._find_subplace(i.code)
            name = "%s - %s" % (i.code, i.name)
            group.update_name(name)
        raise web.seeother(place.get_url() + "/groups")


class regions:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        if place.type != "STATE":
            raise web.notfound()
        return render.regions(place)

    @placify(roles=['admin', 'coordinator'])
    def POST(self, place):
        if place.type != "STATE":
            raise web.notfound()

        i = web.input(action="")
        print i.action

        if i.action == "new-region":
            place.add_subplace(i.name, "REGION")
        elif i.action == "update-region":
            p = place._find_subplace(i.code)
            name = "%s - %s" % (i.code, i.name)
            p.update_name(name)
        elif i.action == "update-pcs":
            web.header("content-type", "application/json")            
            data = json.loads(i.data)
            return self.POST_update_pcs(place, data)
        raise web.seeother(place.get_url() + "/regions")

    def POST_update_pcs(self, place, data):
        for row in data:
            key = place.key + "/" + row['code']
            pc = Place.find(key)

            if row['region'] and row['region'].strip():
                # Extract te group code from its name
                key = place.key + "/" + row['region'].split("-")[0].strip()
                region = Place.find(key)
                if pc.region_id != region.id:
                    pc.set_parent("REGION", region)
            else:
                pc.set_parent("REGION", None)
        web.header("content-type", "application/json")
        return '{"result": "ok"}'

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
        place = Place.find(key=get_state())

        form = AddPeopleForm()
        if i.action == "add":
            return render.add_people(place, form, add_users=True)
        else:
            roles = ['admin', 'user']
            users = place.get_people(roles)
            return render.users(place, users)

    def POST(self):
        place = Place.find(key=get_state())
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
        place = Place.find(key=code)
        if not place:
            raise web.notfound()

        user = account.get_current_user()
        if not place.writable_by(user, roles=['coordinator', 'volunteer', 'admin']):
            raise web.seeother(place.url)

        return render.coverage(place, date)

    def POST(self, code, date):
        place = Place.find(key=code)
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
        place = Place.find(key=code)
        if not place:
            raise web.notfound()
        user = account.get_current_user()
        if not place.writable_by(user, roles=['coordinator', 'admin']):
            raise web.seeother(place.url)
        return render.links(place)

    def POST(self, code):
        place = Place.find(key=code)
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
        i = web.input(fail=None, dev=None, backdoor=None)
        if i.fail:
            raise Exception('failed')
        elif i.dev:
            web.header("Content-type", "text/plain")
            return ("\nTo access this website programatically,\n" +
                    "add the following header to your requests.\n\n" +
                    "Cookie: session=" + web.cookies().session + "\n\n")
        elif i.backdoor:
            try:
                env = {"out": StringIO()}
                execfile("backdoor.py", env, env)
                return env['out'].getvalue()
            except IOError:
                raise web.notfound()
        return "hello world!"

class do_search:
    def GET(self):
        i = web.input(q="", page=1)
        page = int(i.page)
        nmatched, results = search.search(i.q, page=page-1)
        if len(results) == 1 and page == 1:
            raise web.seeother(results[0].url)
        else:
            return render.search(i.q, nmatched, results)

class download:
    def GET(self, name):
        user = account.get_current_user()
        if name == "contacts.xls":
            is_admin = user and user.role == 'admin'
            is_coordinator = user and user.role == 'coordinator' and user.place.type in ['STATE', 'PC']
            if is_admin or is_coordinator:
                return self.download_contacts()
        raise web.notfound()

    def download_contacts(self):
        dataset = get_all_coordinators_as_dataset()
        web.header("Content-disposition", "attachment; filename=coordinator-contacts.xls")
        web.header("Content-Type", "application/vnd.ms-excel")
        return dataset.xls

class download_coordinators:
    def GET(self, code):
        place = Place.find(key=code)
        if not place:
            raise web.notfound()
        user = account.get_current_user()
        if not place.writable_by(user, roles=['coordinator', 'admin']):
            raise web.seeother(place.url)
        dataset = place.get_all_coordinators_as_dataset()
        web.header("Content-disposition", "attachment; filename=%s-coordinators.xls" % place.code)
        web.header("Content-Type", "application/vnd.ms-excel")
        return dataset.xls

class activity:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        activities = place.get_activity()
        return render.activity(place, activities)

class login:
    def GET(self):
        google = googlelogin.GoogleLogin()
        return render.login(google.get_redirect_url(), error=False)

class logout:
    def POST(self):
        account.logout()
        raise web.seeother("/")


class oauth2callback:
    def GET(self):
        i = web.input(code=None, error=None, state=None)

        if i.code:
            google = googlelogin.GoogleLogin()
            try:
                token = google.get_token(i.code)
                userinfo = google.get_userinfo(token.access_token)
                if userinfo:
                    account.set_login_cookie(userinfo.email)
                    raise web.seeother("/")
            except IOError:
                return render.login(google.get_redirect_url(), error=True)
        raise web.seeother("/login")

def load_config(configfile):
    web.config.update(yaml.load(open(configfile)))

def check_config():
    if "--config" in sys.argv:
        index = sys.argv.index("--config")
        configfile = sys.argv[index+1]
        sys.argv = sys.argv[:index] + sys.argv[index+2:]
        load_config(configfile)

def open_shell():
    from code import InteractiveConsole
    console = InteractiveConsole()
    console.push("import voternet")
    console.push("from voternet import models")
    console.interact()

def main():
    check_config()
    if "--shell" in sys.argv:
        return open_shell()

    if web.config.get('error_email_recipients'):
        app.internalerror = web.emailerrors(
            web.config.error_email_recipients, 
            app.internalerror, 
            web.config.get('from_address'))

    app.run()

if __name__ == "__main__":
    main()