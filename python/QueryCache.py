# Copyright (c) 2008 River Tarnell <river@wikimedia.org>. 
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely. This software is provided 'as-is', without any express or implied
# warranty.
#
# $Id: QueryCache.py 58 2008-09-18 18:54:21Z river $

import pickle, MySQLdb
import repdb

class QueryCache:
    def __init__(self, context):
        self.context = context
    
    def load(self, dbname, report):
        """Return a cached query result"""
        db = repdb.connect_cache(self.context)
        c = db.cursor()
    
        c.execute("""SELECT (UNIX_TIMESTAMP() - last_run), result 
                    FROM report_cache 
                    WHERE report_key=%s AND dbname=%s""", (report.key, dbname))
       
        r = c.fetchone()
        if r == None:
            return None
        return (r[0], r[1])

    def check_create_row(self, cursor, dbname, report_key):
         cursor.execute("""INSERT IGNORE INTO report_cache (dbname, report_key)
                     VALUES(%s, %s)""",
                  (dbname, report_key))
    
    def save(self, dbname, report, data):
        """Save the result of a query to the cache"""
        db = repdb.connect_cache(self.context)
        c = db.cursor()
        self.check_create_row(c, dbname, report.key)
        
        c.execute("""UPDATE report_cache
                     SET last_run=UNIX_TIMESTAMP(), result=%s
                     WHERE dbname=%s AND report_key=%s""",
                     (data, dbname, report.key)
                 )
       
        db.commit()
    
    def purge(self, dbname, report):
        """Remove a query from the cache"""
        db = repdb.connect_cache(self.context)
        c = db.cursor()
        c.execute("DELETE FROM report_cache WHERE dbname = %s AND report_key = %s",
                (dbname, report.key));
        db.commit()
    
    def purge_all(self, report):
        """Remove a query from the cache for all wikis"""
        db = repdb.connect_cache(self.context)
        c = db.cursor()
        c.execute("DELETE FROM report_cache WHERE report_key = %s", report.key)
        db.commit()

    def execute(self, report, dbname, variables, force = False):
        """Like Report.execute(), except load/save from the cache as appropriate"""
        if not report.cachable():
            return {'age': 0,
                    'result': report.execute(self.context, dbname, variables)}
            
        # Try cache load
        if not force:
            result = self.load(dbname, report)
            if (result != None) and \
               (result[0] < report.cache):
                try:
                    data = pickle.loads(result[1])
                except Exception:
                    pass
                else:
                    return {'age': result[0], 'result': result}
        
            # Not cached; if it's a nightly query, return failure
            if report.nightly:
                return None

        result = self.update_report(dbname, report, variables)
        return {'age': 0, 'result': result}
   
    def update_report(self, dbname, report, variables):
        db = repdb.connect_cache(self.context)
        c = db.cursor()
        self.check_create_row(c, dbname, report.key)
        c.execute("""UPDATE report_cache
                     SET last_start=UNIX_TIMESTAMP()
                     WHERE dbname=%s AND report_key=%s""",
                     (dbname, report.key))
        db.commit()

        result = report.execute(self.context, dbname, variables)
        self.save(dbname, report, pickle.dumps(result))
        return result

    def check_cache(self, dbname, reports):
        """Given a list of reports, return a list of those which are uncached
           %nightly queries."""
        db = repdb.connect_cache(self.context)
        c = db.cursor()
        ret = []
        for r in reports:
            if not r.nightly: continue
            c.execute("SELECT 1 FROM report_cache WHERE dbname=%s AND report_key=%s",
                (dbname, r.key))
            if len(c.fetchall()) == 0:
                ret.append(r)
        return ret
