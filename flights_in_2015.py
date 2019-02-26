# Load flights

def load_flights():

    filename = 'data/flightDescriptions2015.txt'
    with open(filename,'rb') as f:
        ft = f.readlines()

    flights = [f.strip() for f in ft]
    
    return flights

def unique_airports(flights):

    airports = []
    for fp in flights:
        airports.extend(fp.split(',')[0].split('-'))

    ua = set(airports)

    return list(ua)
    
def airport_coo(code):

    import pandas as pd

    airport_data = pd.read_csv('data/airports.txt',
                                header=None,
                                names=('airport_id','name','city','country',
                                       'code','icao','latitude','longitude',
                                       'altitude','timezone','dst','tzname'))

    lat = airport_data[airport_data['code'] == code]['latitude'].values[0]
    lon = airport_data[airport_data['code'] == code]['longitude'].values[0]

    return lat,lon
    
def get_path(lat1,lon1,lat2,lon2):

    import pyproj

    g = pyproj.Geod(ellps='WGS84')
    az12,az21,dist = g.inv(lon1,lat1,lon2,lat2)
    path = g.npts(lon1,lat1,lon2,lat2,1 + int(dist/1000.))
    path.insert(0,(lon1,lat1))
    path.append((lon2,lat2))

    return path

if __name__ == "__main__":
    flights = load_flights()
    d = {}
    for x in unique_airports(flights):
        coo = airport_coo(x)
        d[x] = {'lat':coo[0],'lon':coo[1]}

    # Construct a big text list of all paths

    with open('data/flightPaths2015.txt','wb') as f:
        allpaths = []
        f.write('longitude,latitude,airport_start,airport_end,type\n')
        for flight in flights:
            start_code,end_code = flight.split(',')[0].split('-')
            flight_type = flight.split(',')[1]
            start_data = d[start_code]
            end_data = d[end_code]
            path = get_path(start_data['lat'],start_data['lon'],end_data['lat'],end_data['lon'])
            for p in path:
                f.write("{0:},{1:},{2:},{3:}\n".format(str(p)[1:-1],start_code,end_code,flight_type))
