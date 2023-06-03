import sys
import json
import logging as log
from datetime import datetime, timedelta  # , timezone
from pathlib import Path

import requests

log.basicConfig(level=log.DEBUG)

def call_api(body, url, headers):
    # Make the request
    response = requests.post(url, headers=headers, json={"query": body})
    # Check the response status code
    if response.status_code == 200:
        log.debug('call success 200')
        return response.json()
    else:
        log.warning(f'call unknown {response.status_code}')
        return response

def get_project_id(USR, PROJNUM, url, headers):
    body = 'query { user(login: "'+USR+'") {projectV2(number: '+str(PROJNUM)+') {id}}}'
    res = call_api(body, url, headers)
    return res['data']['user']['projectV2']['id']

def get_project(pId, url, headers):
    """ queries github for the project information """
    body = 'query{ node(id: "'+pId+'''") { 
                ... on ProjectV2 { items(first: 20) { nodes{ id fieldValues(first: 8) { nodes{ 
                    ... on ProjectV2ItemFieldTextValue { text field { ... on ProjectV2FieldCommon {  name }}} 
                    ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name }}} 
                    ... on ProjectV2ItemFieldSingleSelectValue { name field { 
                    ... on ProjectV2FieldCommon { name }}}}}
                    content{ 
                        ... on DraftIssue { title body } 
                        ... on Issue { title assignees(first: 10) { nodes{ login }}} 
                        ... on PullRequest { title assignees(first: 10) { nodes{ login }}}}
                }}}}}'''
    return call_api(body, url, headers)

def write_ical(res):
    """ write the calendar """
    with open('static/project2calendar.ics', 'wt', encoding='utf-8') as afile:
        afile.writelines([
            'BEGIN:VCALENDAR\r\n',
            'VERSION:2.0\r\n',
            'PRODID:-//appsheet.com//appsheet 1.0//EN\r\n'
            'CALSCALE:GREGORIAN\r\n'
            'METHOD:PUBLISH\r\n'
           f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}\r\n"
        ])
        for node in res['data']['node']['items']['nodes']:
            afile.write('BEGIN:VEVENT\r\n')
            # content
            if 'content' in node.keys():
                if 'title' in node['content'].keys():
                    title = node['content']['title'] if node['content']['title'] else 'no title'
                    afile.writelines(f'SUMMARY:"{title[:75].encode()}"\r\n')
                if 'assignees' in node['content'].keys():
                    for ass in node['content']['assignees']['nodes']:
                        usr = ass['login']
                        afile.writelines(f'OWNER:"{usr.encode()}"\r\n')
                #if 'body' in node['content'].keys():
                #    descr = str(node['content']['body']).encode( errors="replace")
                #    afile.write(f'DESCRIPTION: "{descr}"\r\n')
            # fieldValues
            no_dtstart=True
            no_dtend=True
            if 'fieldValues' in node.keys():
                for f in node['fieldValues']['nodes']:
                    if f:
                        if 'date' in f.keys():
                            if f['field']['name'] == 'Start':
                                if f['date']!='':
                                    dts = datetime.fromisoformat(f['date'])
                                    no_dtstart = False
                            elif f['field']['name'] == 'Due':
                                if f['date']!='':
                                    dte = datetime.fromisoformat(f['date'])
                                    no_dtend = False
                        elif 'name' in f.keys():
                            st = f['name'] if f['name'] else 'no status'
                            afile.writelines(f'DESCRIPTION:{st.encode()}\r\n')
            if no_dtstart and no_dtend:
                dts = datetime.now()+timedelta(days=7)
                dte = dts+timedelta(days=9)
            elif no_dtend:
                dte = dts+timedelta(days=2)
            elif no_dtstart:
                dts = dte-timedelta(days=2)
            elif dts >= dte:
                dts = dte-timedelta(days=2)
            elif dts < dte:
                pass
            else:
                log.error(f'EDGE CASE {dts} {dte} {title}')
            dts = dts.strftime('%Y%m%dT%H%M%SZ')
            dte = dte.strftime('%Y%m%dT%H%M%SZ')
            afile.writelines(f'DTSTART:{dts}\r\n')
            afile.writelines(f'DTEND:{dte}\r\n')
            afile.write(f'UID:{node["id"]}\r\n')
            afile.write('END:VEVENT\r\n')
        afile.write('END:VCALENDAR\r\n')


if __name__ == '__main__':
    url = "https://api.github.com/graphql"
    USR, PROJNUM, TOKEN = sys.argv[1:]
    headers = {'Authorization': f'Bearer {TOKEN}'}
    pId = get_project_id(USR, PROJNUM, url, headers)
    response = get_project(pId, url, headers)
    write_ical(response)
