import web

@web.memoize
def get_db():
    params = web.config.get("db_parameters") or dict(dbn="postgres", db="voternet")
    return web.database(**params)

class Place(web.storage):
    TYPE_LABELS = dict(
        state="State",
        pc="Parliamentary Constituency",
        ac="Assembly Constituency",
        ward="Ward",
        ps="Polling Station",
        pb="Polling Booth")

    @property
    def volunteers(self):
        result = get_db().select("people", where="place_id=$place_id", vars={"place_id": self.id})
        return [Place(row) for row in result]

    def add_volunteer(self, name, email, phone):
        get_db().insert("people", name=name, email=email, phone=phone, place_id=self.id)

    @property
    def type_label(self):
        return self.TYPE_LABELS[self.type.lower()]


    def get_places(self):
        db = get_db()
        id = self.id
        result = db.select("place", where="parent_id=$id", vars=locals())
        return [Place(row) for row in result]

    @staticmethod
    def find(code):
        db = get_db()
        result = db.select("place", where="code=$code", vars=locals())
        if result:
            return Place(result[0])

    @staticmethod
    def from_id(id):
        db = get_db()
        result = db.select("place", where="id=$id", vars=locals())
        if result:
            return Place(result[0])            

class Person(web.storage):
    @property
    def place(self):
        return Place.from_id(self.place_id)
