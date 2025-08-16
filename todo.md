# TODO

## API related commands

- [x] Add a subcommand that uses the [STAC Api](https://cds.climate.copernicus.eu/stac-browser/collections/reanalysis-era5-single-levels?.language=en) to discover variables & constraints easily from online JSON data
- [ ] Add a subcommand that allows "planning" the CDS download to check the provided schema against documented constraints
- [ ] Add async sessions to allow for faster fetching (aiosqlite, with httpx async)
- [x] Add a list of mandatory inputs for a template
- [ ] Make sure each cost computation is saved in the history & current template
- [x] Create a way to import template from JSON file
- [ ] Add logic to fetch the budget from costing api if it is not set so far (dummy value of -1)
- [x] Create a basic template optimizer

## Db related

- [ ] Handle duplicate values better
- [ ] Add some field on template to help distinguish between templates & sub-templates
- [ ] Add some fields on template to indicate if it was downloaded & some machine id + time