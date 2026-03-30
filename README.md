# GraphPAD Prism Converter

Python utility to extract and plot data from GraphPad Prism `.prism` files (Prism 10+ zip-based format).

## Features

- Parses `.prism` archives and extracts XY data tables into pandas DataFrames
- Automatically reads axis labels and graph titles from the embedded graph metadata
- Plots mean +/- SEM across replicates with configurable colormaps
- Saves each plot as a PNG file

## Setup

### Create the conda environment

```bash
conda create -n prism python=3.12 pandas numpy matplotlib scipy jupyter -y
conda activate prism
```

### Clone and run

```bash
git clone <repo-url>
cd GraphPAD_PrismConverter
conda activate prism
jupyter notebook explore_prism.ipynb
```

## Usage

### Jupyter notebook (recommended)

Open `explore_prism.ipynb` and run all cells. The first cell contains configuration you can adjust:

| Variable | Default | Description |
|---|---|---|
| `PRISM_FILE` | `"Prism_Data.prism"` | Path to your `.prism` file |
| `DOSE_CMAP` | `"plasma"` | Colormap for dose curves (`"viridis"`, `"inferno"`, `"turbo"`, etc.) |
| `COLOR_BUFFER` | `"grey"` | Color for the buffer control |
| `COLOR_FSK` | `"red"` | Color for the 10uM Fsk reference |
| `X_MIN` | `0` | X-axis start (minutes) |
| `X_MAX` | `30` | X-axis end (minutes) |

Plots are saved as PNG files in the working directory, named after the graph title (e.g. `CAMYEN_GLP-1R.png`).

### Python API

```python
from prism_parser import parse_prism

sheets = parse_prism("Prism_Data.prism")

for title, sheet in sheets.items():
    print(sheet.graph_title)  # e.g. "CAMYEN"
    print(sheet.xlabel)       # e.g. "time (min)"
    print(sheet.ylabel)       # e.g. "BRET"
    print(sheet.df.head())    # pandas DataFrame with X + MultiIndex Y columns
```

Each `PrismSheet` object contains:

- `title` -- data sheet name
- `df` -- DataFrame with an `"X"` column and Y columns as a MultiIndex of `(dataset, replicate)`
- `xlabel`, `ylabel` -- axis labels extracted from the Prism graph binary
- `graph_title` -- full graph title (e.g. includes receptor name)

## Project structure

```
prism_parser.py          # Core parser module
explore_prism.ipynb      # Interactive notebook for plotting
Prism_Data.prism         # Example data file
```

## Requirements

- Python >= 3.10
- pandas
- numpy
- matplotlib
- scipy
- jupyter (for the notebook)

## Acknowledgements

Notebook structure, plot types, and export logic developed with the assistance of
[GitHub Copilot](https://github.com/features/copilot) (Claude Sonnet 4.6).
