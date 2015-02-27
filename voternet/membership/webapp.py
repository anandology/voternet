"""AAP Bengaluru member registration form
"""

import web
from webpy_jinja2 import render_template, context_processor
from form import RegistrationForm
from ..models import get_db
from .. import account, googlelogin
import json
import os

web.config['jinja2_template_path'] = 'voternet/membership/templates'

class member_registration:
    def GET(self):
        user = account.get_current_user()
        google = googlelogin.GoogleLogin()
        next = web.ctx.path
        google_url = google.get_redirect_url(state=next)

        form = RegistrationForm()
        return render_template("index.html", form=form, user=user, google_url=google_url)

    def POST(self):
        user = account.get_current_user()
        google = googlelogin.GoogleLogin()
        next = web.ctx.path
        google_url = google.get_redirect_url(state=next)

        form = RegistrationForm(web.webapi.rawinput())
        if user and form.validate():
            self.add_member(form.data)
            return "done"
        else:
            return render_template("index.html", form=form, user=user, google_url=google_url)

    def add_member(self, data):
        def process_value(value):
            if isinstance(value, list):
                return ",".join(v.replace(",", " ") for v in value)
            else:
                return value
        data = {k: process_value(v) for k, v in data.items()}
        db = get_db()
        db.insert("signup", name=data['name'], phone=data['mobile'], email=data['email'], data=json.dumps(data))
