import xappy
import models
from web import config

def search(s, page=0):
    conn = xappy.SearchConnection(config.search_db)

    # disable spell corrector.
    # It was converting PB0119 to PB0019.

    #q = conn.query_parse(conn.spell_correct(s))
    q = conn.query_parse(s)

    result = conn.search(q, page*20, page*20+20)
    return result.matches_estimated, [models.Place.from_id(x.data['id']) for x in result]

def index():
    """Index entire database."""
    indexer = xappy.IndexerConnection(config.search_db)
    #indexer.add_field_action("id", xappy.FieldActions.STORE_CONTENT)
    indexer.add_field_action("name", xappy.FieldActions.INDEX_FREETEXT, spell=True)
    indexer.add_field_action("code", xappy.FieldActions.INDEX_EXACT)
    indexer.add_field_action("type", xappy.FieldActions.INDEX_EXACT)
    indexer.add_field_action("url", xappy.FieldActions.INDEX_EXACT)

    def add_field(doc, k, v):
        doc.fields.append(xappy.Field(k, v))

    def add_to_index(place):
        print "indexing", place.url
        doc = xappy.UnprocessedDocument()
        doc.id = place.url
        add_field(doc, "name", place.name)
        add_field(doc, "type", place.type)
        add_field(doc, "url", place.type)
        doc = indexer.process(doc)
        doc.data = {"id": place.id}
        indexer.replace(doc)

    places = models.Place.find_all()
    for p in places:
        add_to_index(p)

    indexer.flush()
    indexer.close()

if __name__ == "__main__":
    import sys
    import webapp
    webapp.load_config(sys.argv[1])
    if len(sys.argv) > 2:
        matches, result = search(sys.argv[2])
        print matches, "matches"
        for d in result:
            print repr(d)
    else:
        index()