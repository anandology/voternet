import csv
import sys
import re
from collections import defaultdict
import web

re_room = re.compile("(?:room no|room nam|room nem| r no)( \d+)?", re.I)
re_non_alphanum = re.compile("[^a-zA-Z0-9 ]")
re_space = re.compile("\s+")

def process_address(address):
    a0 = address
    address = re_non_alphanum.sub(" ", address)
    address = re_space.sub(" ", address)
    address = re_room.sub(" ", address)
    address = re_space.sub(" ", address)
    if 'R No' in address:
        print >> sys.stderr, repr(a0), repr(address)
    return address.strip()
    
def process_row(row):
    address = process_address(row[3])

def read_data_ka():
    f = open("pb.csv")
    f.readline() # skip header
    for row in csv.reader(f):
        #print row
        address = process_address(row[3])
        ac = row[0][:5]
        pb = "PB{:04d}".format(int(row[0][-4:]))
        name = row[2]
        if row[4] != "-":
            ward = "W{} - {}".format(row[4], row[5])
        else:
            ward = "-"
        if ac == "AC175" or True:
            yield web.storage(ac=ac, pb=pb,  name=name, address=address, ward=ward)

def read_data_ap(filename):
    """Reads data from polling_booth.txt
    """
    f = open(filename)
    for row in csv.reader(f, delimiter="\t"):
        address = process_address(row[-1])
        yield web.storage(ac=row[0], pb=row[1], name=row[-1], address=address)    

def counts():
    d = defaultdict(set)
    d2 = defaultdict(lambda: 0)
    for row in read_data_ka():
        d[row.ac].add(row.address.lower())
        d2[ac] += 1
    
    for ac, addresses in d.items():
        print ac, len(addresses), d2[ac]

def generate_codes(filename):
    d = {}
    for row in sorted(read_data_ap(filename), key=lambda row: (row.ac, row.pb)):
        ac = d.setdefault(row.ac, {})
        key = row.address.lower()
        if key not in ac:
            ac[key] = "PX{:03d}".format(len(ac)+1)
        x = row.ac, ac[key], row.pb, "{} - {}".format(ac[key], row.address)
        print "\t".join(x)

def main():
    if "--counts" in sys.argv:
        counts()
    else:
        generate_codes(sys.argv[1])

main()
    
