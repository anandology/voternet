import web
import re
import json
import cache
import time, datetime
import tablib
import uuid
import voterlib
import hmac
import logging

logger = logging.getLogger(__name__)

@web.memoize
def get_db():
    params = web.config.get("db_parameters") or dict(dbn="postgres", db="voternet")
    return web.database(**params)

@web.memoize
def get_voter_db():
    if web.config.get("voterdb"):
        return web.database(**web.config.voterdb)
    else:
        return get_db()

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
        PX="Polling Center",
        PB="Polling Booth")

    TYPES = ['STATE', 'REGION', 'PC', 'AC', 'WARD', 'PX', 'PB']

    CODE_PREFIXES = {
        "STATE": "",
        "REGION": "R",
        "PC": "PC",
        "AC": "AC",
        "WARD": "W",
        "PX": "PX",
        "PB": "PB"
    }

    COLUMN_NAMES = dict(STATE="state_id", REGION="region_id", PC="pc_id", AC="ac_id", WARD="ward_id", PX="px_id")

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

    def get_children(self, type):
        rows = get_db().query("SELECT * FROM places WHERE type=$type AND {0} = $self.id ORDER BY key".format(self.type_column), vars=locals())
        return [Place(row) for row in rows]

    @property
    def volunteers(self):
        return self.get_people(['coordinator', 'volunteer', 'pb_agent', 'px_agent', 'member', 'active_member'])

    def get_people(self, roles):
        result = get_db().select("people",
            where="place_id=$place_id AND role IN $roles",
            order='role, id',
            vars={"place_id": self.id, "roles": roles})
        return [Person(row) for row in result]

    def get_pb_agents(self):
        return self.get_all_volunteers("pb_agent")

    def get_all_volunteers(self, role="volunteer", notes=None, email=None):
        """Returns all volunteers in the sub tree.
        """
        where = ""
        if isinstance(role, list):
            where += " AND people.role IN $role"
        else:
            where += " AND people.role = $role"

        if notes:
            if isinstance(notes, list):
                where += " AND notes IN $notes"
            else:
                where += " AND notes=$notes"

        if email:
            where += " AND email=$email"

        result = get_db().query(
            "SELECT people.* FROM people, places" + 
            " WHERE people.place_id=places.id" + 
            where +
            "   AND (places.id=$self.id OR places.{0} = $self.id)".format(self.type_column),
            vars=locals())
        return [Person(row) for row in result]

    @cache.object_memoize(key="coordinators")
    def get_coordinators(self):
        return self.get_people(["coordinator"])

    def add_volunteer(self, name, email, phone, voterid=None, role=None, notes=None):
        person_id = get_db().insert("people", 
            place_id=self.id, 
            name=name,
            email=email,
            phone=phone,
            voterid=voterid,
            role=role, 
            notes=notes)
        self._invalidate_object_cache()
        logger.info("Added %s <%s> as %s to %s", name, email, role, self.key)
        self.record_activity("volunteer-added", volunteer_id=person_id, name=name, role=role)
        person = Person.find_by_id(person_id)
        if voterid:
            person.populate_voterid_info()
        return person

    def add_invite(self, name, email, phone, batch=None):
        get_db().insert("invite", 
                    place_id=self.id, 
                    name=name,
                    email=email,
                    phone=phone,
                    batch=batch)

    def find_volunteer(self, email, phone, role):
        where = {}
        if email:
            where['email'] = email
        if phone:
            where['phone'] = phone
        rows = get_db().where("people", place_id=self.id, role=role, limit=1, **where)
        if rows:
            return Person.find_by_id(rows[0].id)

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
        if self.type == "PB":
            return "id"
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
        if self.type == "PB":
            px = self.get_parent("PX")
            px and px.autoupdate_ward()

    def set_px(self, px):
        self.px_id = px and px.id
        get_db().update("places", px_id=self.px_id, where="id=$self.id", vars=locals())
        self._invalidate_object_cache()
        px = self.get_parent("PX")
        px and px.autoupdate_ward()

    def autoupdate_ward(self):
        d = {}
        for pb in self.get_children("PB"):
            ward = pb.get_parent("WARD")
            if ward:
                d[ward.key] = d.get(ward.key, 0) + 1
        if d:
            top_ward = max(d, key=d.__getitem__)
            self.set_ward(Place.find(top_ward))

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
            px_id=self.px_id,
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

    @cache.object_memoize(key="agent_counts")
    def get_agent_counts(self):
        if self.type == "PB":
            where = "places.id=$self.id"
        else:
            where = "(places.%s=$self.id OR places.id=$self.id)" % self.type_column

        # find total agents
        result = get_db().query(
            "SELECT count(*) as count FROM people, places" +
            " WHERE people.role='pb_agent'" + 
            "   AND people.place_id=places.id" +
            "   AND " + where, 
            vars=locals())
        total = result[0].count

        # find confirmed agents
        result = get_db().query(
            "SELECT count(*) as agents, count(distinct places.id) as booths FROM people" +
            " JOIN voterid_info ON voterid_info.voterid=people.voterid" +
            " JOIN places ON places.id=people.place_id" +
            " WHERE people.role='pb_agent' and places.type='PB'" +
            "   AND " + where, 
            vars=locals())
        row = result[0]
        confirmed = row.agents
        confirmed_booths = row.booths
        pending = total-confirmed
        return web.storage(total=total, confirmed=confirmed, confirmed_booths=confirmed_booths, pending=pending)

    #@cache.object_memoize(key="agent_counts2")
    def get_agent_counts2(self):
        total_pb_agents, _ = self._get_agent_counts("pb_agent")
        assigned_pb_agents, assigned_booths = self._get_agent_counts("pb_agent", 'PB')

        total_px_agents, _ = self._get_agent_counts("px_agent")
        assigned_px_agents, assigned_centers = self._get_agent_counts("px_agent", 'PX')

        ward_coordinators, assigned_wards = self._get_agent_counts('coordinator', 'WARD')

        return web.storage({
            "assigned_pb_agents": assigned_pb_agents,
            "assigned_pbs": assigned_booths,
            "unassigned_pb_agents": total_pb_agents - assigned_pb_agents,
            "assigned_px_agents": assigned_px_agents,
            "unassigned_px_agents": total_px_agents - assigned_px_agents,            
            "assigned_pxs": assigned_centers,
            "assigned_pxs_including_pbs": self._get_px_count(),

            "assigned_ward_coordinators": ward_coordinators,
            "assigned_wards": assigned_wards,
        })

    def _get_agent_counts(self, role, place_type=None):
        where = "(places.%s=$self.id OR places.id=$self.id)" % self.type_column
        if place_type:
            where += " AND places.type=$place_type"
        if isinstance(role, list):
            where += " AND people.role IN $role"
        else:
            where += " AND people.role = $role"
        result = get_db().query(
            "SELECT count(*) as count, count(distinct places.id) as place_count, count(distinct places.px_id) as px_count FROM people, places" +
            " WHERE people.place_id=places.id" +
            "   AND " + where, 
            vars=locals())
        row = result[0]
        return row.count, row.place_count

    def _get_px_count(self):
        """When counting PX agents, we count both PB agents and PX agents.
        """
        q1 = ("SELECT places.id FROM places, people" +
            " WHERE people.place_id=places.id" +
            "   AND people.role='px_agent'" + 
            "   AND places.type='PX'" +
            "   AND (places.{}=$self.id OR places.id=$self.id)".format(self.type_column)) 

        q2 = ("SELECT places.px_id FROM places, people" +
            " WHERE people.place_id=places.id" +
            "   AND people.role='pb_agent'" + 
            "   AND places.type='PB'" +
            "   AND (places.{}=$self.id OR places.id=$self.id)".format(self.type_column)) 

        q =  "SELECT count(*) FROM ({} UNION {}) as t".format(q1, q2)
        result = get_db().query(q, vars=locals())
        row = result[0]
        return row.count

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
        if not user:
            return False
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
        if not user:
            return False
        # super admins can view any page.
        if user.email in web.config.get('super_admins', []):
            return True

        # If they can write, then can view as well.
        if self.writable_by(user, roles=['coordinator', 'admin', 'user']):
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
            types = ['volunteer-added', 'coverage-added', 'voterid-added']
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

    def get_messages(self, limit=5):
        places = [self] + self.get_parents()
        place_ids = [p.id for p in places]
        return Message.find(place_id=place_ids, limit=limit)

    def find_message(self, id):
        m = Message.by_id(id)
        if m and m.place_id == self.id:
            return m

    def post_message(self, message, author):
        return Message.create(place=self, author=author, message=message)

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

    def get_thing(self, _key):
        key = self.key + "/" + _key
        return Thing.find(key)

    def new_thing(self, _key, type='thing', **kw):
        key = self.key + "/" + _key
        return Thing(key=key, type=type, **kw)

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
        def process_ward(w):
            d = w.get_localities()
            return {
                "key": w.key,
                "name": w.name,
                "ac": w.get_parent("AC").name,
                "pc": w.get_parent("PC").name,
                "localities": d.get('localities') or [w.name.split("-")[-1].strip()],
                "pincodes": d.get('pincodes', [])
            }
        wards = self.get_places(type="WARD")            
        return [process_ward(w) for w in wards]

    def get_all_coordinators_as_dataset(self, types=['STATE', 'REGION', 'PC', 'AC', 'WARD']):
        return self.get_all_volunteers_as_dataset(roles=['coordinator'], types=types)

    def get_all_volunteers_as_dataset(self, roles=['volunteer', 'pb_agent', 'px_agent', 'coordinator', 'member', 'active_member'], types=['STATE', 'REGION', 'PC', 'AC', 'WARD', 'PB', 'PX']):
        result = get_db().query(
            "SELECT places.type, places.pc_id, places.ac_id, places.ward_id, places.name as place," +
            " people.name as name, people.email, people.phone, people.voterid, people.role" +
            " FROM people, places" +
            " WHERE people.place_id=places.id AND role IN $roles AND places.type IN $types" +
            " AND (places.%s=$self.id or places.id=$self.id)" % self.type_column +
            " ORDER by place_id", vars=locals())
        rows = sorted(result, key=lambda row: (row.pc_id, row.ac_id, row.ward_id))
        for row in rows:
            row.pc = row.pc_id and Place.from_id(row.pc_id).name or "-"
            row.ac = row.ac_id and Place.from_id(row.ac_id).name or "-"
            row.ward = row.ward_id and Place.from_id(row.ward_id).name or "-"
            row.ward = row.ward_id and Place.from_id(row.ward_id).name or "-"
            row.pb = "-"
            row[row.type.lower()] = row.place

        dataset = tablib.Dataset(headers=['Name', 'E-Mail', 'Phone', 'Voter ID', 'Role', 'Polling Booth', 'Ward', 'Assembly Constituency', 'Parliamentary Constituency'])
        for row in rows:
            dataset.append([row.name, row.email, row.phone, row.voterid, row.role, row.pb, row.ward, row.ac, row.pc])
        return dataset

def get_voterid_details(voterid, fetch=False):
    if voterid:
        rows = get_db().query("SELECT * FROM voterid_info where voterid=$voterid", vars=locals())
        if rows:
            return rows[0]
        if fetch:
            d = voterlib.get_voter_details(voterid)
            if d:
                key = "KA/AC{0:03d}/PB{1:04d}".format(int(d.ac_num), int(d.part_no))
                d.pb_id = Place.find(key).id
                get_db().insert("voterid_info", **d)
                return d

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

    def get_voterid_info(self):
        return get_voterid_details(self.voterid)

    def populate_voterid_info(self):
        d = self.get_voterid_info()
        if self.voterid and not d:
            d = voterlib.get_voter_details(self.voterid)
            # The voter ID might have been added while we are fetching the voter details.
            # Usually happens when user press save button twice.
            if d and not self.get_voterid_info():
                key = "KA/AC{0:03d}/PB{1:04d}".format(int(d.ac_num), int(d.part_no))
                d.pb_id = Place.find(key).id
                get_db().insert("voterid_info", **d)
        if d and d.get('pb_id') and self.role == "pb_agent" and self.place_id != d.pb_id:
            self.update(place_id=d.pb_id)
            logger.info("Reassigned %s <%s> as %s to %s", self.name, self.email, self.role, self.place.key)

    def get_agent_status(self):
        """Return one of [None, "pending", "verified", mismatch"].
        """
        if self.role == "pb_agent":
            d = self.get_voterid_info()
            if not d:
                return "pending"
            elif d.pb_id == self.place_id:
                return "verified"
            else:
                return "mismatch"

    def get_pb(self):
        d = self.get_voterid_info()
        return d and Place.from_id(d.pb_id)

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

    def get_edit_token(self):
        msg = "{} {} {}".format(self.id, self.email, self.phone)
        h = hmac.HMAC(web.config.secret_key, msg).hexdigest()
        return "{}-{}".format(self.id, h)

    @staticmethod
    def find_by_edit_token(token):
        try:
            person_id = int(token.split("-")[0])
        except ValueError:
            return
        person = Person.find_by_id(person_id)
        if person and person.get_edit_token() == token:
            return person

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
            roles = {
                'admin': 0,
                'coordinator': 1,
                'volunteer': 2
            }
            # Pick the high-ranked role when the person has multiple roles.
            result = sorted(result, key=lambda p: roles.get(p['role'], 100))
            return Person(result[0])

    @staticmethod
    def find_by_id(id):
        result = get_db().select("people", where="id=$id", vars=locals())
        if result:
            return Person(result[0])

    def is_authorized(self):
        return True

    def update(self, values=None, **kwargs):
        old_self = Person(self)
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
        if self.voterid and old_self.voterid != self.voterid:
            self.place.record_activity("voterid-added", volunteer_id=self.id, voterid=self.voterid)
        if old_self.place_id != self.place.id:
            old_self.place._invalidate_object_cache()
        self.populate_voterid_info()

    def delete(self):
        db = get_db()
        place = self.place
        with db.transaction():
            db.update("coverage", editor_id=None, where="editor_id=$self.id", vars=locals())
            db.delete("activity", where="person_id=$self.id", vars=locals())
            db.delete("invite", where="person_id=$self.id", vars=locals())
            db.delete("people", where="id=$self.id", vars=locals())
        place._invalidate_object_cache()

    def dict(self):
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "voterid": self.voterid,
            "role": self.role,
            "place": self.place.key,
            "place_type": self.place.type,
        }

    def __repr__(self):           
        return "<Person: %s>" % dict(self)

class Message(web.storage):
    @property
    def place(self):
        return Place.from_id(self.place_id)

    @property
    def author(self):
        return Person.find_by_id(self.author_id)

    @property
    def url(self):
        return "{}/messages/{}".format(self.place.url, self.id) 

    @staticmethod
    def create(place, author, message):
        d = {
            "place_id": place.id,
            "author_id": author.id,
            "message": message
        }
        message_id = get_db().insert("messages", **d)
        return Message.find(message_id)

    @staticmethod
    def find(place_id=None, limit=10):
        wheres = []
        if place_id and isinstance(place_id, list):
            wheres.append("place_id IN $place_id")
        else:
            wheres.append("place_id = $place_id")

        where = " AND ".join(wheres)
        result = get_db().select("messages", where=where, order="tstamp desc", vars=locals())
        return [Message(row) for row in result]

    @staticmethod
    def by_id(message_id):
        result = get_db().select("messages", where="id=$message_id", vars=locals())
        if result:
            return Message(result[0])

class Activity(web.storage):
    def get_place(self):
        return Place.from_id(self.place_id)

    def get_person(self):
        return Person.find_by_id(self.person_id)

    def get_data(self):
        return web.storage(json.loads(self['data']))

    def get_volunteer(self):
        vid = self.get_data().get("volunteer_id")
        return vid and Person.find_by_id(vid)

    def get_volunteer_name(self):
        return self.get_data()['volunteer_name']

    def get_coverage_count(self):
        return self.get_data()['count']

    @staticmethod
    def record(event_type, place_id, **kwargs):
        import account
        who = account.get_current_user()
        who_id = who and who.id

        get_db().insert("activity", 
            type=event_type, 
            place_id=place_id, 
            person_id=who_id, 
            data=json.dumps(kwargs))

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

class Thing(web.storage):
    @staticmethod
    def find(key):
        result = get_db().select("things", where="key=$key", vars=locals())
        if result:
            row = result[0]
            d = json.loads(row['data'])
            d['key'] = key
            d['id'] = row.id
            return Thing(d)

    @property
    def jsondata(self):
        d = dict(self)
        d.pop('id', None)
        return json.dumps(d)

    def exists(self):
        return self.get("id") is not None

    def save(self):
        if self.exists():
            get_db().update("things", where="id=$id", data=self.jsondata, vars=self)
        else:
            get_db().insert("things", key=self.key, type=self.type, data=self.jsondata)

class Invite(web.storage):
    @property
    def place(self):
        return Place.from_id(self.place_id)

    @property
    def person(self):
        return self.person_id and Person.find_by_id(self.person_id)

    @property
    def role(self):
        """This is required to make Invite work like person when sending emails.
        """
        return "pb_agent"

    def get_url(self):
        # to indicate that this is not a real volunteer
        return None

    @staticmethod
    def find(id):
        """Return person by id.
        """
        result = get_db().where("invite", id=id)
        if result:
            return Invite(result[0])

    @staticmethod
    def find_by_email(email):
        """Return person by id.
        """
        result = get_db().where("invite", email=email)
        if result:
            return Invite(result[0])

    @staticmethod
    def find_all():
        result = get_db().query("SELECT * FROM invite WHERE person_id is NULL")
        return [Invite(row) for row in result]

    def digest(self):
        msg = "{} {}".format(self.id, self.email)
        return hmac.HMAC(web.config.secret_key, msg).hexdigest()

    def get_signup_token(self):
        return "{}-{}".format(self.id, self.digest())

    def add_person_id(self, person_id):
        get_db().update("invite", person_id=person_id, where="id=$id", vars=self)

    def signup(self, name, email, phone, voterid):
        place = self.place
        voterid_details = voterid and get_voterid_details(voterid)
        with get_db().transaction():
            agent = place.find_volunteer(email, phone, 'pb_agent')
            if not agent and voterid_details:
                p2 = Place.from_id(voterid_details.pb_id)
                agent = p2.find_volunteer(email, phone, 'pb_agent')
            if agent:
                if voterid and not agent.voterid:
                    agent.update(voterid=voterid)
            else:
                agent = place.add_volunteer(
                    name=name,
                    phone=phone,
                    email=email,
                    voterid=voterid,
                    role='pb_agent',
                    notes=self.batch)
            self.add_person_id(agent.id)
            agent.populate_voterid_info()
            return agent

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, dict(self))


class Voter(web.storage):
    @staticmethod
    def find(voterid):
        result = get_voter_db().where("voter", voterid=voterid.upper())
        if result:
            row = result[0]
            if row.data:
                data = json.loads(row.data)
                return Voter(data, ac=row.ac, part=row.part)
        # elif len(voterid) == 10:
        #     d = get_voterid_details(voterid, fetch=True)
        #     if d:
        #         d2 = {
        #             "name": d.get("first_name", "") + " " + d.get("last_name", ""),
        #             "relname": d.get("rel_firstname", "") + " " + d.get("rel_lastname", ""),
        #             "ac": int(d.ac_num),
        #             "part": int(d.part_no),
        #             "srno": int(d.sl_no),
        #             "age_sex": "{}/{}".format(d.sex, d.age)
        #         }
        #         return Voter(d2)

    @property
    def ac_name(self):
        key = "UP/AC{:03d}".format(self.ac)
        return Place.find(key).name

    @property
    def booth_name(self):
        key = "UP/AC{:03d}/PB{:04d}".format(self.ac, self.part)
        return Place.find(key).name.split("-", 1)[-1]

class SendMailBatch(web.storage):
    @staticmethod
    def find(id):
        result = get_db().where("sendmail_batch", id=id)
        if result:
            return SendMailBatch(result[0])

    @staticmethod
    def new(from_address, subject, message, notes=""):
        id = get_db().insert("sendmail_batch",
            from_address=from_address,
            subject=subject,
            message=message,
            notes=notes)
        return SendMailBatch.find(id)

    def add_people(self, people):
        # remove dups by putting them in a dict
        people_dict = dict((p.email, p) for p in people if p.email)
        people = people_dict.values()

        values = [{"batch_id": self.id, "to_address": p.email, "name": p.name} for p in people]
        get_db().multiple_insert("sendmail_message", values)

    def get_messages(self, status="pending"):
        rows = get_db().query(
            "SELECT * FROM sendmail_message" +
            " WHERE batch_id=$self.id AND status=$status",
            vars=locals())
        return [SendMailMessage(row) for row in rows]

    def get_stats(self):
        result = get_db().query(
            "SELECT status, count(*) as count" +
            " FROM sendmail_message" +
            " WHERE batch_id=$id " +
            " GROUP BY status",
            vars=self)
        stats = web.storage((row.status, row.count) for row in result)
        stats.total = sum(stats.values())
        return stats

class SendMailMessage(web.storage):
    def set_status(self, status):
        get_db().update("sendmail_message", where="id=$id", status=status, vars=self)
        self.status = status
