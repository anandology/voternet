import web

@web.memoize
def get_db():
    params = web.config.get("db_parameters") or dict(dbn="postgres", db="voternet")
    return web.database(**params)

class Place(object):
    TYPE_LABELS = dict(
        state="State",
        pc="Parliamentary Constituency",
        ac="Assembly Constituency",
        ward="Ward",
        ps="Polling Station",
        pb="Polling Booth")

    def __init__(self, row):
        self.row = row

        self.id = self.row.id
        self.name = row.name
        self.code = row.code
        self.type = row.type
        self.type_label = self.TYPE_LABELS[self.type.lower()]

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
