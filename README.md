# Sitemap Comparison Tool

## Overview
The Sitemap Comparison Tool is a Python script designed to compare the URL path structures between two websites by analyzing their sitemaps. It generates a detailed Excel report highlighting the differences and similarities between the two sitemaps.

## Features
- Recursively resolves `<sitemapindex>` to child sitemaps.
- Handles `.xml` and `.xml.gz` sitemap formats.
- Extracts all `<loc>` URLs and converts them to normalized pathnames.
- Excludes media pathnames (e.g., `.jpg`, `.png`, `.mp4`, etc.) from the report.
- Compares sets of URLs and generates an Excel report with detailed sheets.

## Requirements
- Python 3.6+
- Required Python packages:
  - `requests`
  - `pandas`
  - `xlsxwriter`

Install the required packages using pip:
```bash
pip install requests pandas xlsxwriter
```

## Usage
Run the script with the following command:
```bash
python compare_sitemaps.py <sitemap_a_url> <sitemap_b_url> -o <output_file>
```

### Arguments
- `sitemap_a_url`: URL of the sitemap for the old site.
- `sitemap_b_url`: URL of the sitemap for the new site.
- `-o, --out`: (Optional) Path to the output Excel file. Default is `sitemap_comparison.xlsx`.
- `--label-a`: (Optional) Label for the old site in the report. Default is `OLD`.
- `--label-b`: (Optional) Label for the new site in the report. Default is `NEW`.
- `--keep-trailing-slash`: (Optional) Keep trailing slashes during normalization.
- `--respect-case`: (Optional) Do not lowercase paths during normalization.
- `--include-query`: (Optional) Include query strings in the comparison key.

### Example
```bash
python compare_sitemaps.py https://old.com/sitemap.xml https://new.com/sitemap.xml -o comparison_report.xlsx
```

## Output
The script generates an Excel file with the following sheets:
1. **Overview**: Summary of the comparison metrics.
2. **Matches**: URLs present in both sitemaps.
3. **Only_in_A**: URLs present only in the old site's sitemap.
4. **Only_in_B**: URLs present only in the new site's sitemap.
5. **All**: Combined list of all URLs with their status.

## Notes
- The script automatically excludes media URLs (e.g., `.jpg`, `.png`, `.mp4`) from the comparison.
- Ensure that the provided sitemap URLs are accessible and valid.

## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing
Contributions are welcome! Feel free to open issues or submit pull requests.

## Author
Developed by [Shakil Ilham](https://githup.com/silham).