import web
import re

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

    TYPES = ['STATE', 'PC', 'AC', 'WARD', 'PS', 'PB']

    @property
    def url(self):
        return self.get_url()

    def get_url(self):
        if self.type in ['STATE', 'PC', 'AC']:            
            return "/" + self.code
        else:
            return self.parent.url + "/" + self.code

    @property
    def parent(self):
        return Place.from_id(self.parent_id)

    @property
    def volunteers(self):
        result = get_db().select("people", where="place_id=$place_id", vars={"place_id": self.id})
        return [Place(row) for row in result]

    def add_volunteer(self, name, email, phone):
        get_db().insert("people", name=name, email=email, phone=phone, place_id=self.id)

    @property
    def type_label(self):
        return self.TYPE_LABELS[self.type]

    @property
    def type_column(self):
        return self.type.lower() + "_id"

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

    def get_all_subtypes(self):
        index = self.TYPES.index(self.type)
        return [web.storage(code=type, label=self.TYPE_LABELS[type]) for type in self.TYPES[index+1:]]

    def get_places(self):
        db = get_db()
        id = self.id
        result = db.select("places", where="parent_id=$id", vars=locals())
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
            result = get_db().query("SELECT type, count(*) as count FROM places WHERE %s=$self.id GROUP BY type" % self.type_column, vars=locals())
            return dict((row.type, row.count) for row in result)
        return dict()

    def get_volunteer_counts(self):
        if self.type != "PB":
            result = get_db().query(
                "SELECT type, count(*) as count" +
                " FROM places" +
                " JOIN people ON places.id=people.place_id" +
                " WHERE %s=$self.id" % self.type_column + 
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

class Person(web.storage):
    @property
    def place(self):
        return Place.from_id(self.place_id)

    def __repr__(self):           
        return "<Person: %s>" % dict(self)
