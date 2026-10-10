# Data sources and generated data

## ⚠️ What is real and what is synthetic

| Data | Real or synthetic | Used for |
|---|---|---|
| Platelet discard rates at 5 Indian blood centres (4.7%–61.1%) | **Real**, published studies (refs 1–5) | Calibrating the status-quo policy (target 45% expiry) and as context |
| All-India dengue cases by year, 2021–2025 (NCVBDC) | **Real** (ref 6) | Relative severity of each simulated dengue year |
| Platelet shelf life: 5 days at 20–24 °C with agitation | **Real** (ref 10) | Simulator shelf life |
| Inter-blood-bank transfers allowed (MoHFW, 2015) | **Real** (ref 9) | Justifies the transfer feature |
| District daily dengue cases | **Synthetic** | Forecast input; drives demand |
| Daily platelet demand and donations at 5 centres | **Synthetic** | Training, tuning and testing |
| Centre locations and road travel times | **Synthetic** (fictional centres placed around Patiala, Punjab) | Transfer costs |

No public dataset of daily platelet demand at Indian blood centres exists, so the centre-level data is generated. Synthetic data validates the **method**; it does **not** prove a real-world saving. The next step is to test on a real centre's anonymised issue register, which the `register` command and the app's "Use your own register" tab support.

## How the data is generated (`pp_data.py`, seed 7)

All parameters live in `pp_config.py`. Each item marked ASSUMPTION is a choice we made, not a measured fact.

1. **Dengue cases (district, daily).** Each year's total = 1,500 cases (ASSUMPTION: a mid-sized district) × that year's all-India cases ÷ the 2021–2025 mean (real NCVBDC ratio). 85% of cases follow a seasonal bump peaking in week 40 (late Sept/Oct, spread 5.5 weeks; ASSUMPTION: post-monsoon season). 15% are spread evenly through the year. Daily counts are Poisson-distributed.
2. **What the centre sees.** It sees the 7-day case total, reported **7 days late** (ASSUMPTION: surveillance lag).
3. **Platelet demand (per centre, daily).** Mean = base demand × weekday factor + dengue sensitivity × (true weekly cases ÷ 100). Daily values follow a negative binomial (dispersion 8), giving realistic day-to-day noise. Base demand runs from 11/day (medical college) to 1.4/day (sub-district hospital). Weekday factors run from 1.12 on Monday to 0.76 on Sunday (ASSUMPTION).
4. **Donations (per centre, daily).** Poisson, with mean about 2× base demand and a weekend bump for camps (ASSUMPTION). Each donation can yield one random-donor platelet unit.
5. **Travel time.** Straight-line distance × 1.35 road factor at 40 km/h (ASSUMPTION; no OpenStreetMap routing). Transfers are only allowed within 90 minutes.
6. **Status quo.** Centres make platelets from a fixed share of donations. The share is calibrated by bisection so that the simulated expiry rate on 2021–2023 reaches the published 45%. The result is a share of 1.0, meaning platelets are made from every donation, which gives 44–50% expiry.

Generated files: `dengue_district.csv`, `centre_daily.csv`, `travel_minutes.csv`, `sample_register.csv` (Centre B, 2024–2025, in the format the register feature accepts). Regenerate with `python pp_cli.py generate`.

## What the synthetic data cannot show

- Real demand patterns: how much dengue actually drives platelet use at a given centre, real weekday effects, and hospital-specific events.
- Blood-group mismatch, which is not modelled.
- Real behaviour of staff, transport and donors.

## References

1. Kaur L, Bassi R, Sidhu V, Garg M, Sidhu B. Evaluation of whole blood and blood components discard in a government hospital. *Asian J Pharm Clin Res* 2025;18(3). https://www.journals.innovareacademics.in/index.php/ajpcr/article/download/53772/31656/253063
2. Kori S, Yadav YR, Banerjee S, Bari V. Analysis of the total wastage of blood bags and various blood components. *Int J Community Med Public Health* 2024;11(2):904–907. https://www.ijcmph.com/index.php/ijcmph/article/download/12142/7332/56439
3. Patil P, Bhake A, Hiwale K. Analysis of discard of whole blood and its components. *Int J Res Med Sci* 2016;4(2):477–481. https://www.msjonline.org/index.php/ijrms/article/view/523
4. Gaude NK et al. Blood and blood component discards: an Indian tertiary-care blood bank study. *Bioinformation* 2026;22(7). https://www.bioinformation.net/022/973206300224047.htm
5. Luhar RK, Shah RJ, V H. Discard rate in blood transfusion service. *Int J Med Sci Public Health* 2020;9(7):426–430. https://imsear.searo.who.int/items/bc10cffb-703e-4bdd-8a82-802129c611e3/full
6. NCVBDC, MoHFW. Dengue cases and deaths in the country, 2021–2026. https://ncvbdc.mohfw.gov.in/Doc/Dengue-Cases-deaths-2021-2026-till-April.pdf
7. Pham T, Tibshirani R et al. Big data modeling to predict platelet usage and minimize wastage. *PNAS* 2018. https://www.amstat.org/asa/files/pdfs/pressreleases/2018-New-Statistical-Model-Forecast-Future-Demand-of-Blood-Platelets.pdf
8. Schilling M et al. Reduction of platelet outdating and shortage by forecasting demand. *JMIR Med Inform* 2022;10(2):e29978. https://medinform.jmir.org/2022/2/e29978
9. Medical Dialogues. Health Ministry permits transfer of blood between blood banks, 19 Oct 2015. https://medicaldialogues.in/health-ministry-permits-transfer-of-blood-between-blood-banks
10. e-RaktKosh, MoHFW. https://eraktkosh.mohfw.gov.in/

## Licences of data used

- NCVBDC figures are Government of India public data, used here as yearly totals only.
- The published studies are cited for their summary figures only; no data from them is redistributed.
- All generated data CSVs is released under this repository's MIT licence.
