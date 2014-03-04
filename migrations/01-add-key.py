"""Migration to add a key column to places table and populate it.

It is becoming hard to find URL of a place dynamically. Adding a key column
solves that issue for ever. We can decide what should be URL for a place when
adding it.

As of now, the URLs are like:

/KA - for state
/KA/R01 - for regions
/KA/PC23 - for Parliamentary Constituency
/KA/AC123 - for Assembly Constituency
/KA/AC123/PB0123 - for Polling Booth
/KA/AC123/W01 - for ward
/KA/AC123/G12 - for group
"""

from voternet.models import get_db

def upgrade():
    db = get_db()

    with db.transaction():
        db.query("alter table places add column key text unique")

        # set key for states
        db.query("update places set key=code WHERE type='STATE'")

        # set key for PC, AC and REGIONs
        db.query("UPDATE places" +
            " SET key=state.key || '/' || places.code" +
            " FROM places state" + 
            " WHERE places.type IN ('PC', 'AC', 'REGION')" +
            " AND places.state_id=state.id")

        # set key for WARDs and PBs
        db.query("UPDATE places" +
            " SET key=ac.key || '/' || places.code" +
            " FROM places ac" + 
            " WHERE places.type IN ('WARD', 'PB')" +
            " AND places.ac_id=ac.id")

if __name__ == "__main__":
    from voternet import webapp
    webapp.check_config()

    upgrade()