"""Distance to the nearest university hospital (F3 covariate): population-weighted, derived."""

import pytest

from equal_path.loaders import distance
from equal_path.observations import load_observations


@pytest.fixture(scope="module")
def rows():
    return distance.load()


def test_haversine_matches_known_great_circle_distances():
    # Helsinki cathedral -> Oulu cathedral ~ 539 km; Helsinki -> Tampere ~ 161 km (great circle)
    assert distance.haversine_km(60.1708, 24.9524, 65.0142, 25.4719) == pytest.approx(540, rel=0.06)
    assert distance.haversine_km(60.1708, 24.9524, 61.4981, 23.7608) == pytest.approx(161, rel=0.03)


def test_five_university_hospitals_parsed():
    hospitals = distance.hospitals()
    assert len(hospitals) == 5
    for name, (lat, lon) in hospitals.items():
        assert 60 < lat < 66 and 22 < lon < 28, name


def test_every_mainland_municipality_mapped_and_population_sums_to_county(rows):
    municipalities = distance.municipalities()
    assert len(municipalities) == 308 - 16  # mainland municipalities (Åland has 16)
    store = load_observations()
    populations = store[(store.indicator_id == "cov_population") & (store.geo_level == "unit")].set_index("county_id").value
    sums = municipalities.groupby("unit").population.sum()
    assert sums.to_dict() == populations.to_dict()


def test_one_derived_value_per_unit(rows):
    assert len(rows) == 22 and rows.county_id.is_unique
    assert (rows.quality_flag == "derived").all()
    assert (rows.indicator_id == "cov_distance_university_hospital_km").all()


def test_hospital_counties_are_close(rows):
    km = rows.set_index("county_id").value
    for host in ("05", "08", "13", "19", "90"):  # Turku, Tampere, Kuopio, Oulu, Helsinki
        assert km[host] < 60, host


@pytest.mark.parametrize(
    "code,city,hospital",
    [   # spec F9: three hand-checked distances within +/-10 % (main city -> nearest university hospital)
        ("17", (63.0951, 21.6165), "TAYS Tampere"),   # Pohjanmaa: Vaasa -> Tampere
        ("11", (61.0587, 28.1887), "HUS Helsinki"),   # Etelä-Karjala: Lappeenranta -> Helsinki
        ("20", (64.2273, 27.7285), "KYS Kuopio"),     # Kainuu: Kajaani -> Kuopio
    ],
)
def test_hand_checked_distances_within_10_percent(rows, code, city, hospital):
    expected = distance.haversine_km(*city, *distance.hospitals()[hospital])
    assert rows.set_index("county_id").value[code] == pytest.approx(expected, rel=0.10)


def test_centroid_of_an_asymmetric_polygon_is_area_weighted():
    """Review D-1: an L-shape (2x1 block plus a 1x1 block on top) has its centroid at 5/6 of a degree
    from the corner on both axes, which neither the bounding-box centre nor the vertex mean gives."""
    ell = {"type": "Polygon", "coordinates": [[[25, 65], [27, 65], [27, 66], [26, 66], [26, 67], [25, 67], [25, 65]]]}
    lat, lon = distance.centroid(ell)
    assert (lat, lon) == (pytest.approx(65 + 5 / 6, abs=1e-9), pytest.approx(25 + 5 / 6, abs=1e-9))


def test_centroid_of_a_multipolygon_weights_parts_by_area():
    small = [[[25, 65], [26, 65], [26, 66], [25, 66], [25, 65]]]          # area 1, centre (25.5, 65.5)
    large = [[[30, 65], [32, 65], [32, 67], [30, 67], [30, 65]]]          # area 4, centre (31, 66)
    lat, lon = distance.centroid({"type": "MultiPolygon", "coordinates": [small, large]})
    assert (lat, lon) == (pytest.approx((65.5 + 4 * 66) / 5, abs=1e-9), pytest.approx((25.5 + 4 * 31) / 5, abs=1e-9))
