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
import tablib
import urllib
import logging

from models import Place, Person, Invite, SendMailBatch, get_all_coordinators_as_dataset, get_voterid_details
import forms
import googlelogin
import account
import search
import flash
import utils

logger = logging.getLogger("webapp")

urls = (
    "/", "index",

    "/account/login", "login",
    "/account/logout", "logout",
    "/account/forgot-password", "forgot_password",
    "/account/reset-password", "change_password",
    "/account/change-password", "change_password",
    "/account/edit/(\d+-.*)", "edit_account",
    "/account/oauth2callback", "oauth2callback",
    "/login/oauth2callback", "oauth2callback",
    "/report-issue", "report_issue",
    "/tmp/(KA/AC\d+)/px.txt", "tmp_px_dump",
    "/x/member-registration", "voternet.membership.webapp.member_registration",


    "/sudo", "sudo",
    "/debug", "debug",
    "/search", "do_search",    
    "/download/(.*)", "download",
    "/voterid/(.*)", "voter_info",    
    "/([A-Z][A-Z])/users", "users",    
    "/([\w/]+)/delete", "delete_place",
    "/([\w/]+)/edit", "edit_place",
    "/([\w/]+)/info", "place_info",
    "/([\w/]+)/signups", "vol_signups",
    "/([\w/]+)/signups.xls", "vol_signups_xls",
    "/([\w/]+)/localities", "place_localities",
    "/([\w/]+)/export-localities", "export_localities",
    "/([\w/]+)/booths", "pb_list",
    "/([\w/]+)/groups", "pb_groups",
    "/([\w/]+)/regions", "regions",
    "/([\w/]+)/add-people", "add_people",
    "/([\w/]+)/pb-agents", "pb_agents",
    "/([\w/]+)/import-people", "import_people",
    "/([\w/]+)/people", "list_people",
    "/([\w/]+)/people/(\d+)", "edit_person",
    "/([\w/]+)/links", "links",
    "/([\w/]+)/coordinators.xls", "download_coordinators",
    "/([\w/]+)/volunteers.xls", "download_volunteers",
    "/([\w/]+)/pb-agents.xls", "download_pb_agents",
    "/([\w/]+)/member-registrations.xls", "download_member_registrations",
    "/([\w/]+)/activity", "activity",
    "/([\w/]+)/sms", "send_sms",
    "/([\w/]+)/email", "send_email",
    "/([\w/]+)/email/(\d+)", "send_email_batch",
    "/([\w/]+)/messages", "messages",
    "/([\w/]+)/messages/(\d+)", "view_message",
    "/([\w/]+)/messages/new", "new_message",
    "/([\w/]+)", "place",
    "/(.*/PB\d+)/(\d\d\d\d-\d\d-\d\d)", "coverage",
)

app = web.application(urls, globals())
app.add_processor(flash.flash_processor)

def login_requrired(handler):
    whitelist = ["/report-issue"]
    if (not web.ctx.path.startswith("/account") 
        and not web.ctx.path.startswith("/login") 
        and not web.ctx.path.startswith("/voterid/") 
        and not web.ctx.path.startswith("/tmp/") 
        and not web.ctx.path.startswith("/x/")
        and web.ctx.path not in whitelist):
        user = account.get_current_user()
        if not user:
            params = {"next": web.ctx.fullpath}
            raise web.seeother("/account/login?" + urllib.urlencode(params))

        elif not user.is_authorized() and user.email not in web.config.get("super_admins", []):
            return render.permission_denied()
    return handler()

app.add_processor(login_requrired)

def placify(f=None, roles=None, types=None):
    """Decorator that converts the first argument from place code to place.
    Also makes sure if the current user has the specified permission.
    """
    if not f:
        return lambda f: placify(f=f, roles=roles, types=types)


    @functools.wraps(f)
    def g(self, code, *args):
        place = Place.find(key=code)
        if not place:
            raise web.notfound()

        if types is not None and place.type not in types:
            raise web.notfound()

        user = account.get_current_user()

        if not user or not place.viewable_by(user):
            raise web.ok(render.access_restricted())

        if roles:
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
    return datetime.datetime.now(get_timezone()).date()

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
    "max": max,
    "storage": web.storage,
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
    "get_site_full_title": lambda: web.config.get("site_full_title", tglobals['get_site_title']()),
    "get_today": get_today,
    "get_yesterday": get_yesterday,
    "get_flashed_messages": flash.get_flashed_messages,
    "get_site_url": lambda : web.ctx.home,
    "get_url": lambda: web.ctx.home + web.ctx.fullpath,

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
        user = account.get_current_user()
        return render.dashboard(user)

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
            raise web.seeother(place.url + "/users")
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

class place_localities:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        if place.type != "WARD":
            raise web.notfound()
        return render.localities(place)

    @placify(roles=['admin', 'coordinator'])
    def POST(self, place):
        if place.type != "WARD":
            raise web.notfound()

        i = web.input(localities="", pincodes="")
        print i
        localities = [line.strip() for line in i.localities.splitlines() if line.strip()]
        pincodes = [line.strip() for line in i.pincodes.splitlines() if line.strip()]
        place.set_localities(localities, pincodes)
        flash.add_flash_message("info", "Thanks for updating localities info.")
        raise web.seeother(place.url)

class export_localities:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        d = place.get_all_localities()
        web.header("Content-Type", "application/json")
        return json.dumps(d)

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
            code = place.key + "/" + row['code']
            pb = Place.find(code)

            if row['ward'] and row['ward'].strip():
                # Extract te group code from its name
                key = place.key + "/" + row['ward'].split("-")[0].strip()
                ward = Place.find(key)
                if pb.ward_id != ward.id:
                    pb.set_ward(ward)
            else:
                pb.set_ward(None)

            if row['px'] and row['px'].strip():
                # Extract te group code from its name
                key = place.key + "/" + row['px'].split("-")[0].strip()
                px = Place.find(key)
                if pb.px_id != px.id:
                    pb.set_px(px)
            else:
                pb.set_px(None)

        web.header("content-type", "application/json")
        return '{"result": "ok"}'

class vol_signups:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        return render.volunteer_signups(place)

class vol_signups_xls:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        web.header("Content-disposition", "attachment; filename=%s-signups.xls" % place.code)
        web.header("Content-Type", "application/vnd.ms-excel")
        return self.get_dataset(place).xls

    def get_dataset(self, place):
        headers = ['Name', "Phone", 'Email', 'Locality', 'Ward', 'Timestamp']
        dataset = tablib.Dataset(headers=headers)
        for p in place.get_signups():
            dataset.append([p.name, p.phone, p.email, p.address, p.get_place().name, p.added.isoformat()])
        return dataset

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
        form = forms.AddPeopleForm(web.input())
        return render.add_people(place, form)

    @placify(roles=['admin', 'coordinator'])
    def POST(self, place):
        i = web.input()
        form = forms.AddPeopleForm(i)
        if form.validate():
            place.add_volunteer(i.name.strip(), i.email.strip(), i.phone.strip(), i.voterid.strip(), i.role.strip())
            raise web.seeother(place.url)
        else:
            return render.add_people(place, form)

class import_people:
    @placify(roles=['admin', 'coordinator'], types=["REGION", "PC", "AC"])
    def GET(self, place):
        return render.import_people(place)

    @placify(roles=['admin', 'coordinator'], types=["REGION", "PC", "AC"])
    def POST(self, place):
        i = json.loads(web.data())
        batch = i.get('batch')
        as_invite = i.get('as_invite', False)
        data = i['data']
        data = [self.process_row(row) for row in data]

        # skip empty rows
        data = [row for row in data if any(row) and row.name]
        count = 0
        for row in data:
            if self.add_volunteer(row, place, batch, as_invite):
                count += 1
        flash.add_flash_message("success", "Added {0} volunteers.".format(count))
        #raise web.seeother(place.url)
        web.header("content-type", "application/json")
        return '{"result": "ok"}'

    def process_row(self, row):
        """Strips all values.
        """
        return web.storage((k, v and v.strip()) for k, v in row.items())

    def add_volunteer(self, row, ac, batch, as_invite):
        if not row.name:
            return

        if row.place:
            key = ac.key + "/" + row.place.split("-")[0].strip()
            place = Place.find(key)
            if not place:
                return
        else:
            place = ac
        if row.email and place.find_volunteer(email=row.email, phone=None, role=row.role):
            logger.warn("Already found a vol with same email and role. Ignoring this %s", row)
            return
        if row.phone and place.find_volunteer(email=None, phone=row.phone, role=row.role):
            logger.warn("Already found a vol with same phone number and role. Ignoring this %s", row)
            return
        if not row.email and not row.phone:
            logger.warn("No email/phone number specified. Ignoring this %s", row)
            return

        if as_invite:
            if not row.email:
                logger.warn("Can't add invite as no email provided. Ignoring this %s", row)
                return
            if Invite.find_by_email(row.email):
                logger.warn("Already found an invite with the same email. Ignoring this %s", row)
                return

            place.add_invite(       
                name=row.name, 
                phone=row.phone, 
                email=row.email, 
                batch=batch)
        else:
            place.add_volunteer(
                name=row.name, 
                phone=row.phone, 
                email=row.email, 
                voterid=row.voterid, 
                role=row.role,
                notes=batch)
        return True

class pb_agents:
    @placify(roles=['coordinator', 'admin'], types=['PC', 'AC', 'WARD', 'PB'])
    def GET(self, place):
        return render.pb_agents(place)

class users:
    def GET(self, key):
        place = Place.find(key=key)
        self.check_write_access(place)

        i = web.input(action="")
        if i.action == "add":
            form = self.make_form()
            return render.add_people(place, form, add_users=True)
        else:
            roles = ['admin', 'user']
            users = place.get_people(roles)
            return render.users(place, users)

    def check_write_access(self, place):
        user = account.get_current_user()    
        if not place.writable_by(user):
            raise web.ok(render.access_restricted())

    def make_form(self, *args):
        form = forms.AddPeopleForm(*args)
        form.role.choices = [('admin', 'Admin'), ('user', 'User')]
        return form

    def POST(self, key):
        place = Place.find(key=key)
        self.check_write_access(place)

        if not place:
            raise web.notfound()
        elif not place.writable_by(account.get_current_user()):
            raise web.seeother(place.url + "/users")

        i = web.input()
        form = self.make_form(i)
        if form.validate():
            place.add_volunteer(i.name.strip(), i.email.strip(), i.phone.strip(), i.voterid.strip(), i.role.strip())
            raise web.redirect(place.url + "/users")
        else:
            return render.add_people(place, form, add_users=True)

class voter_info:
    def GET(self, voterid):
        d = get_voterid_details(voterid, fetch=True)
        if d:
            d.booth = Place.from_id(d.pb_id)
            d.ward = d.booth.get_parent("WARD")
            d.ac = d.booth.get_parent("AC")
            d.pc = d.booth.get_parent("PC")
        #web.header("content-type", "application/json")
        #return json.dumps(d)
        return render.voterid(voterid, d)

class list_people:
    @placify(roles=['coordinator', 'admin'])
    def GET(self, place):
        i = web.input(notes=[], email=None, format="html")
        if i.format == "json":
            return self.GET_json(place, i)
        return render.people(place, i.notes)

    def GET_json(self, place, i):
        people = place.get_all_volunteers(["coordinator", "volunteer", "pb_agent"], notes=i.notes, email=i.email)
        d = [p.dict() for p in people]
        web.header("content-type", "application/json")
        return json.dumps(d)

class edit_person:
    @placify()
    def GET(self, place, id):
        person = Person.find(place_id=place.id, id=id)
        if not person:
            raise web.notfound()

        user = account.get_current_user()
        if user.role not in ['admin', 'coordinator'] and person.id != int(id):
            return render.access_restricted()
        form = forms.AddPeopleForm(person)
        return render.person(person, form, show_role=self.can_change_role(user))

    def can_change_role(self, person):
        return person.role in ['admin', 'coordinator']

    @placify()
    def POST(self, place, id):
        person = Person.find(place_id=place.id, id=id)
        if not person:
            raise web.notfound()

        user = account.get_current_user()
        if user.role not in ['admin', 'coordinator'] and person.id != int(id):
            return render.access_restricted()

        i = web.input()
        if i.action == "save":
            d = dict(name=i.name, email=i.email, phone=i.phone, voterid=i.voterid)
            if self.can_change_role(user):
                d['role'] = i.role
            person.update(d)
            if person.role == 'pb_agent':
                person.populate_voterid_info()
                if person.get_voterid_info():
                    utils.sendmail_voterid_added(person)
                else:
                    utils.sendmail_voterid_pending(person)
            flash.add_flash_message("success", "Thanks for updating!")            
        elif i.action == "delete" and self.can_change_role(user): # don't allow self deletes
            person.delete()
            flash.add_flash_message("success", "Delete the volunteer successfully.")            
        elif i.action == "update-place":
            next = i.get("next")
            new_place = Place.find(i.place)
            if not new_place:
                flash.add_flash_message("warning", "Unable to update the location of the volunteer.")
                raise web.seeother(next or place.url)
            elif not new_place.writable_by(user):
                return render.access_restricted()
            else:
                person.update(place_id=new_place.id)
                flash.add_flash_message("success", "Assigned {0} to {1}".format(person.name, new_place.name))
                raise web.seeother(next or new_place.url)
        raise web.seeother(place.url)

class edit_account:
    """TODO: merge this with edit_people.
    """
    def GET(self, token):
        person = Person.find_by_edit_token(token)
        if not person:
            return render.invalid_token()

        form = forms.AddPeopleForm(person)
        return render.person(person, form, show_role=False)

    def POST(self, token):
        person = Person.find_by_edit_token(token)
        if not person:
            raise render.invalid_token()

        i = web.input()
        if i.action == "save":
            d = dict(name=i.name, email=i.email, phone=i.phone, voterid=i.voterid)
            person.update(d)
            return render.message("Thanks!", "Thank you for updaing your account details.")
        else:
            return self.GET(token)

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
        if not user or user.email not in web.config.get('super_admins', []):
            return render.access_restricted()

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

def is_coordinator(levels=['STATE']):
    user = account.get_current_user()
    _is_admin = user and user.role == 'admin'
    _is_coordinator = user and user.role == 'coordinator' and user.place.type in levels
    return _is_admin or _is_coordinator


class download:
    def GET(self, name):
        if not is_coordinator():
            raise web.notfound()

        if name == "contacts.xls":
            return self.download_contacts()
        raise web.notfound()

    def download_contacts(self):
        dataset = get_all_coordinators_as_dataset()
        web.header("Content-disposition", "attachment; filename=coordinator-contacts.xls")
        web.header("Content-Type", "application/vnd.ms-excel")
        return dataset.xls

class download_coordinators:
    def GET(self, code):
        if not is_coordinator():
            raise web.notfound()

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

class download_volunteers:
    @placify(roles=['coordinator', 'admin'])
    def GET(self, place):
        if not is_coordinator():
            raise web.notfound()

        dataset = place.get_all_volunteers_as_dataset()
        web.header("Content-disposition", "attachment; filename=%s-volunteers.xls" % place.code)
        web.header("Content-Type", "application/vnd.ms-excel")
        return dataset.xls

class download_pb_agents:
    @placify(roles=['coordinator', 'admin'])
    def GET(self, place):
        if not is_coordinator():
            raise web.notfound()

        dataset = place.get_all_volunteers_as_dataset(roles=['pb_agent'])
        web.header("Content-disposition", "attachment; filename=%s-pb-agents.xls" % place.code)
        web.header("Content-Type", "application/vnd.ms-excel")
        return dataset.xls

class download_member_registrations:
    @placify(roles=['coordinator', 'admin'])
    def GET(self, place):
        if not is_coordinator():
            raise web.notfound()

        from voternet.membership.webapp import get_signups_as_dataset
        dataset = get_signups_as_dataset()
        web.header("Content-disposition", "attachment; filename=%s-member-registrations.xls" % place.code)
        web.header("Content-Type", "application/vnd.ms-excel")
        return dataset.xls


class activity:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        activities = place.get_activity()
        return render.activity(place, activities)

class send_sms:
    @placify(roles=['admin', 'coordinator'], types=['PC', 'AC'])
    def GET(self, place):
        form = forms.SMSForm()
        return render.sms(place, form)

    @placify(roles=['admin', 'coordinator'], types=['PC', 'AC'])
    def POST(self, place):
        i = web.input()
        form = forms.SMSForm(i)
        if not form.validate():
            return render.sms(place, form)
        people = self.get_people(place, i.people)
        count = utils.send_sms(people, i.message)
        flash.add_flash_message("success", "Successfully sent SMS to {} people".format(count))
        return render.sms(place, form)

    def get_people(self, place, choice):
        if choice == "self":
            user = account.get_current_user()
            return [user]
        elif choice == "agents.confirmed":
            agents = [p for p in place.get_pb_agents() if p.get_voterid_info()]
            return agents
        elif choice == "agents.pending":
            agents = [p for p in place.get_pb_agents() if not p.get_voterid_info()]
            return agents
        elif choice == "volunteers":
            return place.volunteers
        else:
            return []


class send_email:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        form = forms.EmailForm()
        return render.send_email(place, form)

    @placify(roles=['admin', 'coordinator'])
    def POST(self, place):
        i = web.input()
        form = forms.EmailForm(i)
        if not form.validate():
            return render.send_email(place, form)

        i.message = i.message + "\n\n---\nIf you do not like to receive any emails from us, please unsubscribe at http://ka.aapvol.in/unsubscribe?email={email}"

        if i.action == "preview":
            preview = web.storage()
            preview.to_address = "Test Person <test@example.com>"
            preview.from_address = web.config.from_address
            preview.subject = i.subject
            preview.message = i.message.replace("{name}", 'Test Person')
            return render.send_email(place, form, preview)
        else:
            people = send_sms().get_people(place, i.people)
            batch = SendMailBatch.new(
                from_address=web.config.from_address,
                subject=i.subject,
                message=i.message)
            batch.add_people(people)
            utils.sendmail_batch(batch, async=True)
            raise web.seeother(place.url + "/email/" + str(batch.id))

class send_email_batch:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place, id):
        batch = SendMailBatch.find(id=id)
        return render.sendmail_batch(place, batch)

    def sendmail(self, batch, person):
        message = batch.message.replace('{name}', person.name)
        utils.send_email(to_address=person.to_address, message=message, subject=batch.subject)


class new_message:
    @placify(roles=['admin', 'coordinator'])
    def GET(self, place):
        return render.new_message(place)

    @placify(roles=['admin', 'coordinator'])
    def POST(self, place):
        i = web.input(message="")
        if not i.message:
            return render.new_message(place)
        else:
            user = account.get_current_user()
            place.post_message(i.message, author=user)
            flash.add_flash_message("info", "Your message been posted successfully.")
            return web.seeother(place.url)

class messages:
    @placify()
    def GET(self, place):
        return render.messages(place)

class view_message:
    @placify()
    def GET(self, place, msg_id):
        m = place.find_message(msg_id)
        if m:
            return render.view_message(place, m)
        else:
            raise web.notfound()

class login:
    def GET(self):
        i = web.input(next=None, error="false")
        next = i.next or "/"
        error = i.error == "true"
        google = googlelogin.GoogleLogin()
        form = forms.LoginForm()        
        return render.login(google.get_redirect_url(state=next), error=error, form=form)

    def POST(self):
        i = web.input(next=None)
        next = i.next or "/"
        form = forms.LoginForm(i)
        if form.validate():
            account.set_login_cookie(i.email)
            flash.add_flash_message("success", "Login successful!")
            raise web.redirect(next)
        else:
            google = googlelogin.GoogleLogin()            
            return render.login(google.get_redirect_url(), error=False, form=form)

class logout:
    def POST(self):
        i = web.input(next=None, error="false")
        next = i.next or "/"
        account.logout()
        raise web.seeother(next)
    GET = POST

class forgot_password:
    def GET(self):
        return render.reset_password()

    def POST(self):
        i = web.input(email="")
        person = Person.find(email=i.email)
        if person:
            token = person.generate_reset_token()
            msg = render_template("email_password_reset", token=token)
            utils.send_email(to_addr=person.email, message=msg)
            #TODO: send email
            return render.reset_password(email=i.email, success=True)
        else:
            return render.reset_password(email=i.email, error=True)

class change_password:
    def GET(self):
        user = self.get_user()
        form = forms.ChangePasswordForm()
        return render.change_password(user, form)

    def get_user(self):
        i = web.input(token=None)
        if i.token:
            user = Person.find_from_reset_token(i.token)
            if not user:
                form = forms.ChangePasswordForm()
                raise web.ok(render.change_password(user, form))
            else:
                return user
        else:
            user = account.get_current_user()
            if not user:
                raise web.seeother("/account/login")
            else:
                return user

    def POST(self):
        user = self.get_user()

        i = web.input()
        form = forms.ChangePasswordForm(i)
        if form.validate():
            account.set_password(user, i.password)
            flash.add_flash_message("success", "Your password has been updated successfully. Please login to continue.")
            raise web.seeother("/account/login")
        else:
            return render.change_password(user, form)


class oauth2callback:
    def GET(self):
        i = web.input(code=None, error=None, state=None)
        next = i.state or "/"
        if i.code:
            google = googlelogin.GoogleLogin()
            try:
                token = google.get_token(i.code)
                userinfo = google.get_userinfo(token.access_token)
                if userinfo:
                    account.set_login_cookie(userinfo.email)
                    raise web.seeother(next)
            except IOError:
                raise web.seeother(next + "?error=true")
                #return render.login(google.get_redirect_url(), error=True, form=forms.LoginForm())

        raise web.seeother(next)

class report_issue:
    def GET(self):
        i = web.input(url=None)
        return render.report_issue(i.url)

    def POST(self):
        i = web.input(url=None, email=None, description=None)
        msg = render_template("email_issue", i, web.cookies(), web.ctx.env)
        utils.send_email(to_addr=web.config.super_admins, message=msg)
        flash.add_flash_message("info", "Thanks for reporting the issue. We'll get back to you shortly.")
        raise web.seeother("/")

class tmp_px_dump:
    def GET(self, key):
        place = Place.find(key)
        if not place:
            raise web.notfound()

        booths = place.get_all_polling_booths()
        from collections import defaultdict
        d = defaultdict(list)
        pxd = {}
        for booth in booths:
            px = booth.get_parent("PX")
            px_code = px.key.split("/")[-1]
            d[px_code].append(booth)
            pxd[px_code] = px

        def get_row(px_code):
            booths = d[px_code]
            px = pxd[px_code]
            ward = px.get_parent("WARD")
            ward_name = ward and ward.name or "-"
            return [place.code, place.name, px_code, ",".join(b.code for b in booths), px.name, ward_name]

        data = [get_row(px_code) for px_code in sorted(d)]
        web.header("content-type", "text/plain")
        return "\n".join("\t".join(row) for row in data)

def load_config(configfile):
    web.config.update(yaml.load(open(configfile)))

def check_config():
    if "--config" in sys.argv:
        index = sys.argv.index("--config")
        configfile = sys.argv[index+1]
        sys.argv = sys.argv[:index] + sys.argv[index+2:]
        load_config(configfile)
        web.config.configfile = configfile

        if web.config.get('error_email_recipients'):
            app.internalerror = web.emailerrors(
                web.config.error_email_recipients, 
                app.internalerror, 
                web.config.get('error_from_address'))

def open_shell():
    from code import InteractiveConsole
    console = InteractiveConsole()
    console.push("import voternet")
    console.push("from voternet import models")
    console.interact()

def main():
    FORMAT = "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)

    check_config()
    if "--shell" in sys.argv:
        return open_shell()

    logger = logging.getLogger(__name__)
    logger.info("starting the webapp")
    app.run()

if __name__ == "__main__":
    main()
