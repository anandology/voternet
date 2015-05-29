"""AAP Bengaluru member registration form
"""

import web
from webpy_jinja2 import render_template, context_processor
from form import RegistrationForm
from ..models import get_db, Place
from .. import account, googlelogin, utils
import json
import os
import tablib
import datetime
import logging

logger = logging.getLogger("webapp")

web.config['jinja2_template_path'] = 'voternet/membership/templates'

@context_processor
def context_vars():
    return {
        'current_url': web.ctx.home + web.ctx.fullpath
    }

class member_registration:
    USE_SIMPLE_FORM = False

    def GET(self):
        user = account.get_current_user()
        google = googlelogin.GoogleLogin()
        next = web.ctx.path
        google_url = google.get_redirect_url(state=next)

        form = RegistrationForm()
        return render_template("index.html", form=form, user=user, google_url=google_url, simple=self.USE_SIMPLE_FORM)

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
            return render_template("index.html", form=form, user=user, google_url=google_url, simple=self.USE_SIMPLE_FORM)

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
                return ",".join(v.replace(",", " ").strip() for v in value)
            else:
                return value.strip()
        special_fields = ['voterid_info', 'proxy_voterid_info', 'date_of_birth']
        data2 = {k: process_value(v) for k, v in data.items() if k not in special_fields}

        data2['voterid_info'] = json.loads(data['voterid_info']) if data.get("voterid_info") else None
        data2['proxy_voterid_info'] = json.loads(data['proxy_voterid_info']) if data.get("proxy_voterid_info") else None
        data2['submitted_by'] = user.email
        data2['date_of_birth'] = data['date_of_birth'] and data['date_of_birth'].isoformat() or ''

        place_info = data2['voterid_info'] or data2['proxy_voterid_info'] or {}
        if place_info:
            ac = place_info['ac'].split("-")[0].strip()
            pb = place_info['pb'].split("-")[0].strip()
            place_key = "KA/{}/{}".format(ac, pb)
            place = Place.find(place_key)

            member = place.add_volunteer(
                name=data2['name'],
                email=data2['email'] if data2['email'] != 'NA' else None,
                phone=data2['mobile'],
                voterid=data2['voterid'] or None,
                role='pb_agent',
                notes='membership-signup')
        else:
            place = None
            member = None

        db = get_db()
        db.insert("signup",
            place_id=place and place.id,
            name=data['name'],
            phone=data['mobile'],
            email=data['email'],
            data=json.dumps(data2))
        if member:
            try:
                utils.notify_signup(member)
            except:
                logger.error("Failed to notify about signup.", exc_info=True)

class member_registration2(member_registration):
    USE_SIMPLE_FORM = True

def get_signups_as_dataset():
    rows = get_db().select("signup", order='timestamp, id')

    def process_row(row):
        data = row.data

        IST = datetime.timedelta(hours=5, minutes=30)
        timestamp = row.timestamp + IST # Add timezone offset for Indian Standard Time

        if isinstance(data, basestring):
            data = json.loads(data)

        d = dict(data)
        residing_info = d.get('voterid_info') or d.get('proxy_voterid_info') or {}
        d['residing_lc'] = residing_info.get('lc')
        d['residing_ac'] = residing_info.get('ac')
        d['residing_ward'] = residing_info.get('ward')
        d['residing_booth'] = residing_info.get('pb')

        voter_info = d.get('voterid_info') or {}
        d['voter_name'] = voter_info.get('name')
        d['voter_relname'] = voter_info.get('rel_name')
        d['voter_lc'] = voter_info.get('lc')
        d['voter_ac'] = voter_info.get('ac')
        d['voter_ward'] = voter_info.get('ward')
        d['voter_booth'] = voter_info.get('pb')
        d['timestamp'] = timestamp.isoformat()

        return [d.get(c, "-") for c in columns]

    columns = ("name father_name gender date_of_birth mobile mobile2 email" +
              " emergency_contact address pincode employer livelihood" +
              " choice_of_communication work_from internet_connection" +
              " how_much_time languages skills active_volunteer contributions" +
              " reporting_person_name reporting_person_mobile" +
              " is_voter_at_residence voterid proxy_voterid" +
              " residing_lc residing_ac residing_ward residing_booth " +
              " voter_name voter_relname voter_lc voter_ac voter_ward voter_booth" +
              " timestamp"
            ).split()

    header_labels = {
        "livelihood": "Occupation",
        "work_from": "Would Like To Work From",
        "how_much_time": "How Much Time You Ccan Volunteer",
        "skills": "Areas where you can volunteer",
        "active_volunteer": "Volunteered for Aam Aadmi Party before",
        "contributions": "What did you volunteer",
        "residing_ac": "Residing AC",
        "residing_lc": "Residing LC",
        "voter_lc": "Voter LC",
        "voter_ac": "Voter AC",
    }
    headers = [header_labels.get(c, c.replace("_", " ").title()) for c in columns]
    dataset = tablib.Dataset(headers=headers)
    for row in rows:
        dataset.append(process_row(row))
    return dataset
