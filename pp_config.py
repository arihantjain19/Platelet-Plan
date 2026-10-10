"""Parameters for the synthetic district network and the simulator.

Every number here is either taken from a cited source (see DATA.md) or is an
explicit, documented ASSUMPTION. Change them here; nothing else hard-codes values.
"""
from dataclasses import dataclass

# --- Product ---------------------------------------------------------------
SHELF_LIFE_DAYS = 5  # random-donor platelets, 20-24 C with agitation (e-RaktKosh)

# --- Simulation period -----------------------------------------------------
START = "2021-01-01"
END = "2025-12-31"
TRAIN_END = "2023-12-31"   # models are fitted on 2021-2023
TUNE_END = "2024-12-31"    # policy parameters are tuned on 2024
# 2025 is the untouched test year

# All-India dengue cases by year, NCVBDC (MoHFW). Used ONLY to set the relative
# severity of each simulated year (real data, ref 6).
NCVBDC_ALL_INDIA_CASES = {2021: 193_245, 2022: 233_251, 2023: 289_235, 2024: 233_519, 2025: 121_824}

# ASSUMPTION: a mid-sized district records ~1,500 dengue cases in an average year.
DISTRICT_CASES_AVG_YEAR = 1_500
# ASSUMPTION: dengue season peaks in late September / October (post-monsoon),
# modelled as a Gaussian bump over the year (week of peak, spread in weeks).
DENGUE_PEAK_WEEK = 40
DENGUE_SPREAD_WEEKS = 5.5
DENGUE_BASELINE_SHARE = 0.15  # share of yearly cases spread evenly (sporadic cases)
DENGUE_REPORTING_LAG_DAYS = 7  # surveillance figures reach the centre one week late


@dataclass(frozen=True)
class Centre:
    code: str
    name: str
    lat: float
    lon: float
    base_demand: float      # mean platelet units issued per day outside dengue season
    dengue_sensitivity: float  # extra demand per (district weekly cases / 100)
    donations: float        # mean whole-blood donations per day (each can yield one platelet unit)


# ASSUMPTION: five fictional blood centres in one district (coordinates placed
# around Patiala, Punjab, for realistic road distances). Sizes are invented but
# proportionate: one medical-college centre and four smaller centres.
CENTRES = [
    Centre("A", "Centre A - Medical college", 30.3398, 76.3869, 11.0, 10.0, 24.0),
    Centre("B", "Centre B - District hospital", 30.3550, 76.4300, 4.5, 4.0, 10.0),
    Centre("C", "Centre C - Sub-district hospital", 30.4500, 76.5900, 2.8, 2.5, 6.0),
    Centre("D", "Centre D - Charitable blood centre", 30.2600, 76.3000, 2.2, 2.0, 5.5),
    Centre("E", "Centre E - Sub-district hospital", 30.1900, 76.6100, 1.4, 1.2, 3.5),
]

# Weekday multipliers for demand (Mon..Sun). ASSUMPTION: elective surgery and
# chemotherapy concentrate on weekdays; Sunday lowest.
DOW_FACTOR = [1.12, 1.10, 1.06, 1.06, 1.04, 0.86, 0.76]
# Weekday multipliers for donations (camps on weekends). ASSUMPTION.
DOW_DONATION = [0.95, 0.95, 0.95, 0.95, 1.0, 1.15, 1.05]

DEMAND_DISPERSION = 8.0  # negative-binomial shape; smaller = noisier. ASSUMPTION.

# --- Road travel (no network access needed) --------------------------------
ROAD_FACTOR = 1.35      # road distance / straight-line distance. ASSUMPTION.
ROAD_SPEED_KMH = 40.0   # average speed incl. city traffic. ASSUMPTION.
MAX_TRANSFER_MINUTES = 90

# --- Status quo calibration -------------------------------------------------
# Published discard rates at government / teaching-hospital centres: 45-61%
# (refs 1-3). The status-quo share is calibrated so the simulated expiry rate
# lands in this range (see plateletplan/calibrate.py).
STATUS_QUO_TARGET_EXPIRY = 0.45
