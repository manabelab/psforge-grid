# Test Fixtures

This directory contains test files for the psforge-grid parsers (PSS/E RAW, MATPOWER, CPAT).

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

### WEST10peak.pop - IEEJ WEST 10-Machine Model (CPAT .pop format)

- **Source**: CPAT-GUI standard model data (IEEJ WEST 10-machine peak-load model)
- **Format**: CPAT .pop (ZIP archive containing XML data)
- **Description**: IEEJ standard power system model with 10 generators on a 500/275 kV network, used for validating the PopParser and ACPF E2E pipeline

| Component | Count |
|-----------|-------|
| Buses | 27 |
| Generators | 10 |
| Loads | 17 |
| Branches | 35 |
| Base MVA | 1000.0 |

### cpat_model11.dyna - CPAT Manual Model System (dyna card format)

- **Source**: CPAT Manual p.26 (programmatically generated with correct column alignment)
- **Format**: CPAT dyna (Fortran fixed-column 80-character card format)
- **Description**: 10-node model system from the CPAT manual, used for validating the DynaParser and individual card parsers

| Component | Count |
|-----------|-------|
| Buses | 10 (nodes 1010-1100) |
| Generators | 4 (G-1, G-2, G-3, SWING) |
| Loads | 2 (LOAD-9, SWING) |
| Branches | 14 (9 transmission lines + 5 transformers) |
| Base MVA | 1000.0 |
| Swing Node | 1100 |

## Format Notes

The PSS/E parser supports both v33 and v34 formats:

- **v33 format**: Bus data starts immediately after the 3-line case identification header, without an explicit "BEGIN BUS DATA" marker
- **v34 format**: Uses explicit section markers like "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA"

Both formats use similar data field layouts within each section, with v34 adding some additional fields (e.g., NAME field in branch data).

The CPAT `.pop` format is a ZIP archive containing XML files. The `data.pnsd` file inside the archive holds the electrical data (nodes, branches, generators, loads). XML tag names correspond 1:1 to the CPAT card format field names (e.g., `<Z1r>`, `<Xd>`, `<Gmva>`).

The CPAT `.dyna` card format uses Fortran fixed-column (80-character) lines with card type prefixes (T, X, N, G1-G5) and section terminators (TEND, XEND, NEND, GEND, STOP).

## References

- IEEE Test Systems: https://icseg.iti.illinois.edu/power-cases/
- Texas A&M Electric Grid Test Case Repository: https://electricgrids.engr.tamu.edu/electric-grid-test-cases/
- PSS/E Documentation: Siemens PTI PSS/E Program Operation Manual
- CPAT: https://www.jpower.co.jp/bs/cpat/
