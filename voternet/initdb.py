from models import get_db, Place
import os
import web

db = get_db()

def add_places(parent):
    path = "places" + parent.get_url() + ".txt"
    if os.path.exists(path):
        print "loading places from", path
        parent.add_places(open(path).read())
        for p in parent.get_places():
            add_places(p)

@web.memoize
def get_pc(code):
    return db.select("places", where="type='PC' AND code=$code", vars=locals())[0]

@web.memoize
def get_ac(code):
    return db.select("places", where="type='AC' AND code=$code", vars=locals())[0]

@web.memoize
def get_ward(ac_id, code):
    return db.select("places", where="type='WARD' AND ac_id=$ac_id AND code=$code", vars=locals())[0]

def add_acs(state):
    for line in open("places/ac.txt"):
        pc, ac, name = line.strip("\n").split(" - ", 2)
        name = ac + " - " + name
        if not db.select("places", where="type='AC' AND code=$ac", vars=locals()):
            parent = get_pc(pc)
            db.insert("places", name=name, type="AC", code=ac, parent_id=parent.id, state_id=state.id, pc_id=parent.id)

def add_pcs(state):
    for line in open("places/pc.txt"):
        name = line.strip("\n")
        code = name.split("-")[0].strip()
        if not db.select("places", where="type='PC' AND code=$code", vars=locals()):
            db.insert("places", name=name, type="PC", code=code, parent_id=state.id, state_id=state.id)

def add_wards(state):
    for line in open("places/wards.txt"):
        pc, ac, code, name = line.strip("\n").split("\t")
        name = code + " - " + name
        parent = get_ac(ac)
        if not db.select("places", where="type='WARD' AND parent_id=$parent.id AND code=$code", vars=locals()):
            ac_id = parent.id
            pc_id = get_pc(pc).id
            db.insert("places", name=name, type="WARD", code=code, 
                parent_id=parent.id,
                state_id=state.id,
                pc_id=pc_id,
                ac_id=ac_id)

def add_polling_booths(state):
    for line in open("places/polling_booths.txt"):
        pc, ac, ward, code, name = line.strip("\n").split("\t")
        name = code + " - " + name

        pc_id = get_pc(pc).id
        ac_id = get_ac(ac).id
        if ward:
            ward_id = get_ward(ac_id, ward).id
        else:
            ward_id = None

        if not db.select("places", where="type='PB' AND ac_id=$ac_id AND code=$code", vars=locals()):
            db.insert("places", name=name, type="PB", code=code, 
                parent_id=ac_id,
                state_id=state.id,
                pc_id=pc_id,
                ac_id=ac_id,
                ward_id=ward_id)

def main():
    if not db.select("places", where="type='STATE' AND code='karnataka'"):
        db.insert("places", name="Karnataka", type="STATE", code="karnataka", parent_id=None)
    state = Place.find("karnataka")
    #add_places(state)
    add_pcs(state)
    add_acs(state)
    add_wards(state)
    add_polling_booths(state)

if __name__ == '__main__':
    main()
