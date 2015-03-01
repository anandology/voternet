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
            self.add_member(user, form.data)
            return render_template("index.html", form=form, user=user, google_url=google_url, done=True)
        else:
            return render_template("index.html", form=form, user=user, google_url=google_url)

    def add_voterid_info(self, info, prefix, result, skip_presonal=False):
        """Adds the voterid info to result with given prefix.

        Used to add voterid or proxy voterid info to result with prefix
        VOTER- or RESIDENCE-.
        """
        info = dict(info)
        info.pop('voterid')
        if skip_presonal:
            for k in ['name', 'relname', 'gender', 'age']:
                info.pop(k)
        result.update({prefix+k})

    def add_member(self, user, data):
        def process_value(value):
            if isinstance(value, list):
                return ",".join(v.replace(",", " ") for v in value)
            else:
                return value
        special_fields = ['voterid_info', 'proxy_voterid_info', 'date_of_birth']
        data2 = {k: process_value(v) for k, v in data.items() if k not in special_fields}

        data2['voterid_info'] = json.loads(data['voterid_info']) if data.get("voterid_info") else None
        data2['proxy_voterid_info'] = json.loads(data['proxy_voterid_info']) if data.get("proxy_voterid_info") else None
        data2['submitted_by'] = user.email
        data2['date_of_birth'] = data['date_of_birth'].isoformat()

        db = get_db()
        db.insert("signup", name=data['name'], phone=data['mobile'], email=data['email'], data=json.dumps(data2))
