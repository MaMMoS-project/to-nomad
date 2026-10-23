# Example input data

**Full source upload on NOMAD: [MaMMoS_IFW_SEM](https://nomad-lab.eu/gui/upload/id/6NzAe8uWS5SCsuKNvl7EUw)**
([entry IFW-SEM-Data](https://nomad-lab.eu/gui/upload/id/6NzAe8uWS5SCsuKNvl7EUw/entry/id/9JfRldglcycgSpsOe7eU8y6zRP4Z))

*(both links verified accessible without login)*

## 22632_01_CBS.tif

A scanning electron microscope (SEM) micrograph, 1536x1094 pixels, 8-bit
grayscale, uncompressed TIFF (1.6 MB).

- **Source:** the published NOMAD upload `MaMMoS_IFW_SEM`
  (upload id `6NzAe8uWS5SCsuKNvl7EUw`), entry `IFW-SEM-Data`
  (`SEM_measurements_IFW`, entry id
  `9JfRldglcycgSpsOe7eU8y6zRP4Z`).
- **Retrieved via** the NOMAD REST API (2026-10-22):
  `GET https://nomad-lab.eu/prod/v1/api/v1/uploads/6NzAe8uWS5SCsuKNvl7EUw/raw/IFW_SEM_RawData/22632_01_CBS.tif`
- **Provenance / license:** published data of the EU project MaMMoS
  (grant no. 101135546); provided by IFW Dresden (Magnetic Materials
  Group).
- **Use:** input for [examples/from_sem_image.py](../from_sem_image.py),
  which stores the image in a MaMMoS EntityCollection and exports it as
  NOMAD archive YAML + HDF5 (see the repository README, section
  "Plotting x-y curves in NOMAD").

## Co2Fe2H4_structure.cif

Crystal structure of Co2Fe2H4 (hexagonal, space group P6_3/mmc, 10 atoms
per unit cell), exported with VESTA; CIF text, 1.5 KB.

- **Source:** the published NOMAD upload
  `MaMMoS_DFT_MC_Atomistic+Spindynamic-calculations_UU`
  (upload id `xRAGFnhFTAqWHdSdpmMcCg`, main author Heike Herper /
  Mohammad Nur Hassan / Alena Vishina, Uppsala University), file
  `datasets/Co2Fe2H4/structure.cif`.
  GUI entry view:
  https://nomad-lab.eu/gui/upload/id/xRAGFnhFTAqWHdSdpmMcCg/entry/id/xTMM7Ww9Yp7YlZk2lbj-NQGHB_UZ
- **Retrieved via** the NOMAD REST API (2026-10-23), extracted from the
  local copy `Co2Fe2H4.zip`:
  `GET https://nomad-lab.eu/prod/v1/api/v1/uploads/xRAGFnhFTAqWHdSdpmMcCg/raw/datasets/Co2Fe2H4/structure.cif`
- **Provenance / license:** published data of the EU project MaMMoS
  (grant no. 101135546); DFT and Monte-Carlo calculations performed at
  Uppsala University.
- **Use:** input for [examples/from_cif_structure.py](../from_cif_structure.py),
  which ships the CIF in a NOMAD upload so the entry overview shows a 3-D
  structure preview (see the repository README, section
  "Structure preview from a CIF file").
