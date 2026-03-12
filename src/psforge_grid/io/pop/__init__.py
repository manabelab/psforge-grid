"""CPAT .pop format parser subpackage.

Parses CPAT-GUI native format (.pop = ZIP archive containing XML files)
into psforge-grid System objects.

File structure inside .pop:
    - data.pnsd: Electrical parameters (impedances, generator data, etc.)
    - *.pnsw: Topology (single-line diagram with Cluster objects)
    - *.pnsj: Operating point (voltages, P/Q dispatch, swing bus designation)
"""
