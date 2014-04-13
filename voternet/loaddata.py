"""Script to load places into the database.

USAGE:
    
    python voternet/loaddata.py places/AP AP "Andhra Pradesh"

    * The first argument is path a directory containg the following files.
        * pc.csv - List of parliamentary constituencies with columns pc_code and pc_name
        * ac.csv - List of assembly constituencies with columns pc_code, ac_code and ac_name
        * polling_booths.csv - list of all polling booths in the state with columns ac_code, pb_code and pb_name
    * The second argument is the state code
    * The third argument is the state name

This script is also used to add the first admin user.

    python voternet/loaddata.py --add-admin your.email@gmail.com
"""

from models import get_db, Place
import web
import csv

# will be initialized in main()
db = None

@web.memoize
def get_pc(state_id, code):
    return db.select("places", where="type='PC' AND state_id=$state_id AND code=$code", vars=locals())[0]

@web.memoize
def get_ac(state_id, code):
    return db.select("places", where="type='AC' AND state_id=$state_id AND code=$code", vars=locals())[0]

@web.memoize
def get_ward(ac_id, code):
    return db.select("places", where="type='WARD' AND ac_id=$ac_id AND code=$code", vars=locals())[0]

def add_acs(state, dir):
    with db.transaction():
        for pc, ac, name in read_csv(dir + "/ac.txt"):
            key = state.key + "/" + ac
            name = ac + " - " + name
            if not db.select("places", where="type='AC' AND state_id=$state.id AND code=$ac", vars=locals()):
                parent = get_pc(state.id, pc)
                db.insert("places", key=key, name=name, type="AC", code=ac, parent_id=parent.id, state_id=state.id, pc_id=parent.id)

def add_pcs(state, dir):
    with db.transaction():
        for code, name in read_csv(dir + "/pc.txt"):
            key = state.key + "/" + code
            name = code + " - " + name
            if not db.select("places", where="type='PC' AND key=$key", vars=locals()):
                db.insert("places", key=key, name=name, type="PC", code=code, parent_id=state.id, state_id=state.id)

def add_wards(state, dir):
    for line in open("dir/wards.txt"):
        pc, ac, code, name = line.strip("\n").split("\t")
        key = "{0}/{1}/{2}".format(state.key, ac, code)
        name = code + " - " + name
        parent = get_ac(state.id, ac)
        if not db.select("places", where="type='WARD' AND key=$key", vars=locals()):
            ac_id = parent.id
            pc_id = get_pc(state.id, pc).id
            db.insert("places", key=key, name=name, type="WARD", code=code,
                parent_id=parent.id,
                state_id=state.id,
                pc_id=pc_id,
                ac_id=ac_id)

def add_polling_booths(state, dir):
    with db.transaction():
        for ac_code, code, name in read_csv(dir + "/polling_booths.txt"):
            print "add_polling_booths", state.id, ac_code, code
            key = "{0}/{1}/{2}".format(state.key, ac_code, code)
            name = code + " - " + name
            ac = get_ac(state.id, ac_code)
            ac_id = ac.id
            pc_id = ac.pc_id
            ward_id = None

            if not db.select("places", where="type='PB' AND key=$key", vars=locals()):
                lazy_insert("places", key=key, name=name, type="PB", code=code,
                    parent_id=ac_id,
                    state_id=state.id,
                    pc_id=pc_id,
                    ac_id=ac_id,
                    ward_id=ward_id)
        commit_lazy_inserts()

def add_polling_centers(state, filename):
    d = {}
    with db.transaction():
        for ac_code, px_code, pb_code, name in read_csv(filename):
            print "adding polling center", state.id, ac_code, px_code
            if (ac_code, px_code) not in d:
                key = "{0}/{1}/{2}".format(state.key, ac_code, px_code)                    
                if not db.select("places", where="type='PS' AND key=$key", vars=locals()):
                    pb_key = "{0}/{1}/{2}".format(state.key, ac_code, pb_code)
                    pb = Place.find(pb_key)
                    lazy_insert("places", key=key, name=name, type="PS", 
                        code=key.split("/")[-1],
                        state_id=state.id,
                        region_id=pb.region_id,
                        pc_id=pb.pc_id,
                        ac_id=pb.ac_id,
                        ward_id=pb.ward_id)
                d[ac_code, px_code] = 1
        commit_lazy_inserts()

    with db.transaction():
        for ac_code, px_code, pb_code, name in read_csv(filename):
            key = "{0}/{1}/{2}".format(state.key, ac_code, px_code)                    
            px = Place.find(key)
            pb_key = "{0}/{1}/{2}".format(state.key, ac_code, pb_code)
            db.update("places", px_id=px.id, where="key=$pb_key", vars=locals())

_inserts = {}
def lazy_insert(table, **row):
    rows = _inserts.setdefault(table, [])
    rows.append(row)
    if len(rows) >= 1000:
        commit_lazy_inserts()

def commit_lazy_inserts():
    for table, rows in _inserts.items():
        if rows:
            db.multiple_insert(table, rows)
            _inserts[table] = []

def add_state(code, name):
    if not db.select("places", where="type='STATE' AND key=$code", vars=locals()):
        db.insert("places", key=code, name=name, type="STATE", code=code, parent_id=None)
    return Place.find(code)

def read_csv(filename):
    return [[c.strip() for c in row] for row in csv.reader(open(filename), delimiter='\t')]

def main():
    import sys
    import webapp
    webapp.check_config()

    global db 
    db = get_db()

    if "--add-admin" in sys.argv:
        index = sys.argv.index("--add-admin")
        email = sys.argv[index+1]
        state = Place.find(code=webapp.get_state())

        # Hack to fix the error at account.get_current_user() when adding volunteer
        web.ctx.current_user = None

        state.add_volunteer("Fix Your Name", email, "0000000000", role="admin")
        return
    if "--polling-centers" in sys.argv:
        index = sys.argv.index("--polling-centers")
        state_code = sys.argv[index+1]
        filename = sys.argv[index+2]
        state = Place.find(state_code)
        print "add_polling_centers", state, filename
        add_polling_centers(state, filename)
        return
    
    dir = sys.argv[1]
    code = sys.argv[2]
    name = sys.argv[3]

    state = add_state(code, name)

    add_pcs(state, dir)
    add_acs(state, dir)
    #add_wards(state, dir)
    add_polling_booths(state, dir)

if __name__ == '__main__':
    main()
