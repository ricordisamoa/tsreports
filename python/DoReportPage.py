# Copyright (c) 2008 River Tarnell <river@wikimedia.org>. 
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely. This software is provided 'as-is', without any express or implied
# warranty.
#
# $Id: DoReportPage.py 81 2010-02-06 21:11:57Z river $

import cgi, pickle
import repdb
from QueryCache import *
from templates.QueryVariables import QueryVariables
from templates.Report import Report
from templates.CachedReportUnavailable import CachedReportUnavailable

class Field:
    def __init__(self, formatter, vars, lang):
        self.vars = vars
        self.formatter = formatter
        self.lang = lang

    def format(self):
        return self.formatter.format(self.vars, self.lang)

def response(context, req):
    try:
        key = req.params['report']
        report = context.reports[key]
    except ValueError:
        raise ValueError('no such report')
    
    dbname = req.params['wiki']
    wiki = repdb.find_wiki(context, dbname)
    namespaces = repdb.get_namespaces(context, dbname)

    # Extract all variables from the request.  Make sure all the
    # required variables were specified; if not, emit a form
    # where the user can specify them.
    variables = {}
    for k in req.params.keys():
        if k[0:4] != "var_":
            continue
        varname = k[4:]
        value = req.params[k]
        variables[varname] = value
    
    for v in report.variables:
        if not variables.has_key(v.name):
            # missing a variable
            t = req.prepare_template(QueryVariables)
            t.variables = report.variables
            t.wiki = wiki
            t.report = report

            output = str(t)
            req.start_response('200 OK', [('Content-Type', 'text/html; charset=UTF-8')])
            yield output
            return

    cache = QueryCache(context)
    cache_result = cache.execute(report, dbname, variables)
    if cache_result == None:
        t = req.prepare_template(CachedReportUnavailable)
        t.report = report
        output = str(t)
        req.start_response('200 OK', [('Content-Type', 'text/html; charset=UTF-8')])
        yield output
        return

    age = cache_result[0]
    result = cache_result[1]

    fields = report.fields

    t = req.prepare_template(Report)
    t.age = age
    t.report = report
    t.wiki = wiki

    # Generate a list of variables + values for the report page
    t.variables = {}
    for v in report.variables:
        t.variables[v.title] = variables[v.name]

    t.headers = []
    for f in fields:
        t.headers.append(f.title)

    t.rows = []
    for r in result:
        row = []
        for f in fields:
            r['__namespaces__'] = namespaces
            r['__dbname__'] = dbname
            r['__domain__'] = wiki['domain']
            row.append(Field(f, r, req.i18n))
        t.rows.append(row)

    output = t.respond().encode('utf-8')
    req.start_response('200 OK', [('Content-Type', 'text/html; charset=UTF-8')])
    yield output
