# Example input data

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
  Group). Entry main author: Santa Pile.
- **Use:** input for [examples/from_sem_image.py](../from_sem_image.py),
  which stores the image in a MaMMoS EntityCollection and exports it as
  NOMAD archive YAML + HDF5 (see the repository README, section
  "Plotting x-y curves in NOMAD").
