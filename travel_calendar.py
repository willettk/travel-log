from __future__ import print_function # Assumes Python 2.7
import httplib2
import os
import re
import json

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

from collections import Counter
import datetime

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Calendar API Python Quickstart'

flightFormat = "%Y-%m-%dT%H:%M:%S"
ymdFormat = '%Y-%m-%d'

milesToKilometers = 1.60934
earthRadiusKm = 6367

dataPath = "./data"
# Events should not be uploaded to public GitHub repo
eventsFile = "{}/events.json".format(dataPath)

def getCredentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    This function needs to be run in iPython to complete the OAuth2 flow, rather than called from the command line.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'calendar-python-quickstart.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def getService():
    """
    Get the service object for my calendar
    """
    credentials = getCredentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    return service

def listCalendars():

    """ Return all the calendars associated with the authorized account
    """

    service = getService()
    page_token = None

    calendar_list = service.calendarList().list(pageToken=page_token).execute()

    return calendar_list

def checkAllCalendars():

    """ Check all calendars for this account
    to see if any match the expected pattern for a flight: "[AAA]-[ZZZ]".
    They should all be in 'Travel', but some could have been misclassified.
    """

    service = getService()
    calendar_list = listCalendars()

    for calendar_list_entry in calendar_list['items']:

        eventsResult = service.events().list(
            calendarId=calendar_list_entry['id'],
            singleEvents=True,
            orderBy='startTime').execute()
        events = eventsResult.get('items', [])

        nFlights = 0
        for event in events:
            summary = event['summary']
            if re.match("[A-Z]{3}-[A-Z]{3}",summary):
                nFlights += 1

        if nFlights > 0:
            print("{} has {} events matching format.".format(calendar_list_entry['summary'],nFlights))

def loadAirportData(use_cached_airports=True):

    """ Get pandas dataframe with metadata on airports around the world.
    Data is from http://openflights.org/data.html

    use_cached_airports : bool
        Set as True to load data from local file. If false, will attempt to download data from raw Github content. Set to False to access the most up-to-date version.
    """

    import pandas as pd

    colnamesCached = ['name','city','country','IATA','ICAO','lat','lon','elevation','timezone','DST','tz']
    colnamesWeb = colnamesCached + ['airport','OurAirports']

    if use_cached_airports:
        airportDataLocation = "{}/airports.txt".format(dataPath)
        airports = pd.read_csv(airportDataLocation, sep=',', header = None, names=colnamesCached)
    else:
        airportDataLocation = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
        airports = pd.read_csv(airportDataLocation, sep=',', header = None, names=colnamesWeb)

    return airports

def haversine(lon1, lat1, lon2, lat2):

    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    """

    from math import radians, cos, sin, asin, sqrt

    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    km = earthRadiusKm * c

    return km

def downloadEvents():

    """ Download all events from my Travel calendar
    """

    service = getService()

    # Get the travel calendar
    calendar_list = listCalendars()
    calendarName = 'Travel'

    for calendar_list_entry in calendar_list['items']:
        if calendar_list_entry['summary'] == calendarName:
            travel_cal = calendar_list_entry

    eventsResult = service.events().list(
        calendarId=travel_cal['id'],
        maxResults=1000,
        singleEvents=True,
        orderBy='startTime').execute()
    events = eventsResult.get('items', [])

    with open(eventsFile,'w') as f:
        json.dump(events,f)

    return events

def getEvents(use_cached_calendar=True):

    """ Use cached file with events data as default; improves speed and network requirement.
    Set use_cached_calendar=False to download an updated version of data from cloud.
    """

    if use_cached_calendar:
        with open(eventsFile,'r') as f:
            events = json.load(f)
    else:
        events = downloadEvents()

    return events

def getRoutes(use_cached_calendar=True):

    """ Return a list of all routes flown as flight segments
    """

    events = getEvents(use_cached_calendar)

    routes = []

    for event in events:
        summary = event['summary']
        if re.match("[A-Z]{3}-[A-Z]{3}",summary):
            routes.append(summary)

    return routes

def getAirports(use_cached_calendar=True):

    """ Return a list of all airports listed as part of a segment
    """
    events = getEvents(use_cached_calendar)

    airports = []

    for event in events:
        summary = event['summary']
        if re.match("[A-Z]{3}-[A-Z]{3}",summary):
            splitAirports = summary.split('-')
            airports.extend(splitAirports)

    return airports

def getFlights(use_cached_calendar=True):

    events = getEvents(use_cached_calendar)

    flights = []

    for event in events:
        summary = event['summary']
        if re.match("[A-Z]{3}-[A-Z]{3}",summary):
            flights.append(event)

    return flights

def flightsPerYear(year=datetime.datetime.today().year):

    flights = getFlights()

    nFlights = 0

    flightList = []
    for flight in flights:
        startDatetime = datetime.datetime.strptime(flight['start'].get('dateTime')[:-6],flightFormat)
        if startDatetime.year == year:
            nFlights += 1
            date = startDatetime.strftime(ymdFormat)
            flightList.append("{} - {}".format(date,flight['summary']))

    if nFlights == 0:
        print("\nNo flights in {}\n".format(year))
    elif nFlights == 1:
        print("\n{} flight in {}\n".format(nFlights,year))
        for fl in flightList:
            print(fl)
    else:
        print("\n{} flights in {}\n".format(nFlights,year))
        for fl in flightList:
            print(fl)

    return None

def questions(cached=True):

    """ Answer some questions using the calendar data on my travels
    """

    routes = getRoutes(use_cached_calendar=cached)
    airports = getAirports(use_cached_calendar=cached)

    # What's the longest flight segment I've flown?
    airportDF = loadAirportData(use_cached_airports=cached)
    alphabetizedRoutes = []
    for r in routes:
        r1,r2 = r.split('-')
        if r1 > r2:
            alphabetizedRoutes.append((r2,r1))
        else:
            alphabetizedRoutes.append((r1,r2))

    setRoutesUndirected = set(alphabetizedRoutes)
    setRoutesDirected = set(routes)

    maxDistance = 0.
    longestSegment = 'XXX-XXX'

    minDistance = 1e6
    shortestSegment = 'XXX-XXX'

    for r1,r2 in setRoutesUndirected:
        try:
            matchedAirport1 = airportDF[airportDF.IATA == r1]
        except:
            print(r1)
        try:
            matchedAirport2 = airportDF[airportDF.IATA == r2]
        except:
            print(r2)
        if len(matchedAirport1) == 1 and len(matchedAirport2) == 1:

            # Compute distance
            lat1 = matchedAirport1.lat
            lon1 = matchedAirport1.lon
            lat2 = matchedAirport2.lat
            lon2 = matchedAirport2.lon

            d = haversine(lon1, lat1, lon2, lat2)

            if d > maxDistance:
                maxDistance = d
                longestSegment = (r1,r2)
            if d < minDistance:
                minDistance = d
                shortestSegment = (r1,r2)

        else:
            print("{} matching airports for {}".format(len(matchedAirport1),r1))
            print("{} matching airports for {}".format(len(matchedAirport2),r2))

    if "-".join(longestSegment) not in setRoutesDirected:
        longestSegment = (longestSegment[1],longestSegment[0])

    print("\nSegment flight distances:")
    print("\t Longest segment flown is {}-{}, at {:5.0f} miles.".format(longestSegment[0],longestSegment[1],maxDistance/milesToKilometers))

    # What's the shortest flight segment I've flown?

    if "-".join(shortestSegment) not in setRoutesDirected:
        shortestSegment = (shortestSegment[1],shortestSegment[0])

    print("\tShortest segment flown is {}-{}, at {:5.0f} miles.".format(shortestSegment[0],shortestSegment[1],minDistance/milesToKilometers))

    # What is my lifetime air mileage?

    totalDistance = 0.

    for r in routes:
        r1,r2 = r.split('-')

        matchedAirport1 = airportDF[airportDF.IATA == r1]
        matchedAirport2 = airportDF[airportDF.IATA == r2]

        if len(matchedAirport1) == 1 and len(matchedAirport2) == 1:

            # Compute distance
            lat1 = matchedAirport1.lat
            lon1 = matchedAirport1.lon
            lat2 = matchedAirport2.lat
            lon2 = matchedAirport2.lon

            d = haversine(lon1, lat1, lon2, lat2)

            totalDistance += d

        else:
            print("{} matching airports for {}".format(len(matchedAirport1),r1))
            print("{} matching airports for {}".format(len(matchedAirport2),r2))


    flights = getFlights(use_cached_calendar=cached)
    firstFlightDate = datetime.datetime.strptime(flights[0]['start'].get('dateTime')[:-6],flightFormat)
    print("\nLifetime air mileage flown since {} is {:,} miles.".format(firstFlightDate.strftime(ymdFormat),int(totalDistance)))


    # What flight segment have I flown the most often? Show multiple routes if there's a tie.
    routeCounter = Counter(routes)

    print("\nMost common segment flown:")
    nMostCommonRoute = routeCounter.most_common(1)[0][1]
    for k,v in routeCounter.items():
        if v == nMostCommonRoute:
            print("\t{}, {} times".format(k,v))

    # Which airport have I taken off/landed at the most often?

    for i,flightType in enumerate(('takeoff','landing')):
        endpoint = [x.split('-')[i] for x in routes]
        endpointCounter = Counter(endpoint)
        print("\nMost {}s:".format(flightType))
        mostCommonAirportListDepth = 5
        for ec in endpointCounter.most_common(mostCommonAirportListDepth):
            for k,v in endpointCounter.items():
                if v == ec[1]:
                    print("\t{}, {} times".format(k,v))

    # Which airports exist at only a single endpoint?
    airportCounter = Counter(airports)
    print("\nAirports that only appear as a single endpoint (landing or takeoff):")
    for k,v in airportCounter.items():
        if v == 1:
            name = airportDF[airportDF.IATA == k].name.values[0]
            print("\t{} ({})".format(k,name))

    # How many flights per year have I taken?

    flightCountYear = {}
    for event in getEvents(cached):
        summary = event['summary']
        if re.match("[A-Z]{3}-[A-Z]{3}",summary):
            startDatetime = datetime.datetime.strptime(event['start'].get('dateTime')[:-6],flightFormat)
            year = startDatetime.year
            if flightCountYear.has_key(year):
                flightCountYear[year] += 1
            else:
                flightCountYear[year] = 1

    years = sorted(flightCountYear.keys())
    print("\nTotal flight segments per year:")
    for year in years:
        print("\t{:2d} flights in {}".format(flightCountYear[year],year))

    # What is the distribution between international and domestic flights?

    flightTypes = {'intl':     {'desc':'between two foreign countries','routes':[],'nTotal':0},
                    'domestic':{'desc':'within the United States','routes':[],'nTotal':0},
                    'outward': {'desc':'from the United States to another country','routes':[],'nTotal':0},
                    'inward':  {'desc':'  to the United States to another country','routes':[],'nTotal':0}}

    foreignCountries = set()

    for route in setRoutesDirected:
        r1,r2 = route.split('-')
        matchedAirport1 = airportDF[airportDF.IATA == r1]
        matchedAirport2 = airportDF[airportDF.IATA == r2]
        if len(matchedAirport1) == 1 and len(matchedAirport2) == 1:
            country1 = matchedAirport1.country.values[0]
            country2 = matchedAirport2.country.values[0]
            if country1 == 'United States' and country2 == 'United States':
                ft = 'domestic'
            elif country1 == 'United States':
                ft = 'outward'
                foreignCountries.add(country2)
            elif country2 == 'United States':
                ft = 'inward'
                foreignCountries.add(country1)
            else:
                ft = 'intl'
                foreignCountries.add(country1)
                foreignCountries.add(country2)
            flightTypes[ft]['routes'].append("{}-{}".format(r1,r2))
            flightTypes[ft]['nTotal'] += routeCounter[route]

    print("\nDid I need a passport?")
    for t in flightTypes.keys():
        print("\t{:3d} flights ({:3d} unique segments) {}".format(
                flightTypes[t]['nTotal'],
                len(flightTypes[t]['routes']),
                flightTypes[t]['desc']))

    # Which countries have I flown to?

    print("\nCountries flown to/from ({}):".format(len(foreignCountries)))
    print("\t{}".format(', '.join(sorted(foreignCountries))))

if __name__ == '__main__':
    questions(cached=False)
