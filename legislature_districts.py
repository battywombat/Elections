#!/usr/bin/env python3
'''
No database I can find gives a mapping from legislatures to the districts they
represent. So I have to make one from the wikipedia.
This data is going to a legislator's name (ie, what information is stored in
the database) to something that looks a bit like this:
(district_id, house, party, [(arrival, departure)])
A list is used because different legsilators may have the same name, may represent
different districts, or may be in the senate for a noncontigous period of time.
'''
import datetime
import re
import urllib.request
import xml.etree.ElementTree as ET

HOUSE_PAGE = "https://en.wikipedia.org/wiki/Representative_history_of_the_Ohio_House_of_Representatives"

SENATE_PREFIX = "https://en.wikipedia.org/wiki/Ohio's_"
SENATE_POSTFIX = "_senatorial_district"
SENATE_DISTRICTS = [x for x in range(1, 34)]

SIGNAL_WORDS = {
    "based",
    "consisted",
    "consists",
}

def main() -> None:
    print(house_mapping_wiki())

def prefix(x):
    if x % 10 == 1 and x != 11:
        return "st"
    elif x % 10 == 2 and x != 12:
        return "nd"
    elif x % 10 == 3 and x != 13:
        return "rd"
    else:
        return "th"

def get_map() -> dict:
    '''
    The function that should actually be used by other programs to access this
    data. 
    :return: A dictionary as referred to in the module docstring
    '''
    r = {}
    house = get_house_wiki()
    senate = get_senate_wiki()
    process_district_tables(r, house, "HD")
    process_district_tables(r, senate, "SD")
    return r

def get_child_by_attrib(root, tag, value) -> ET:
    for elem in root:
        if tag in elem.attrib and elem.attrib[tag] == value:
            return elem 

def get_child_by_tag(root, tag):
    for elem in root:
        if elem.tag == tag:
            return elem
DATES = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    "December"
]

def date_to_num(date):
    return DATES.index(date)+1

date_regex = re.compile("("+"|".join(DATES)+") ([0-9]+), ([0-9]{4})")
simple_date_regex = re.compile("("+"|".join(DATES)+") ([0-9]{4})")

def get_date(datestring):
    datestring = datestring.strip(" .")
    match = date_regex.match(datestring)
    if match:
        return datetime.date(int(match.group(3)), date_to_num(match.group(1)), int(match.group(2)))
    match = simple_date_regex.match(datestring)
    if match:
        return datetime.date(int(match.group(2)), date_to_num(match.group(1)), 1)
    if datestring == 'present':
        return datetime.date.today()
    raise ValueError("Incorrect value for date: "+datestring)

def process_district_row(row: ET) -> tuple:
    if len(row) > 3:
        name = row[0].text if row[0].text is not None else row[0][0].text
        name = name.strip()
        if re.match(".*(Jr.|Sr.)$", name):
            name = name[:-3].strip()
        if re.match(".*(II)$", name):
            name = name[:-2].strip()
        if len(name.split(" ")) > 2:
            names = name.split(" ")
            name = " ".join([names[0], names[-1]])
        name = name.strip(",")
        party = row[1][0].text
        dates = re.split('-|–', row[2].text) # nearly guaranteed to have two values
        return (name, party, get_date(dates[0]), get_date(dates[1]))

def process_district_table(r, d, table: ET, house: str) -> tuple:
    for row in table:
        if row[0].text != "Representative" and row[0].text != "Senator":
            t = process_district_row(row)
            if t:
                if t[0] in r:
                    r[t[0]].append((house+str(d), t[1], t[2]))
                else:
                    r[t[0]] = []
                    r[t[0]].append((house+str(d), t[1], t[2], t[3]))

def process_district_tables(r, d, house) -> dict:
    '''Process dictionary of table elements with legislator information'''
    for v in d:
        process_district_table(r, v, d[v], house)

def get_wiki_body(root: ET) -> ET:
    body = get_child_by_tag(root, 'body')
    content = get_child_by_attrib(body, 'id', 'content')
    bodyContent = get_child_by_attrib(content, 'id', 'bodyContent')
    contentText = get_child_by_attrib(bodyContent, 'id', 'mw-content-text')
    return contentText

def get_house_wiki() -> dict:
    # It sure is a good thing that the structure of this page won't change...
    raw_page = urllib.request.urlopen(HOUSE_PAGE).read()
    content = get_wiki_body(ET.fromstring(raw_page))
    regex = re.compile("([0-9]+)(st|nd|rd|th){1} District")
    in_district = -1
    districts = {}
    for elem in content:
        if in_district == -1 and elem.tag == 'h2':  # look for beginning of district_id
            test = regex.match(elem[0].text)
            if test is not None:
                in_district = int(test.group(1))
        elif in_district != -1:
            if elem.tag == 'table':
                districts[in_district] = elem
                in_district = -1
    return districts

def get_table(root):
    for elem in root:
        if elem.tag == 'table':
            return elem

def get_senate_wiki() -> dict:
    r = {}
    for i in SENATE_DISTRICTS:
        url = SENATE_PREFIX+str(i)+prefix(i)+SENATE_POSTFIX
        raw_page = urllib.request.urlopen(url).read()
        content = get_wiki_body(ET.fromstring(raw_page))
        for elem in content:
            if elem.tag == 'table':
                r[i] = elem
                break
    return r

# There is not a one to one correspondence between congressional districts and
# counties. However, most demographic data that might be helpful would be is at
# the county level. Again, I can't find any data that would be useful to map
# congressional districts to counties, so I'm using wikipedia again.
# These functions will go through the wikipedia pages for the house and build
# A "best guess" mapping that will estimate based on the text of the wikipedia
# page what districts contain what counties.

def house_mapping_wiki() -> dict:
    raw_page = urllib.request.urlopen(HOUSE_PAGE).read()
    content = get_wiki_body(ET.fromstring(raw_page))
    regex = re.compile("([0-9]+)(st|nd|rd|th){1} District")
    in_district = -1
    for elem in content:
        if in_district == -1 and elem.tag == 'h2':
            test = regex.match(elem[0].text)
            if test is not None:
                in_district = int(test.group(1))
        elif in_district != -1 and elem.tag != 'table':
            print_elem(elem)

def print_elem(elem):
    print(elem.text, end="")
    for e in elem:
        print_elem(e)
    print()

def senate_mapping_wiki() -> dict:
    pass

if __name__ == '__main__':
    main()

