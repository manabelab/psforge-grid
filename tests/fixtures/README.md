# Test Fixtures

This directory contains test files for the psforge-grid parsers (PSS/E RAW, MATPOWER, OpenDSS).

## Data Sources

### ieee9.raw - IEEE 9-Bus System (v34 format)

- **Source**: GitHub - todstewart1001/PSSE-24-Hour-Load-Dispatch-IEEE-9-Bus-System-
- **URL**: https://github.com/todstewart1001/PSSE-24-Hour-Load-Dispatch-IEEE-9-Bus-System-
- **Format**: PSS/E v34
- **Description**: IEEE 9-bus test system with 3 generators, 3 loads, 6 transmission lines, and 3 transformers

| Component | Count |
|-----------|-------|
| Buses | 9 |
| Generators | 3 |
| Loads | 3 |
| Branches | 9 (6 lines + 3 transformers) |
| Total Generation | ~320 MW |
| Total Load | 315 MW |

### ieee14.raw - IEEE 14-Bus System (v33 format)

- **Source**: ITI/models repository (University of Washington Archive)
- **URL**: https://github.com/ITI/models/blob/master/electric-grid/physical/reference/ieee-14bus/models/ieee-14-bus.raw
- **Format**: PSS/E v33
- **Original Date**: August 19, 1993
- **Description**: Classic IEEE 14-bus test system with 5 generators, 11 loads, 17 transmission lines, 3 transformers, and 1 shunt capacitor

| Component | Count |
|-----------|-------|
| Buses | 14 |
| Generators | 5 |
| Loads | 11 |
| Branches | 20 (17 lines + 3 transformers) |
| Shunts | 1 (19 MVAr capacitor at bus 9) |
| Total Generation | ~272 MW |
| Total Load | ~259 MW |

### ieee118_powsybl.raw - IEEE 118-Bus System (v33 format, alternative source)

- **Source**: powsybl/powsybl-distribution repository
- **URL**: https://github.com/powsybl/powsybl-distribution/blob/main/resources/PSSE/IEEE_118_bus.raw
- **Format**: PSS/E v33
- **Original Date**: August 25, 1993
- **Description**: Large-scale IEEE 118-bus test system used for parser tolerance verification

| Component | Count |
|-----------|-------|
| Buses | 118 |
| Generators | 54 |
| Loads | 99 |
| Branches | 186 |
| Shunts | 14 |
| Total Generation | ~4374 MW |
| Total Load | ~4242 MW |

### 39bus.raw - New England 39-Bus System (PSS/E v34 format)

- **Source**: https://github.com/NatLabRockies/ParaEMT_public `models/39bus_psse/39bus.raw`
- **Terms**: BSD 3-Clause. See `NOTICE.md` in this directory -- the notice must travel with the file.
- **Format**: PSS/E v34, written by `PSS(R)E-34.8` on 2022-12-09
- **Description**: The only v34 fixture, and the only one written by PSS/E itself. Tests that read
  only files psforge wrote cannot show that psforge reads what other tools produce. It also carries
  a v34 `SYSTEM-WIDE DATA` block (GENERAL / GAUSS / NEWTON / ADJUST / TYSL / RATING), which no other
  fixture has.

| Component | Count |
|-----------|-------|
| Buses | 39 (1 slack / 9 PV / 29 PQ) |
| Generators | 10 |
| Loads | 19 |
| Branches | 46 (34 lines + 12 transformers) |
| Shunts | 2 |
| Base MVA | 100.0 |
| Total Load | ~6150 MW |

Note: every bus declares `BASKV = 1.0`; the model is expressed in per-unit. That is what the file
says, not a parsing artefact.
### ACTIVSg2000.raw - Synthetic Texas 2000-Bus System (v33 format)

- **Source**: Texas A&M University Electric Grid Test Case Repository
- **URL**: https://electricgrids.engr.tamu.edu/electric-grid-test-cases/activsg2000/
- **Format**: PSS/E v33
- **Terms**: "This power system dataset is synthetic and does not represent any actual grid.
  It is provided by Texas A&M University researchers free for commercial or non-commercial use."
  The repository asks users to cite the corresponding papers; developed with support of the
  U.S. DOE ARPA-E GRID DATA program, and contains no CEII.
- **Description**: Synthetic 2000-bus model geographically sited on the footprint of the Texas
  grid. Used by `test_large_case.py` to exercise the RAW parser and writer at a scale the IEEE
  fixtures cannot reach: eight areas, ten voltage levels, and a mix of in-service and
  out-of-service generators.

| Component | Count |
|-----------|-------|
| Buses | 2000 (1 slack / 484 PV / 1515 PQ) |
| Generators | 544 (432 in service) |
| Loads | 1350 |
| Branches | 3206 (2345 lines + 861 transformers) |
| Shunts | 4 |
| Base MVA | 100.0 |
| Total Load | ~67109 MW / ~19014 MVAr |
| Voltage Levels | 13.2, 13.8, 18, 20, 22, 24, 115, 161, 230, 500 kV |

### psforge-grid JSON Files (.psfg.json)

The following `.psfg.json` files are generated from the source fixtures above and serve as reference data for the psforge-grid native JSON format.

#### ieee14.psfg.json - IEEE 14-Bus System

- **Source**: Generated from `ieee14.raw`
- **Format**: psforge-grid JSON v1.0
- **Description**: JSON representation of the IEEE 14-bus system with all buses, branches, generators, loads, and shunts

| Component | Count |
|-----------|-------|
| Buses | 14 |
| Generators | 5 |
| Loads | 11 |
| Branches | 20 |
| Shunts | 1 |

#### ieee9.psfg.json - IEEE 9-Bus System

- **Source**: Generated from `ieee9.raw`
- **Format**: psforge-grid JSON v1.0

| Component | Count |
|-----------|-------|
| Buses | 9 |
| Generators | 3 |
| Loads | 3 |
| Branches | 9 |

#### ieee14_contingencies.psfg.json - N-1 Contingency Scenarios

- **Source**: Scenario definitions referencing `ieee14.psfg.json` as base case
- **Format**: psforge-grid-scenario v1.0
- **Description**: Example scenario file for base case + differential modification pattern

| Scenario | Description |
|----------|-------------|
| N-1_Line_1-5 | Line 1-5 outage (branch status=0) |
| N-1_Line_2-3 | Line 2-3 outage (branch status=0) |
| heavy_load_bus14 | Double load at bus 14 |

## Format Notes

The PSS/E parser supports both v33 and v34 formats:

- **v33 format**: Bus data starts immediately after the 3-line case identification header, without an explicit "BEGIN BUS DATA" marker
- **v34 format**: Uses explicit section markers like "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA"

Both formats use similar data field layouts within each section, with v34 adding some additional fields (e.g., NAME field in branch data).



The psforge-grid `.psfg.json` format uses JSON with explicit metadata:
- `"format": "psforge-grid"` identifies the file format (prevents confusion with pglib-uc JSON)
- `"version": "1.0"` for schema versioning
- `None` fields are omitted by default for compact output
- Field names use snake_case with unit suffixes (`_pu`, `_mw`, `_kv`, `_deg`)

The scenario format (`"format": "psforge-grid-scenario"`) references a base case `.psfg.json` file and defines differential modifications (target + match + set) to generate multiple System variants.

## References

- IEEE Test Systems: https://icseg.iti.illinois.edu/power-cases/
- Texas A&M Electric Grid Test Case Repository: https://electricgrids.engr.tamu.edu/electric-grid-test-cases/
- PSS/E Documentation: Siemens PTI PSS/E Program Operation Manual
