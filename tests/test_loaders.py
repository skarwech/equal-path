"""Loaders parse the saved raw files by code. Pinned values were read independently from the
publishers' own pages during source discovery (2026-11-14), so a parser bug cannot pass by
agreeing with itself."""

import pytest

from equal_path.loaders import cr_app, cif_report, lung_report, screening, sotkanet, statfin
from equal_path.names import resolve_area


def _one(frame, **match):
    rows = frame
    for column, value in match.items():
        rows = rows[rows[column] == value]
    assert len(rows) == 1, (match, len(rows))
    return rows.iloc[0]


@pytest.fixture(scope="module")
def screening_rows():
    return screening.load()


@pytest.mark.parametrize(
    "geo,code,period,subgroup,num,den,value",
    [
        ("unit", "90", "2024", "all", 28686, 38630, 0.743),  # City of Helsinki
        ("unit", "19", "2024", "all", 20168, 23560, 0.856),  # North Ostrobothnia
        ("national", "FI", "2024", "all", 281369, 344851, 0.816),
        ("national", "FI", "2024", "lang:other_or_missing", 15091, 24803, 0.608),
        ("national", "FI", "2024", "lang:domestic", 266278, 320048, 0.832),
        ("national", "FI", "2024", "edu:primary_or_unknown", 23585, 37116, 0.635),
        ("national", "FI", "2024", "edu:tertiary", 145750, 169721, 0.859),
    ],
)
def test_breast_participation_pinned(screening_rows, geo, code, period, subgroup, num, den, value):
    row = _one(screening_rows, indicator_id="screening_participation_breast", geo_level=geo, county_id=code, period=period, subgroup=subgroup)
    assert (row.numerator, row.denominator) == (num, den)
    assert row.value == pytest.approx(value)


@pytest.mark.parametrize("year,value", [("2020", 0.727), ("2021", 0.745), ("2022", 0.734), ("2023", 0.724), ("2024", 0.743)])
def test_helsinki_breast_trend(screening_rows, year, value):
    row = _one(screening_rows, indicator_id="screening_participation_breast", county_id="90", period=year, subgroup="all")
    assert row.value == pytest.approx(value)


def test_every_programme_covers_22_units(screening_rows):
    for indicator, years in (
        ("screening_participation_breast", ["2020", "2021", "2022", "2023", "2024"]),
        ("screening_participation_cervical", ["2020", "2021", "2022", "2023", "2024"]),
        ("screening_participation_colorectal", ["2022", "2023", "2024"]),
    ):
        for year in years:
            units = screening_rows[(screening_rows.indicator_id == indicator) & (screening_rows.period == year)
                                   & (screening_rows.geo_level == "unit") & (screening_rows.subgroup == "all")]
            assert units.county_id.nunique() == 22, (indicator, year)


def test_cervical_headline_is_age_group_programme(screening_rows):
    row = _one(screening_rows, indicator_id="screening_participation_cervical", county_id="90", period="2024", subgroup="all")
    assert row.numerator == 27514 and row.value == pytest.approx(0.717)


@pytest.mark.parametrize("code,subgroup,count", [("FI", "prog:breast", 1904), ("20", "prog:breast", 17), ("18", "prog:breast", 27)])
def test_screen_detected_cancers_pinned(screening_rows, code, subgroup, count):
    geo = "national" if code == "FI" else "unit"
    row = _one(screening_rows, indicator_id="screening_cancers_detected", geo_level=geo, county_id=code, period="2024", subgroup=subgroup)
    assert row.value == count


def test_screening_totals_reconcile_bottom_up_to_press_release(screening_rows):
    """22 units + Åland, summed across programmes, equal the published national totals."""
    pool = screening_rows[screening_rows.geo_level.isin(["unit", "excluded_unit"]) & (screening_rows.period == "2024")]
    cancers = pool[pool.indicator_id == "screening_cancers_detected"].value.sum()
    precursors = pool[pool.indicator_id == "screening_precursors_detected"].value.sum()
    assert (cancers, precursors) == (2360, 5272)


@pytest.fixture(scope="module")
def lung_rows():
    return lung_report.load()


@pytest.mark.parametrize(
    "code,num,den,value",
    [("11", 67, 355, 0.189), ("90", 491, 1486, 0.330)],  # South Karelia, Helsinki
)
def test_lung_curative_pinned(lung_rows, code, num, den, value):
    row = _one(lung_rows, indicator_id="lung_curative_route_share", geo_level="unit", county_id=code)
    assert (row.numerator, row.denominator, row.value) == (num, den, pytest.approx(value))


@pytest.mark.parametrize("code,value", [("21", 0.185), ("04", 0.356)])  # Lapland lowest, Vantaa-Kerava highest
def test_lung_curative_extremes(lung_rows, code, value):
    assert _one(lung_rows, indicator_id="lung_curative_route_share", geo_level="unit", county_id=code).value == pytest.approx(value)


def test_lung_covers_22_units(lung_rows):
    units = lung_rows[(lung_rows.indicator_id == "lung_curative_route_share") & (lung_rows.geo_level == "unit")]
    assert sorted(units.county_id) == sorted({f"{i:02d}" for i in range(1, 22)} | {"90"})


@pytest.fixture(scope="module")
def app_rows():
    return cr_app.load()


@pytest.mark.parametrize(
    "indicator,geo,code,subgroup,value",
    [
        ("cancer_incidence", "national", "FI", "all", 38853),
        ("cancer_deaths", "national", "FI", "all", 13490),
        ("cancer_incidence", "cooperation_area", "YTA1", "all", 14546),
        ("cancer_incidence", "national", "FI", "site:lung", 2892),
        ("cancer_deaths", "national", "FI", "site:lung", 2275),
    ],
)
def test_app_counts_pinned(app_rows, indicator, geo, code, subgroup, value):
    assert _one(app_rows, indicator_id=indicator, geo_level=geo, county_id=code, subgroup=subgroup).value == value


@pytest.fixture(scope="module")
def cif_rows():
    return cif_report.load()


def test_cif_lung_men_southern_finland(cif_rows):
    row = _one(cif_rows, indicator_id="survival_5y_relative", geo_level="cooperation_area", county_id="YTA1", subgroup="site:lung|sex:male")
    assert (row.value, row.ci_low, row.ci_high) == (pytest.approx(0.163), pytest.approx(0.143), pytest.approx(0.184))


def test_cif_survival_covers_22_units_for_four_series(cif_rows):
    units = cif_rows[(cif_rows.indicator_id == "survival_5y_relative") & (cif_rows.geo_level == "unit")]
    assert units.groupby("subgroup").county_id.nunique().to_dict() == {
        "site:breast|sex:female": 22, "site:colorectal|sex:all": 22, "site:lung|sex:female": 22, "site:lung|sex:male": 22,
    }


def test_cif_stage_coverage_national(cif_rows):
    row = _one(cif_rows, indicator_id="stage_recording_coverage", geo_level="national", county_id="FI", subgroup="all")
    assert (row.numerator, row.denominator, row.value) == (13285, 31731, pytest.approx(0.419))


@pytest.fixture(scope="module")
def sotkanet_rows():
    return sotkanet.load()


def test_sotkanet_units_complete(sotkanet_rows):
    for indicator in ("hpv_vaccination_coverage", "cov_share_aged_75_plus", "cov_education", "primary_care_access"):
        units = sotkanet_rows[(sotkanet_rows.indicator_id == indicator) & (sotkanet_rows.geo_level == "unit")]
        assert units.county_id.nunique() == 22, indicator


@pytest.fixture(scope="module")
def statfin_rows():
    return statfin.load()


def test_statfin_foreign_language_counts_pinned(statfin_rows):
    helsinki = _one(statfin_rows, indicator_id="cov_foreign_language_share", county_id="90")
    national = _one(statfin_rows, indicator_id="cov_foreign_language_share", county_id="FI")
    assert (helsinki.numerator, national.numerator) == (147482, 646392)


def test_statfin_income_covers_22_units(statfin_rows):
    units = statfin_rows[(statfin_rows.indicator_id == "cov_income") & (statfin_rows.geo_level == "unit")]
    assert units.county_id.nunique() == 22 and (units.value > 10000).all()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("City of Helsinki", ("unit", "90")), ("Helsingin kaupunki", ("unit", "90")),
        ("Southwest Finland", ("unit", "05")), ("Pirkanmaan hyvinvointialue", ("unit", "08")),
        ("North Ostrobothnia", ("unit", "19")), ("Lapland", ("unit", "21")),
        ("Koko maa", ("national", "FI")), ("Whole Finland", ("national", "FI")), ("Total", ("national", "FI")),
        ("Åland", ("excluded_unit", "91")), ("Ahvenanmaa", ("excluded_unit", "91")),
        ("Etelä-Suomen yhteistyöalue", ("cooperation_area", "YTA1")),
    ],
)
def test_name_resolution(name, expected):
    assert resolve_area(name) == expected


def test_unknown_name_fails_loudly():
    with pytest.raises(ValueError, match="Atlantis"):
        resolve_area("Atlantis")


# ---------------------------------------------------------------- every loader passes full validation alone

from equal_path.loaders import distance  # noqa: E402

LOADERS = {"screening": screening, "cr_app": cr_app, "cif_report": cif_report,
           "lung_report": lung_report, "sotkanet": sotkanet, "statfin": statfin, "distance": distance}


@pytest.mark.parametrize("name", sorted(LOADERS))
def test_each_loader_output_is_valid_on_its_own(name):
    """Shares in 0-1, values inside their CI, num <= den, no duplicate keys, known codes."""
    from equal_path.config import load_indicator_catalog
    from equal_path.geography import UNIT_CODES
    from equal_path.sources import source_ids
    from equal_path.spine import validate_observations

    catalog = {i.id: i.model_dump() for i in load_indicator_catalog()}
    frame = LOADERS[name].load()
    assert not frame.empty
    assert validate_observations(frame, catalog=catalog, unit_codes=UNIT_CODES, source_ids=source_ids()) == []


@pytest.mark.parametrize(
    "code,subgroup,value,low,high",
    [
        ("02", "site:lung|sex:male", 0.158, 0.104, 0.240),        # Central Uusimaa (spot-check SC05)
        ("05", "site:colorectal|sex:all", 0.685, 0.645, 0.728),   # Southwest Finland (spot-check SC04)
    ],
)
def test_cif_unit_survival_and_ci_pinned(cif_rows, code, subgroup, value, low, high):
    row = _one(cif_rows, indicator_id="survival_5y_relative", geo_level="unit", county_id=code, subgroup=subgroup)
    assert (row.value, row.ci_low, row.ci_high) == (pytest.approx(value), pytest.approx(low), pytest.approx(high))


@pytest.mark.parametrize(
    "indicator,code,year,value",
    [
        ("hpv_vaccination_coverage", "04", "2024", 0.638),  # Vantaa-Kerava (spot-check SC08)
        ("primary_care_access", "18", "2022", 0.423),       # Central Ostrobothnia (spot-check SC09)
    ],
)
def test_sotkanet_shares_pinned(sotkanet_rows, indicator, code, year, value):
    row = _one(sotkanet_rows, indicator_id=indicator, geo_level="unit", county_id=code, period=year)
    assert row.value == pytest.approx(value)


def test_colorectal_population_groups_use_both_sexes_total(screening_rows):
    rows = screening_rows[(screening_rows.indicator_id == "screening_participation_colorectal")
                          & (screening_rows.geo_level == "national") & (screening_rows.period == "2024")]
    assert rows.subgroup.is_unique
    domestic = _one(rows, subgroup="lang:domestic")
    other = _one(rows, subgroup="lang:other_or_missing")
    national = _one(rows, subgroup="all")
    assert domestic.denominator + other.denominator == national.denominator  # sexes combined, not one sex


@pytest.mark.parametrize(
    "subgroup,value,low,high",
    [
        ("site:colorectal|sex:all", 0.700, 0.688, 0.713),  # Whole Finland, Taulukko 15.11 (seen on the live page)
        ("site:lung|sex:female", 0.271, 0.255, 0.288),     # Whole Finland, Taulukko 15.12 (seen on the live page)
    ],
)
def test_cif_national_survival_pinned(cif_rows, subgroup, value, low, high):
    row = _one(cif_rows, indicator_id="survival_5y_relative", geo_level="national", county_id="FI", subgroup=subgroup)
    assert (row.value, row.ci_low, row.ci_high) == (pytest.approx(value), pytest.approx(low), pytest.approx(high))


def test_cif_every_series_has_national_and_five_areas(cif_rows):
    survival = cif_rows[cif_rows.indicator_id == "survival_5y_relative"]
    for subgroup, rows in survival.groupby("subgroup"):
        assert (rows.geo_level == "national").sum() == 1, subgroup
        assert sorted(rows.loc[rows.geo_level == "cooperation_area", "county_id"]) == ["YTA1", "YTA2", "YTA3", "YTA4", "YTA5"], subgroup


def test_cif_english_area_names_resolve():
    for name, code in (("Southern Finland", "YTA1"), ("Eastern Finland", "YTA2"), ("Inland Finland", "YTA3"),
                       ("Western Finland", "YTA4"), ("Northern Finland", "YTA5")):
        assert resolve_area(name) == ("cooperation_area", code)


def test_colorectal_denominator_is_picked_population(screening_rows):
    row = _one(screening_rows, indicator_id="screening_participation_colorectal", geo_level="national",
               county_id="FI", period="2024", subgroup="all")
    assert (row.numerator, row.denominator) == (309871, 421365)  # 419,966 of the 421,365 picked were mailed


def test_participation_table_without_known_denominator_raises():
    import pandas as pd

    table = screening.Table("Wellbeing services counties", "Screening process", "2024", "",
                            pd.DataFrame({"Wellbeing service county": ["Kainuu"], "Selected | N": ["10"],
                                          "Attended | N": ["5"], "Attended | %": ["50.0"]}), "x")
    # (a results table with an attended COUNT but no rate is not a participation table and is skipped)
    with pytest.raises(ValueError, match="denominator"):
        screening._participation("colorectal", table)


def test_prose_stage_coverage_values_parsed_and_flagged(cif_rows):
    """Report text: 'Inland Finland collaborative area (60.4%) ... Pirkanmaa (71.9%)'."""
    area = _one(cif_rows, indicator_id="stage_recording_coverage", geo_level="cooperation_area", county_id="YTA3")
    unit = _one(cif_rows, indicator_id="stage_recording_coverage", geo_level="unit", county_id="08")
    assert (area.value, unit.value) == (pytest.approx(0.604), pytest.approx(0.719))
    assert area.quality_flag == unit.quality_flag == "transcribed"
    others = cif_rows[(cif_rows.indicator_id == "stage_recording_coverage") & (cif_rows.geo_level == "unit")]
    assert list(others.county_id) == ["08"]  # never copied onto Kanta-Häme or South Ostrobothnia
