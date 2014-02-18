import web
import re
import json
import cache
import time, datetime
import tablib

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
        PC="Parliamentary Constituency",
        AC="Assembly Constituency",
        WARD="Ward",
        PS="Polling Station",
        PB="Polling Booth")

    TYPES = ['STATE', 'PC', 'AC', 'WARD', 'PB']

    @property
    def url(self):
        return self.get_url()

    def get_url(self):
        if self.type in ['STATE', 'PC', 'AC']:            
            return "/" + self.code
        else:
            return self.get_ac().url + "/" + self.code

    @property
    def parent(self):
        if self.type != 'STATE':
            # quick fix to handle PollingBooths not assigned to any ward
            if self.type == 'PB' and self.ward_id is None:
                parent_id = self.ac_id
            else:
                parent_id = self[self.parent_column]
            return parent_id and Place.from_id(parent_id)

    def get_ac(self):
        return Place.from_id(self.ac_id)

    def get_parents(self):
        parent = self.parent
        if self.type == 'STATE' or not parent:
            return []
        return self.parent.get_parents() + [self.parent]

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
        cache.invalidate_cache("Place.find", self.code)
        cache.invalidate_cache("Place.find", code=self.code)

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

    def get_places(self):
        db = get_db()
        id = self.id
        subtype = self.subtype
        column = self.type_column
        result = db.select("places", where="%s=$id and type=$subtype" % column, order="code", vars=locals())
        return [Place(row) for row in result]

    def get_places_text(self):
        return "\n".join(str(p) for p in self.get_places())

    def __str__(self):
        return "%s {{ %s }}" % (self.name, self.code)

    def add_places(self, places_text):
        lines = places_text.strip().splitlines()
        rows = [self.process_place_line(line) for line in lines]

        # We may need to generate codes for new entries. 
        # We should make sure the generated code should be already used.
        existing_codes = set(place.code for place in self.get_places())
        codeset = set(existing_codes)

        def generate_code(name):
            code = normalize(name)[:20]
            count = 1
            while code in codeset:
                code = normalize(name)[:20] + str(count)
                count += 1
            codeset.add(code)
            print "generate_code", repr(name), repr(code)
            return code

        db = get_db()
        with db.transaction():
            for row in rows:
                if row.code is None:
                    row.code = generate_code(row.name)
                row.type = self.subtype
                row.parent_id = self.id

                row.state_id = self.state_id
                row.pc_id = self.pc_id
                row.ac_id = self.ac_id
                row.ward_id = self.ward_id
                row.ps_id = self.ps_id

                # sent the parent id in the apprpriate field
                row[self.type.lower() + "_id"] = self.id

                if row.code in existing_codes:
                    db.update("places", name=row.name, where="code=$code AND type=$type AND parent_id=parent_id", vars=row)
                else:
                    db.insert("places", **row)

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

    @staticmethod
    @cache.memoize(key="Place.find")
    def find(code):
        db = get_db()
        if "/" in code:
            parts = code.split("/")
            place = Place.find(parts[0])
            for p in parts[1:]:
                place = place and place._find_subplace(p)
            return place
        else:
            result = db.select("places", where="code=$code AND type IN ('STATE', 'PC', 'AC')", vars=locals())
        if result:
            return Place(result[0])

    @staticmethod
    def find_all():
        db = get_db()
        return [Place(row) for row in db.select("places")]

    @staticmethod
    @cache.memoize
    def from_id(id):
        db = get_db()
        result = db.select("places", where="id=$id", vars=locals())
        if result:
            return Place(result[0]) 

    def __repr__(self):           
        return "<Place: %s>" % dict(self)

    def writable_by(self, user, roles=['coordinator', 'admin']):
        place_ids = [self.id, self.state_id, self.pc_id, self.ac_id, self.ward_id]
        result = get_db().query("SELECT * FROM people" +
            " WHERE lower(email)=lower($user.email)" +
            "   AND place_id in $place_ids" +
            "   AND role IN $roles", vars=locals())
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

    def get_activity(self, offset=0, limit=100):
        if self.type == 'PB':
            where = "places.id=$self.id"
        else:
            where = "(places.id=$self.id OR places.%s=$self.id)" % self.type_column
        result = get_db().query(
            "SELECT activity.*" +
            " FROM activity, places" + 
            " WHERE activity.place_id=places.id AND " + where +
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

    def get_coverage_data_for_graph(self):
        today = datetime.date.today()
        yday = today - datetime.timedelta(days=1)

        result = self.get_coverage_counts_by_date() or [web.storage(date=today, count=0)]

        mindate = min(result[0].date, yday)
        maxdate = max(result[-1].date, today)

        d = dict((row.date, row.count) for row in result)

        x = []
        count = 0
        for date in self.daterange(mindate, maxdate):
            count += d.get(date, 0)
            x.append([time.mktime(date.timetuple()) * 1000, count])
        return x

    def get_data(self, suffix=""):
        if suffix:
            key = self.code + "/" + suffix
        else:
            key = self.code
        row = self._get_data_row(key)
        data = row and json.loads(row.data) or {}
        return web.storage(data)

    def _get_data_row(self, key):
        result = get_db().select("things", where="key=$key", vars=locals())
        return result and result[0] or None

    def put_data(self, data, suffix="", type="place"):
        if suffix:
            key = self.code + "/" + suffix
        else:
            key = self.code

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

    def update(self, values):
        web.storage.update(self, values)
        # update cache before and after as the place can change.

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
