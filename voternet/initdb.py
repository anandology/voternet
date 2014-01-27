from models import get_db, Place
import os

def add_places(parent):
    path = "places" + parent.get_url() + ".txt"
    if os.path.exists(path):
        print "loading places from", path
        parent.add_places(open(path).read())
        for p in parent.get_places():
            add_places(p)

def main():
    db = get_db()
    db.insert("places", name="Karnataka", type="STATE", code="karnataka", parent_id=None)
    state = Place.find("karnataka")
    add_places(state)

if __name__ == '__main__':
    main()