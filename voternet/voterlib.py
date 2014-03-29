"""module to load voter details from EC website.
"""
import web
import sys

URL = "http://ceokarnataka.kar.nic.in/SearchWithEpicNo_New.aspx"

def get_voter_details(voterid):
    b = web.Browser()
    b.open(URL)
    b.select_form(index=0)
    b['ctl00$ContentPlaceHolder1$ddlDistrict'] = ['21']
    b['ctl00$ContentPlaceHolder1$txtEpic'] = voterid
    b.submit()

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
    return web.storage(d)

if __name__ == '__main__':
    print get_voter_details(sys.argv[1])
