# EIA Grid Explorer

An interactive scrollytelling visualization exploring how America's electricity grid works — from historic generation mix trends (2019–2025) to hour-by-hour grid operations across 13 regions.

Built with EIA Form 930 Hourly Electric Grid Monitor data.

## Features

- **13 NEMS grid regions** with clickable tile map selector
- **Historic Grid Mix (2019–2025)**: Interactive donut charts, demand wave, coal waffle, renewables spiral, seasonal radial, and then-vs-now comparison — all with animated year sliders
- **Hourly Grid Analysis (2024)**: 8,760-dot emission intensity chart with sparkle/breathe effects, baseload area chart, stacked dispatch, wind/solar heatmaps, annual-vs-hourly comparison, clean/dirty hour breakdown, and Sankey energy flow diagram
- Scroll-driven storytelling with IntersectionObserver
- Responsive design (desktop, tablet, mobile)
- Single-file HTML deployment (~5.7 MB, fully self-contained)

## Usage

Open `index.html` in any modern browser. No server or build step required for viewing.

## Rebuilding

To regenerate `index.html` from the source projects:

```bash
python build_explorer.py
```

This requires the two source HTML files in sibling directories:
- `../EIA Grid Story/grid-story.html`
- `../3D Grid Viz/grid_story.html`

## Data

All data is embedded inline from [EIA Form 930](https://www.eia.gov/electricity/gridmonitor/) — the Hourly Electric Grid Monitor covering 2019–2025 annual trends and 2024 hourly generation.

## License

MIT
