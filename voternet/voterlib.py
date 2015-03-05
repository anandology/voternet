"""module to load voter details from EC website.
"""
import web
import sys
import logging
import urllib
import json
logger = logging.getLogger(__name__)

URL = "http://ceokarnataka.kar.nic.in/SearchWithEpicNo_New.aspx"

def get_voter_details_old(voterid):
    # ignore voterids like "yes" etc.
    if len(voterid) <= 4:
        return

    logger.info("get_voter_details %s", voterid)    
    try:
        b = web.Browser()
        b.open(URL)
        b.select_form(index=0)
        b['ctl00$ContentPlaceHolder1$ddlDistrict'] = ['21']
        b['ctl00$ContentPlaceHolder1$txtEpic'] = voterid
        b.submit()
    except Exception:
        logger.error("failed to request voterid details for %s", voterid, exc_info=True)
        return web.storage()

    soup = b.get_soup()
    table = soup.find("table", {"id": "ctl00_ContentPlaceHolder1_GridView1"})
    if not table:
        return None
    last_row = table.findAll("tr")[-1]
    data = [td.getText() for td in last_row.findAll(("td", "tr"))]
    # skip the first one, which is a button
    data = data[1:]
    cols = "ac_num ac_name part_no sl_no first_name last_name rel_firstname rel_lastname sex age".split()
    d = dict(zip(cols, data))
    d['voterid'] = voterid
    logger.info("voter info %s %s", voterid, d)   
    return web.storage(d)

def get_voter_details(voterid):    
    response = urllib.urlopen("http://voter.missionvistaar.in/search?voterid=" + voterid).read()
    d = json.loads(response)
    if d:
        cols = "ac_num ac_name part_no sl_no first_name last_name rel_firstname rel_lastname sex age".split()
        mapping = {
            "ac_num": "ac",
            "part_no": "part",
            "sl_no": "serial",
            "first_name": "name",
            "rel_firstname": "relname"
        }
        return {c:d.get(mapping.get(c, c), "") for c in cols}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format = "[%(levelname)s] : %(filename)s:%(lineno)d : %(message)s")
    print get_voter_details(sys.argv[1])
