import web
import re
import json
import cache
import time, datetime
import tablib
import uuid

@web.memoize
def get_db():
    params = web.config.get("db_parameters") or dict(dbn="postgres", db="voternet")
    return web.database(**params)

re_normalize = re.compile("[^a-z]")
def normalize(name):
    return re_normalize.sub("", name.lower())

class Place(web.storage):
    TYPE_LABELS = dict(
        STATE="State",
        REGION="Region",
        PC="Parliamentary Constituency",
        AC="Assembly Constituency",
        WARD="Ward",
        PS="Polling Station",
        PB="Polling Booth")

    TYPES = ['STATE', 'REGION', 'PC', 'AC', 'WARD', 'PB']

    CODE_PREFIXES = {
        "STATE": "",
        "REGION": "R",
        "PC": "PC",
        "AC": "AC",
        "WARD": "W",
        "PB": "PB"
    }

    COLUMN_NAMES = dict(STATE="state_id", REGION="region_id", PC="pc_id", AC="ac_id", WARD="ward_id")

    @property
    def url(self):
        return self.get_url()

    def get_url(self):
        return "/" + self.key
        
    @property
    def parent(self):
        if self.type != 'STATE':
            # quick fix to handle PollingBooths not assigned to any ward
            if self.type == 'PB' and self.ward_id is None:
                parent_id = self.ac_id
            else:
                parent_id = self[self.parent_column]
            return parent_id and Place.from_id(parent_id)

    def get_parent(self, type):
        col = type.lower() + "_id"
        return self[col] and Place.from_id(self[col])

    def get_ac(self):
        return Place.from_id(self.ac_id)

    def get_zone(self):
        w = self.ward_id and Place.from_id(self.ward_id)
        if w:
            return w.name

    def get_parents(self):
        i = self.TYPES.index(self.type)
        parent_types = self.TYPES[:i]
        parents = [self.get_parent(t) for t in parent_types]
        return [p for p in parents if p]

    def get_subplaces(self):
        """Returns list of all sub places"""
        rows = get_db().query("SELECT * FROM places WHERE {0} = $id ORDER BY key".format(self.type_column), vars=self)
        return [Place(row) for row in rows]

    @property
    def volunteers(self):
        return self.get_people(['coordinator', 'volunteer'])

    def get_people(self, roles):
        result = get_db().select("people",
            where="place_id=$place_id AND role IN $roles",
            order='role, id',
            vars={"place_id": self.id, "roles": roles})
        return [Person(row) for row in result]

    @cache.object_memoize(key="coordinators")
    def get_coordinators(self):
        return self.get_people(["coordinator"])

    def add_volunteer(self, name, email, phone, voterid=None, role=None):
        person_id = get_db().insert("people", 
            place_id=self.id, 
            name=name,
            email=email,
            phone=phone,
            voterid=voterid,
            role=role)
        self._invalidate_object_cache()
        self.record_activity("volunteer-added", volunteer_id=person_id, name=name, role=role)

    def _invalidate_object_cache(self):
        cache.invalidate_object_cache(objects=[self] + self.get_parents())
        code = self.get_url()[1:] # remove / at the beginning
        cache.invalidate_cache("Place.find", code)
        cache.invalidate_cache("Place.find", code=code)
        cache.invalidate_cache("Place.from_id", self.id)
        cache.invalidate_cache("Place.from_id", id=self.id)

    @property
    def type_label(self):
        return self.TYPE_LABELS[self.type]

    @property
    def type_column(self):
        return self.type.lower() + "_id"

    @property
    def parent_column(self):
        if self.type != "STATE":
            return self.TYPES[self.TYPES.index(self.type)-1].lower() + "_id"

    @property
    def subtype(self):
        try:
            return self.TYPES[self.TYPES.index(self.type)+1]
        except (IndexError, ValueError):
            return None

    @property
    def subtype_label(self):
        subtype = self.subtype
        return subtype and self.TYPE_LABELS[subtype]

    def update_info(self, info):
        get_db().update("places", where='id=$self.id', info=info, vars=locals())
        self._invalidate_object_cache()

    def delete(self):
        db = get_db()
        with db.transaction():
            db.query("DELETE FROM people USING places"
                + " WHERE place_id=places.id"
                + "     AND (places.id=$self.id OR places.%s=$self.id)" % self.type_column,
                vars=locals())
            db.query("DELETE FROM places WHERE id=$self.id OR %s=$self.id" % self.type_column, vars=locals())

    def get_all_subtypes(self):
        """Returns all subtypes including type of this place.
        """
        index = self.TYPES.index(self.type)
        return [web.storage(code=type, label=self.TYPE_LABELS[type]) for type in self.TYPES[index:]]

    def get_places(self, type=None):
        db = get_db()
        id = self.id
        type = type or self.subtype
        column = self.type_column
        result = db.select("places", where="%s=$id and type=$type" % column, order="code", vars=locals())
        return [Place(row) for row in result]

    def get_unassigned_places(self, type, parent_type):
        """Returns places of given type inside this subtree, with out parent of parent_type.
        """
        col = parent_type.lower() + "_id"
        where = "%s=$self.id and %s is NULL and type=$type" % (self.type_column, col)
        result = get_db().select("places", where=where, order="code", vars=locals())
        return [Place(row) for row in result]

    def get_unassigned_polling_booths(self):
        result = get_db().select("places", where="ac_id=$self.id and ward_id is NULL and type='PB'", order="code", vars=locals())
        return [Place(row) for row in result]

    def get_all_polling_booths(self):
        result = get_db().select("places", where="ac_id=$self.id and type='PB'", order="code", vars=locals())
        return [Place(row) for row in result]

    def get_wards(self):
        result = get_db().select("places", where="ac_id=$self.id and type='WARD' and code LIKE 'W%' ", order="code", vars=locals())
        return [Place(row) for row in result]

    def get_groups(self):
        result = get_db().select("places", where="ac_id=$self.id and type='WARD' and code NOT LIKE 'W%' ", order="code", vars=locals())
        return [Place(row) for row in result]

    def add_group(self, name, code=None):
        if not code:
            groups = self.get_groups()
            if groups:
                count = 1 + int(web.numify(max([g.code for g in groups])))
            else:
                count = 1
            code = "G%02d" % count
            key = self.key + "/" + code
            name = "%s - %s" % (code, name)
        self._add_place(key, code, name, "WARD")

    def add_subplace(self, name, type, code=None):
        if not code:
            places = self.get_places(type=type)
            if places:
                count = 1 + int(web.numify(max([p.code for p in places])))
            else:
                count = 1
            code = "{0}{1:02d}".format(self.CODE_PREFIXES[type], count)
            key = self.key + "/" + code
            name = "%s - %s" % (code, name)
        self._add_place(key, code, name, type)

    def set_ward(self, ward):
        self.ward_id = ward and ward.id
        get_db().update("places", ward_id=self.ward_id, where="id=$self.id", vars=locals())
        self._invalidate_object_cache()

    def set_parent(self, type, parent):
        if self.get_parent(type) == parent:
            # nothing to change
            return

        col = self.COLUMN_NAMES[type]
        self[col] = parent and parent.id
        values = {col: self[col]}
        where = "id=$self.id OR {0}=$self.id".format(self.type_column)
        get_db().update("places", where=where, vars=locals(), **values)
        places = [Place(row) for row in get_db().select("places", where=where, vars=locals())]
        for p in places:
            p._invalidate_object_cache()

    def update_name(self, name):
        self.name = name
        get_db().update("places", name=name, where="id=$self.id", vars=locals())
        self._invalidate_object_cache()

    def get_places_text(self):
        return "\n".join(str(p) for p in self.get_places())

    def __str__(self):
        name = self.name.split("-", 1)[-1].strip()
        return "{} - {}".format(self.code, name)

    def _add_place(self, key, code, name, type):
        row = web.storage(
            type=type, 
            key=key,
            code=code, 
            name=name,
            state_id=self.state_id,
            region_id=self.region_id,
            pc_id=self.pc_id,
            ac_id=self.ac_id,
            ward_id=self.ward_id,
            ps_id=self.ps_id,
            parent_id=self.id)

        # set the parent id in the apprpriate field
        row[self.type.lower() + "_id"] = self.id
        row['id'] = get_db().insert("places", **row)
        place = Place(row)
        place._invalidate_object_cache()

    re_place_line = re.compile("([^{}]*) {{(.*)}}")
    def process_place_line(self, line):
        """It is tried to make the editing interface simple by providing just
        a text box to enter the names. To manage already existing places, the
        code is added to the place as {{ code }}.

        This function separates the name and code.
        """
        m = self.re_place_line.match(line.strip())
        if m:
            name, code = m.groups()
        else:
            name, code = line, None
        name = name.strip()
        code = code and code.strip()
        return web.storage(name=name, code=code)

    def _find_subplace(self, code):
        db = get_db()
        result = db.select("places", where="code=$code AND parent_id=$self.id", vars=locals())
        if result:
            return Place(result[0])

    @cache.object_memoize(key="counts")
    def get_counts(self):
        if self.type == "PB":
            where = "places.id=$self.id"
        else:
            where = "(places.%s=$self.id OR places.id=$self.id)" % self.type_column

        result = get_db().query(
            "SELECT type, count(*) as count" +
            " FROM places" +
            " WHERE " + where +
            " GROUP BY type", vars=locals())
        return dict((row.type, row.count) for row in result)
        return dict()

    @cache.object_memoize(key="volunteer_counts")
    def get_volunteer_counts(self):
        if self.type == "PB":
            where = "places.id=$self.id"
        else:
            where = "(places.%s=$self.id OR places.id=$self.id)" % self.type_column

        roles = ['coordinator', 'volunteer']
        result = get_db().query(
            "SELECT type, count(*) as count" +
            " FROM places" +
            " JOIN people ON places.id=people.place_id" +
            " WHERE %s AND role in $roles" % where + 
            " GROUP BY type", vars=locals())
        return dict((row.type, row.count) for row in result)

    @cache.object_memoize(key="volunteer_counts_by_date")
    def get_volunteer_counts_by_date(self):
        if self.type == "PB":
            column = "id"
        else:
            column = self.type_column
        result = get_db().query(
            "SELECT to_char(added, 'YYYY-MM-DD')::date as date, count(*) as count" +
            " FROM people, places" +
            " WHERE people.place_id=places.id AND (places.%s=$self.id OR places.id=$self.id)" % column + 
            " GROUP BY 1" + 
            " ORDER BY 1", vars=locals())
        return result.list()

    def get_volunteer_summary(self):        
        result = self.get_volunteer_counts_by_date()
        d = dict((row.date, row.count) for row in result)

        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        thisweek = self.daterange(today-datetime.timedelta(days=6), today)

        return {
            "today": d.get(today, 0),
            "yesterday": d.get(yesterday, 0),
            "thisweek": sum(d.get(date, 0) for date in thisweek),
            "total": sum(d.values())
        }

    def get_volunteer_data_for_graph(self):
        return self.prepare_data_for_graph(self.get_volunteer_counts_by_date())

    @staticmethod
    @cache.memoize(key="Place.find")
    def find(key):
        print "Place.find", key
        result = get_db().select("places", where="key=$key", vars=locals())
        if result:
            return Place(result[0])

    @staticmethod
    def find_all():
        db = get_db()
        return [Place(row) for row in db.select("places")]

    @staticmethod
    @cache.memoize(key="Place.from_id")
    def from_id(id):
        db = get_db()
        result = db.select("places", where="id=$id", vars=locals())
        if result:
            return Place(result[0]) 

    def __eq__(self, other):
        return self.id is not None and isinstance(other, Place) and self.id == other.id

    def __repr__(self):           
        return "<Place: %s>" % dict(self)

    def writable_by(self, user, roles=['coordinator', 'admin']):
        # super admins can write to any page.
        if user.email in web.config.get('super_admins', []):
            return True

        place_ids = [self.id, self.state_id, self.region_id, self.pc_id, self.ac_id, self.ward_id]
        result = get_db().query("SELECT * FROM people" +
            " WHERE lower(email)=lower($user.email)" +
            "   AND place_id in $place_ids" +
            "   AND role IN $roles", vars=locals())
        return bool(result)

    def viewable_by(self, user):
        # super admins can view any page.
        if user.email in web.config.get('super_admins', []):
            return True

        # If they can write, then can view as well.
        if self.writable_by(user):
            return True

        result = get_db().query("SELECT people.* FROM people, places" +
            " WHERE places.id=people.place_id" +
            "   AND lower(people.email)=lower($user.email)" +
            "   AND $self.id IN (places.id, places.ward_id, places.ac_id, places.pc_id, places.region_id, places.state_id)",
            vars=locals())
        return bool(result)

    def add_coverage(self, date, coverage, user):
        db = get_db()
        coverage_json = json.dumps(coverage)
        with db.transaction():
            count = len(self.get_coverage(date))
            db.delete("coverage", where="place_id=$self.id AND date=$date", vars=locals())
            db.insert("coverage", place_id=self.id, date=date, count=len(coverage), data=coverage_json, editor_id=user.id)
            if count == 0:
                self.record_activity("coverage-added", count=len(coverage))
            else:
                self.record_activity("coverage-updated", count=len(coverage), old_count=count)
        self._invalidate_object_cache()

    def get_activity(self, types=None, offset=0, limit=100):
        if types is None:
            types = ['volunteer-added', 'coverage-added']
        if self.type == 'PB':
            where = "places.id=$self.id"
        else:
            where = "(places.id=$self.id OR places.%s=$self.id)" % self.type_column
        result = get_db().query(
            "SELECT activity.*" +
            " FROM activity, places" + 
            " WHERE activity.place_id=places.id AND activity.type IN $types AND " + where +
            " ORDER by tstamp DESC OFFSET $offset LIMIT $limit",
            vars=locals())
        return [Activity(a) for a in result]

    def record_activity(self, type, **kwargs):
        Activity.record(type, self.id, **kwargs)

    def get_coverage(self, date):
        result = get_db().select("coverage", where="place_id=$self.id AND date=$date", vars=locals())
        if result:
            return json.loads(result[0].data)
        else:
            return []

    @cache.object_memoize(key="coverage_count")
    def get_coverage_count(self):
        if self.type == "PB":
            column = "id"
        else:
            column = self.type_column
        result = get_db().query(
                    "SELECT sum(count) as count" +
                    " FROM coverage, places" +
                    " WHERE coverage.place_id=places.id" +
                    "   AND places.%s=$self.id" % column, vars=locals())
        if result:
            return result[0].count or 0
        else:
            return 0

    @cache.object_memoize(key="coverage_count_by_date")
    def get_coverage_counts_by_date(self):
        if self.type == "PB":
            column = "id"
        else:
            column = self.type_column
        result = get_db().query(
                    "SELECT date, sum(count) as count" +
                    " FROM coverage, places" +
                    " WHERE coverage.place_id=places.id" +
                    "   AND places.%s=$self.id" % column +
                    " GROUP BY date ORDER BY date", vars=locals())
        return result.list()

    def daterange(self, start, end):
        date = start
        while date <= end:
            yield date
            date += datetime.timedelta(days=1)

    def get_coverge_summary(self):
        result = self.get_coverage_counts_by_date()
        d = dict((row.date, row.count) for row in result)

        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        thisweek = self.daterange(today-datetime.timedelta(days=6), today)

        return {
            "today": d.get(today, 0),
            "yesterday": d.get(yesterday, 0),
            "thisweek": sum(d.get(date, 0) for date in thisweek),
            "total": sum(d.values())
        }

    def prepare_data_for_graph(self, rows):
        """Expects each row to have date and count fields.
        """
        today = datetime.date.today()
        yday = today - datetime.timedelta(days=1)

        rows = rows or [web.storage(date=today, count=0)]

        mindate = min(rows[0].date, yday)
        maxdate = max(rows[-1].date, today)

        d = dict((row.date, row.count) for row in rows)
        x = []
        count = 0
        for date in self.daterange(mindate, maxdate):
            count += d.get(date, 0)
            x.append([time.mktime(date.timetuple()) * 1000, count])
        return x

    def get_coverage_data_for_graph(self):
        return self.prepare_data_for_graph(self.get_coverage_counts_by_date())

    def get_data(self, suffix=""):
        if suffix:
            key = self.key + "/" + suffix
        else:
            key = self.key
        row = self._get_data_row(key)
        data = row and json.loads(row.data) or {}
        return web.storage(data)

    def _get_data_row(self, key):
        result = get_db().select("things", where="key=$key", vars=locals())
        return result and result[0] or None

    def put_data(self, data, suffix="", type="place"):
        if suffix:
            key = self.key + "/" + suffix
        else:
            key = self.key

        row = self._get_data_row(key)
        if row:
            get_db().update("things", where="id=$row.id", data=json.dumps(data), vars=locals())
        else:
            get_db().insert("things", key=key, type=type, data=json.dumps(data))

    def get_links(self):
        return [web.storage(link) for link in self.get_data().get("links", [])]

    def save_links(self, links):
        data = self.get_data()
        data['links'] = links
        self.put_data(data)

    def get_signups(self):
        result = get_db().query(
            "SELECT volunteer_signups.* FROM volunteer_signups, places" +
            " WHERE places.id=volunteer_signups.place_id" +
            "   AND $self.id IN (places.id, places.ac_id, places.pc_id, places.region_id, places.state_id)"
            " ORDER BY added DESC", vars=locals())
        return [VolunteerSignup(row) for row in result]

    def get_localities(self):
        """Returns all the localities in this place.
        """
        data = self.get_data(suffix="localities")
        d = {
            "localities": data.get("localities", []),
            "pincodes": data.get("pincodes", [])
        }
        return web.storage(d)

    def set_localities(self, localities, pincodes):
        data = self.get_data(suffix="localities")
        data['localities'] = localities
        data['pincodes'] = pincodes
        self.put_data(data, suffix="localities")

    def get_all_localities(self):
        """Returna all localities in this subtree.
        """
        def process_row(row):
            key = row.key.replace("/localities", "")
            place = Place.find(key)
            data = json.loads(row.data)
            return {
                "code": place.code,
                "name": place.name,
                "ac": place.get_parent("AC").name,
                "pc": place.get_parent("AC").name,
                "localities": data.get("localities", []),
                "pincodes": data.get("pincodes", [])
            }
        key = self.key + '%/localities'
        rows = get_db().query("SELECT * FROM things WHERE key like $key", vars=locals()).list()
        return [process_row(row) for row in rows]

    def get_all_coordinators_as_dataset(self, types=['STATE', 'PC', 'AC', 'WARD']):
        result = get_db().query(
            "SELECT places.type, places.pc_id, places.ac_id, places.ward_id, places.name as place," +
            " people.name as coordinator, people.email, people.phone" +
            " FROM people, places" +
            " WHERE people.place_id=places.id AND role='coordinator' AND places.type IN $types" +
            " AND places.%s=$self.id" % self.type_column +
            " ORDER by place_id", vars=locals())
        rows = sorted(result, key=lambda row: (row.pc_id, row.ac_id, row.ward_id))
        for row in rows:
            row.pc = row.pc_id and Place.from_id(row.pc_id).name or "-"
            row.ac = row.ac_id and Place.from_id(row.ac_id).name or "-"
            row.ward = row.ward_id and Place.from_id(row.ward_id).name or "-"
            row[row.type.lower()] = row.place

        dataset = tablib.Dataset(headers=['Parliamentary Constituency', 'Assembly Constituency', 'Ward', 'Coordinator', 'email', 'phone'])
        for row in rows:
            dataset.append([row.pc, row.ac, row.ward, row.coordinator, row.email, row.phone])
        return dataset

class Person(web.storage):
    @property
    def place(self):
        return Place.from_id(self.place_id)

    def get_url(self):
        return self.place.get_url() + "/people/%d" % self.id

    def find_dups(self):
        if not self.email:
            return []
        else:
            result = get_db().select("people", where="id!=$id AND lower(email)=lower($email)", vars=self)
            return [Person(row) for row in result]

    def set_encrypted_password(self, password):
        self._update_auth(password=password)

    def get_encrypted_password(self):
        rows = get_db().query("SELECT * FROM auth WHERE email=$self.email", vars=locals())
        if rows:
            return rows[0].password

    def generate_reset_token(self):
        token = str(uuid.uuid4()).replace("-", "")
        self._update_auth(reset_token=token)
        return token

    def _update_auth(self, **kwargs):
        result = get_db().select("auth", where="email=$email", vars=self)
        if result:
            get_db().update("auth", where="email=$email", vars=self, **kwargs) 
        else:
            get_db().insert("auth", email=self.email, **kwargs)

    @staticmethod
    def find_from_reset_token(token):
        result = get_db().select("auth", where="reset_token=$token",vars=locals())
        if result:
            email = result[0].email
            return Person.find(email=email)

    @staticmethod
    def find(**kwargs):
        if 'email' in kwargs:
            kwargs["lower(email)"] = kwargs['email'].lower()
            del kwargs['email']
        result = get_db().where("people", **kwargs)
        if result:
            return Person(result[0])

    @staticmethod
    def find_by_id(id):
        result = get_db().select("people", where="id=$id", vars=locals())
        if result:
            return Person(result[0])

    def is_authorized(self):
        return True

    def update(self, values=None, **kwargs):
        if values:
            web.storage.update(self, values)
        web.storage.update(self, kwargs)

        # invalidate cache before and after as the place can change.
        self.place._invalidate_object_cache()
        get_db().update("people", where="id=$self.id", vars=locals(),
            place_id=self.place_id,
            name=self.name,
            email=self.email,
            phone=self.phone,
            voterid=self.voterid,
            role=self.role)
        self.place._invalidate_object_cache()

    def delete(self):
        db = get_db()
        place = self.place
        with db.transaction():
            db.update("coverage", editor_id=None, where="editor_id=$self.id", vars=locals())
            db.delete("activity", where="person_id=$self.id", vars=locals())
            db.delete("people", where="id=$self.id", vars=locals())
        place._invalidate_object_cache()

    def __repr__(self):           
        return "<Person: %s>" % dict(self)

class Activity(web.storage):
    def get_place(self):
        return Place.from_id(self.place_id)

    def get_person(self):
        return Person.find_by_id(self.person_id)

    def get_data(self):
        return web.storage(json.loads(self['data']))

    def get_volunteer(self):
        return Person.find_by_id(self.get_data()['volunteer_id'])

    def get_volunteer_name(self):
        return self.get_data()['volunteer_name']

    def get_coverage_count(self):
        return self.get_data()['count']

    @staticmethod
    def record(event_type, place_id, **kwargs):
        import account
        who = account.get_current_user()
        db = get_db()

        # don't worry about recording activity when run in batch mode
        if who:
            db.insert("activity", type=event_type, place_id=place_id, person_id=who.id, data=json.dumps(kwargs))

    def __repr__(self):           
        return "<Activity: %s>" % dict(self)


class DummyPerson(web.storage):
    def __init__(self, email):
        web.storage.__init__(self)
        self.name = None
        self.email = email
        self.id = None
        self.role = "none"
        self.place_id = None

    def is_authorized(self):
        return False

def get_all_coordinators_as_dataset(types=['STATE', 'PC', 'AC', 'WARD']):
    result = get_db().query(
                "SELECT places.type, places.code, places.name as place," +
                " people.name as coordinator, people.email, people.phone" +
                " FROM people, places" +
                " WHERE people.place_id=places.id AND role='coordinator' AND places.type in $types" +
                " ORDER by place_id", vars=locals())
    dataset = tablib.Dataset(headers=['type', 'place', 'coordinator', 'email', 'phone'])
    for row in result:
        dataset.append([row.type, row.place, row.coordinator, row.email, row.phone])
    return dataset

class VolunteerSignup(web.storage):
    def get_place(self):
        return Place.from_id(self.place_id)
