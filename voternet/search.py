import xappy
import models
from web import config

def search(s, page=0):
    conn = xappy.SearchConnection(config.search_db)
    q = conn.query_parse(conn.spell_correct(s))
    result = conn.search(q, page*20, page*20+20)
    return result.matches_estimated, [x.data for x in result]

def index():
    """Index entire database."""
    indexer = xappy.IndexerConnection(config.search_db)
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
        print sorted(d.name for d in search(sys.argv[2]))
    else:
        index()