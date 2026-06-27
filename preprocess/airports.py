#!/usr/bin/env python3
"""Tiny offline airport lookup table for the flight preprocessor.

Maps 4-letter ICAO codes to a small record used to populate the `origin` /
`destination` blocks of `flight.json` (see FLIGHT_SCHEMA.md). Coordinates are
WGS-84 decimal degrees, accurate to a few decimals (good enough for placing a
marker on a globe). This is deliberately a hand-curated subset of major
international airports, not a full database -- if you need the complete set,
pull OurAirports' `airports.csv` instead.

Usage:
    from airports import AIRPORTS, get_by_icao, get_by_iata
    jfk = get_by_icao("kjfk")     # case-insensitive
    fra = get_by_iata("FRA")
"""

# Each value: {"icao", "iata", "name", "lat", "lon"}
AIRPORTS = {
    # ---- North America ----
    "KJFK": {
        "icao": "KJFK",
        "iata": "JFK",
        "name": "John F. Kennedy International Airport",
        "lat": 40.6398,
        "lon": -73.7789,
    },
    "KLAX": {
        "icao": "KLAX",
        "iata": "LAX",
        "name": "Los Angeles International Airport",
        "lat": 33.9425,
        "lon": -118.4081,
    },
    "KSFO": {
        "icao": "KSFO",
        "iata": "SFO",
        "name": "San Francisco International Airport",
        "lat": 37.6189,
        "lon": -122.3750,
    },
    "KORD": {
        "icao": "KORD",
        "iata": "ORD",
        "name": "Chicago O'Hare International Airport",
        "lat": 41.9786,
        "lon": -87.9048,
    },
    "KATL": {
        "icao": "KATL",
        "iata": "ATL",
        "name": "Hartsfield-Jackson Atlanta International Airport",
        "lat": 33.6367,
        "lon": -84.4281,
    },
    "KSEA": {
        "icao": "KSEA",
        "iata": "SEA",
        "name": "Seattle-Tacoma International Airport",
        "lat": 47.4502,
        "lon": -122.3088,
    },
    "KMIA": {
        "icao": "KMIA",
        "iata": "MIA",
        "name": "Miami International Airport",
        "lat": 25.7959,
        "lon": -80.2870,
    },
    "KBOS": {
        "icao": "KBOS",
        "iata": "BOS",
        "name": "Boston Logan International Airport",
        "lat": 42.3656,
        "lon": -71.0096,
    },
    "KEWR": {
        "icao": "KEWR",
        "iata": "EWR",
        "name": "Newark Liberty International Airport",
        "lat": 40.6925,
        "lon": -74.1687,
    },
    "KDFW": {
        "icao": "KDFW",
        "iata": "DFW",
        "name": "Dallas/Fort Worth International Airport",
        "lat": 32.8998,
        "lon": -97.0403,
    },
    "CYYZ": {
        "icao": "CYYZ",
        "iata": "YYZ",
        "name": "Toronto Pearson International Airport",
        "lat": 43.6777,
        "lon": -79.6248,
    },
    "CYVR": {
        "icao": "CYVR",
        "iata": "YVR",
        "name": "Vancouver International Airport",
        "lat": 49.1939,
        "lon": -123.1844,
    },
    "MMMX": {
        "icao": "MMMX",
        "iata": "MEX",
        "name": "Mexico City International Airport",
        "lat": 19.4363,
        "lon": -99.0721,
    },
    # ---- South America ----
    "SBGR": {
        "icao": "SBGR",
        "iata": "GRU",
        "name": "Sao Paulo/Guarulhos International Airport",
        "lat": -23.4356,
        "lon": -46.4731,
    },
    "SAEZ": {
        "icao": "SAEZ",
        "iata": "EZE",
        "name": "Buenos Aires Ezeiza International Airport",
        "lat": -34.8222,
        "lon": -58.5358,
    },
    # ---- Europe ----
    "EDDF": {
        "icao": "EDDF",
        "iata": "FRA",
        "name": "Frankfurt am Main Airport",
        "lat": 50.0333,
        "lon": 8.5706,
    },
    "EGLL": {
        "icao": "EGLL",
        "iata": "LHR",
        "name": "London Heathrow Airport",
        "lat": 51.4700,
        "lon": -0.4543,
    },
    "LFPG": {
        "icao": "LFPG",
        "iata": "CDG",
        "name": "Paris Charles de Gaulle Airport",
        "lat": 49.0097,
        "lon": 2.5479,
    },
    "EHAM": {
        "icao": "EHAM",
        "iata": "AMS",
        "name": "Amsterdam Airport Schiphol",
        "lat": 52.3105,
        "lon": 4.7683,
    },
    "LEMD": {
        "icao": "LEMD",
        "iata": "MAD",
        "name": "Adolfo Suarez Madrid-Barajas Airport",
        "lat": 40.4719,
        "lon": -3.5626,
    },
    "LIRF": {
        "icao": "LIRF",
        "iata": "FCO",
        "name": "Rome Fiumicino Leonardo da Vinci Airport",
        "lat": 41.8003,
        "lon": 12.2389,
    },
    "LSZH": {
        "icao": "LSZH",
        "iata": "ZRH",
        "name": "Zurich Airport",
        "lat": 47.4647,
        "lon": 8.5492,
    },
    "EDDM": {
        "icao": "EDDM",
        "iata": "MUC",
        "name": "Munich Airport",
        "lat": 48.3538,
        "lon": 11.7861,
    },
    # ---- Middle East / Africa ----
    "OMDB": {
        "icao": "OMDB",
        "iata": "DXB",
        "name": "Dubai International Airport",
        "lat": 25.2528,
        "lon": 55.3644,
    },
    "OTHH": {
        "icao": "OTHH",
        "iata": "DOH",
        "name": "Hamad International Airport",
        "lat": 25.2731,
        "lon": 51.6081,
    },
    "OERK": {
        "icao": "OERK",
        "iata": "RUH",
        "name": "King Khalid International Airport",
        "lat": 24.9576,
        "lon": 46.6988,
    },
    "HECA": {
        "icao": "HECA",
        "iata": "CAI",
        "name": "Cairo International Airport",
        "lat": 30.1219,
        "lon": 31.4056,
    },
    "FAOR": {
        "icao": "FAOR",
        "iata": "JNB",
        "name": "O. R. Tambo International Airport",
        "lat": -26.1392,
        "lon": 28.2460,
    },
    # ---- Asia ----
    "RJTT": {
        "icao": "RJTT",
        "iata": "HND",
        "name": "Tokyo Haneda Airport",
        "lat": 35.5523,
        "lon": 139.7800,
    },
    "RJAA": {
        "icao": "RJAA",
        "iata": "NRT",
        "name": "Tokyo Narita International Airport",
        "lat": 35.7647,
        "lon": 140.3864,
    },
    "RKSI": {
        "icao": "RKSI",
        "iata": "ICN",
        "name": "Incheon International Airport",
        "lat": 37.4602,
        "lon": 126.4407,
    },
    "VHHH": {
        "icao": "VHHH",
        "iata": "HKG",
        "name": "Hong Kong International Airport",
        "lat": 22.3080,
        "lon": 113.9185,
    },
    "WSSS": {
        "icao": "WSSS",
        "iata": "SIN",
        "name": "Singapore Changi Airport",
        "lat": 1.3502,
        "lon": 103.9944,
    },
    "ZBAA": {
        "icao": "ZBAA",
        "iata": "PEK",
        "name": "Beijing Capital International Airport",
        "lat": 40.0801,
        "lon": 116.5846,
    },
    "ZSPD": {
        "icao": "ZSPD",
        "iata": "PVG",
        "name": "Shanghai Pudong International Airport",
        "lat": 31.1443,
        "lon": 121.8083,
    },
    "VIDP": {
        "icao": "VIDP",
        "iata": "DEL",
        "name": "Indira Gandhi International Airport",
        "lat": 28.5665,
        "lon": 77.1031,
    },
    "VABB": {
        "icao": "VABB",
        "iata": "BOM",
        "name": "Chhatrapati Shivaji Maharaj International Airport",
        "lat": 19.0887,
        "lon": 72.8679,
    },
    "WMKK": {
        "icao": "WMKK",
        "iata": "KUL",
        "name": "Kuala Lumpur International Airport",
        "lat": 2.7456,
        "lon": 101.7099,
    },
    "VTBS": {
        "icao": "VTBS",
        "iata": "BKK",
        "name": "Suvarnabhumi Airport",
        "lat": 13.6900,
        "lon": 100.7501,
    },
    # ---- Oceania ----
    "YSSY": {
        "icao": "YSSY",
        "iata": "SYD",
        "name": "Sydney Kingsford Smith Airport",
        "lat": -33.9461,
        "lon": 151.1772,
    },
    "YMML": {
        "icao": "YMML",
        "iata": "MEL",
        "name": "Melbourne Airport",
        "lat": -37.6690,
        "lon": 144.8410,
    },
    "NZAA": {
        "icao": "NZAA",
        "iata": "AKL",
        "name": "Auckland Airport",
        "lat": -37.0082,
        "lon": 174.7850,
    },
}


def get_by_icao(icao):
    """Return the airport record for a 4-letter ICAO code, or None.

    Case-insensitive. Whitespace is stripped.
    """
    if not isinstance(icao, str):
        return None
    return AIRPORTS.get(icao.strip().upper())


def get_by_iata(iata):
    """Return the airport record for a 3-letter IATA code, or None.

    Case-insensitive. Linear scan (the table is small).
    """
    if not isinstance(iata, str):
        return None
    key = iata.strip().upper()
    for record in AIRPORTS.values():
        if record["iata"].upper() == key:
            return record
    return None


if __name__ == "__main__":
    # Smoke test.
    print(f"AIRPORTS: {len(AIRPORTS)} entries")
    for code in ("kjfk", "EDDF", "wsss"):
        rec = get_by_icao(code)
        print(f"  get_by_icao({code!r}) -> {rec['name'] if rec else None}")
    for code in ("lhr", "SYD", "DXB"):
        rec = get_by_iata(code)
        print(f"  get_by_iata({code!r}) -> {rec['icao'] if rec else None}")
