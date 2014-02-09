import web
import re
import json

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
        return Place.from_id(self[self.parent_column])

    def get_ac(self):
        return Place.from_id(self.ac_id)

    def get_parents(self):
        if self.type == 'STATE':
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

    def add_volunteer(self, name, email, phone, voterid=None, role=None):
        get_db().insert("people", name=name, email=email, phone=phone, voterid=voterid, role=role, place_id=self.id, )

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

    def delete(self):
        db = get_db()
        with db.transaction():
            db.query("DELETE FROM people USING places"
                + " WHERE place_id=places.id"
                + "     AND (places.id=$self.id OR places.%s=$self.id)" % self.type_column,
                vars=locals())
            db.query("DELETE FROM places WHERE id=$self.id OR %s=$self.id" % self.type_column, vars=locals())

    def get_all_subtypes(self):
        index = self.TYPES.index(self.type)
        return [web.storage(code=type, label=self.TYPE_LABELS[type]) for type in self.TYPES[index+1:]]

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

    def get_counts(self):
        if self.type != "PB":
            result = get_db().query(
                "SELECT type, count(*) as count" +
                " FROM places" +
                " WHERE %s=$self.id OR id=$self.id"  % self.type_column +
                " GROUP BY type", vars=locals())
            return dict((row.type, row.count) for row in result)
        return dict()

    def get_volunteer_counts(self):
        if self.type != "PB":
            result = get_db().query(
                "SELECT type, count(*) as count" +
                " FROM places" +
                " JOIN people ON places.id=people.place_id" +
                " WHERE %s=$self.id OR places.id=$self.id" % self.type_column + 
                " GROUP BY type", vars=locals())
            return dict((row.type, row.count) for row in result)
        return dict()

    @staticmethod
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
    def from_id(id):
        db = get_db()
        result = db.select("places", where="id=$id", vars=locals())
        if result:
            return Place(result[0]) 

    def __repr__(self):           
        return "<Place: %s>" % dict(self)

    def writable_by(self, user, roles=['coordinator', 'admin']):
        place_ids = [self.id, self.state_id, self.pc_id, self.ac_id, self.ward_id]
        return user and user.role in roles and user.place_id in place_ids

    def add_coverage(self, date, coverage):
        db = get_db()
        coverage_json = json.dumps(coverage)
        with db.transaction():
            db.delete("coverage", where="place_id=$self.id AND date=$date", vars=locals())
            db.insert("coverage", place_id=self.id, date=date, data=coverage_json)

    def get_coverage(self, date):
        result = get_db().select("coverage", where="place_id=$self.id AND date=$date", vars=locals())
        if result:
            return json.loads(result[0].data)
        else:
            return []

class Person(web.storage):
    @property
    def place(self):
        return Place.from_id(self.place_id)

    def get_url(self):
        return "/people/%d" % self.id

    @staticmethod
    def find(**kwargs):
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

    def __repr__(self):           
        return "<Person: %s>" % dict(self)

class DummyPerson(web.storage):
    def __init__(self, email):
        web.storage.__init__(self)
        self.email = email
        self.id = None
        self.role = "none"
        self.place_id = None

    def is_authorized(self):
        return False