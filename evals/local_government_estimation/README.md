# local_government_estimation

**Status: demo.** Truth values reflect publicly-reported counts at the time of writing but local-government facts change frequently (city charters revise council size, terms get amended). Re-verify before any specific finding is cited.

Fermi-style calibration but on local-government scale: typical city council size, US-wide count of school boards, mayoral term lengths, etc. Smaller numbers than `fermi_civic_estimation`, more jurisdictional variation, exposes a different failure mode (the model probably has more uncertainty about local facts than federal ones, so coverage rates should sit closer to nominal 0.80).

## Scoring
- `fermi_calibration` — same Winkler-based scorer as `fermi_civic_estimation`. See that eval's README for the math.
