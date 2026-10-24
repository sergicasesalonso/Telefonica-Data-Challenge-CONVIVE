# CONVIVE · Data review and cleaning plan (Iteration 1)

Applies to the 12 Telefónica Tech files described in "Smart Steps - Challenge 2026" (M1 to M3 mobility, T1 to T9 tourism), January 2023 to August 2025. The checks in steps 2 and 3 are automated in `convive.py` (`review()`) and run in section 4 of the notebook.

## 1. Reception (first day of data access)
- Store the files only in `data/raw/` on team computers or the restricted project Drive, never on GitHub or public links (confidentiality agreement).
- Write down for each file: name, format, separator, size, number of rows, date received.
- Read code columns (`cod_barrio`, `cod_municipio`, `barrio_*`, `municipio_*`, `mes`) as text, so leading zeros are kept (`08019`).

## 2. Structure checks (automated)

| # | Check | Problem it detects | Action |
|---|---|---|---|
| S1 | Columns match the official description | Renamed, missing or extra columns | Map names in `SCHEMAS`; ask the mentor if a column is missing |
| S2 | Values of `origen` and `tipo_visitante` | Spelling or new categories | Normalise spelling; ask about new categories |
| S3 | Period covered (32 months / all days) | Missing months or days | Flag them; compare only complete equivalent periods |
| S4 | Neighbourhood codes found on the 73-neighbourhood map | Code format or changes between years | Build a correspondence table; check the code format "8019 + district + neighbourhood" |

## 3. Content checks (automated)

| # | Check | Problem it detects | Action |
|---|---|---|---|
| C1 | Duplicated rows | Double counting | Drop exact duplicates and log how many |
| C2 | Empty / NA values | NA = segments of fewer than 15 people grouped for privacy | Keep as NA; never read as 0 visitors |
| C3 | Share of 0 in `viajes` | Trips below 15 are reported as 0 | Report the share; never read 0 as "no mobility"; aggregate to district or month if the share is high |
| C4 | Negative values | Data errors | Ask the mentor; exclude until clarified |

Trigger (Follow-up Register, R1): more than 10% of records with nulls or inconsistencies in any file, or neighbourhood codes that do not match the map → exclude or flag the affected periods and neighbourhoods, aggregate at district or month level, and explain the limit.

## 4. Cross-file consistency checks (automated, `analysis.consistency_checks`)
Unique visitors are not additive, but they must respect some inequalities:

| # | Check | Action if it fails |
|---|---|---|
| X1 | A neighbourhood's highest daily unique visitors ≤ its monthly unique visitors (T5 vs T4) | Ask the mentor; do not combine both files until clarified |
| X2 | The largest neighbourhood ≤ the whole city in the same month (T4 vs T1) | Same |
| X3 | Sum of neighbourhoods / city total, per day (T5 vs T2) ≥ 1. It equals the average number of neighbourhoods a visitor passes through | Report it; values below 1 indicate a definition problem |

## 5. Analysis rules (from the data description)
- Trips (mobility) and unique visitors (tourism) are different measures: never mix them in one indicator.
- Published zeros in mobility mean "fewer than 15 trips". Models of trip flows must treat them as censored values, not real zeros (see the censoring-aware gravity model in the notebook, §7.1).
- Unique visitors cannot be summed over days or neighbourhoods. City totals come from T1/T2, not from adding up T4/T5.
- `origen` is the visitor segment, not where the trip starts.
- Regional visitors are always excursionists; overnight stays (T3) only exist at municipality level, for international and national visitors.
- Results show patterns and differences, not causes.

## 6. Record
Each problem found is logged with file, check, rows affected and action taken, and summarised in the notebook. Issues that affect scope or dates go to the Follow-up Register.
