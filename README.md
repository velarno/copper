# Copper CLI tool

Copper CLI is a command-line tool for interacting with Copernicus Climate Data Store (CDS) datasets. It provides the following features:

## Features

- **Browse and Search Datasets**
  - List all available Copernicus datasets from a local DuckDB database.
  - Search datasets using full-text queries.
  - Display results in table, JSON, CSV, or TSV formats.

- **Download Data**
  - Download data from the CDS using dataset names and custom time periods.
  - Supports chunked downloads and progress reporting.
  - Flexible request types for different data needs.

- **Extract Data**
  - Extract downloaded `.zip` files containing NetCDF (`.nc`) files.
  - Convert NetCDF files to Parquet format for efficient analysis.
  - Organize extracted data by year and dataset.

- **Utilities**
  - Ensures required dependencies (like Playwright) are installed for scraping.
  - Temporary storage and caching for dataset metadata.

## Example Usage

First, log into the [CDS website](https://cds.climate.copernicus.eu/) and go to [the CDS API page](https://cds.climate.copernicus.eu/how-to-api), create the `.cdsapirc` file and store it in your `$HOME` directory

### Getting the dataset ID

If you already know which dataset you need, great ! Else, you can do
```bash
cdsfetch datasets init
```
This will install playwright, and browse the CDS datasets page to get a list of existing datasets.

To search datasets, use keywords, e.g.
```
copper datasets search "sea level"
```
This returns a table:
```bash
                                        Search Results for 'sea level'                                         
╭───────┬────────────────────────────────────────────────────┬───────────────────────┬────────────────────────╮
│ Score │ ID                                                 │ Title                 │ Description            │
├───────┼────────────────────────────────────────────────────┼───────────────────────┼────────────────────────┤
│ 1.59  │ satellite-sea-level-global                         │ Sea level gridded     │ This dataset provides  │
│       │                                                    │ data from satellite   │ gridded daily and      │
│       │                                                    │ observations for the  │ monthly mean global    │
│       │                                                    │ global ocean from     │ ...                    │
│       │                                                    │ 1993 to present       │                        │
├───────┼────────────────────────────────────────────────────┼───────────────────────┼────────────────────────┤
│ 1.39  │ sis-water-level-change-indicators-cmip6            │ Global sea level      │ This dataset provides  │
│       │                                                    │ change indicators     │ statistical indicators │
│       │                                                    │ from 1950 to 2050     │ of tides, storm...     │
│       │                                                    │ derived from          │                        │
│       │                                                    │ reanalysis and high   │                        │
│       │                                                    │ resolution CMIP6      │                        │
│       │                                                    │ climate projections   │                        │
```
If you need a more compact representation, you can also use `--format`, e.g.
```bash
cdsfetch datasets search 'sea level' -l 2 --format json | jq -r '.[].id'
````
Returns only the ids of the first 2 matches, here:
```bash
satellite-sea-level-global
sis-water-level-change-indicators-cmip6
```

### Download data (required dataset id)

```
copper cds download <dataset_name> --start-period 2000 --end-period 2020
```
For example, `copper cds download sis-water-level-change-indicators-cmip6` downloads all years from 1950 to 2050 (pretty slow, concurrent dl isn't ready yet)

### Extract downloaded data

By default the data uses the `.nc` format, and is stored inside `/tmp/cds_downloads/` on MacOS & Linux (windows version not yet tested). To convert them to "nice" formats (like `parquet` or `csv`), you can use

```
copper cds extract <dataset_name>
```

For more details on each command and its options, use the `--help` flag, e.g.: