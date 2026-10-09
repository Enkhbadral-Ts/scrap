#!/usr/bin/env bash
/opt/homebrew/bin/python3.11 scrape_year.py --year 2021
/opt/homebrew/bin/python3.11 scrape_year.py --year 2022
/opt/homebrew/bin/python3.11 scrape_year.py --year 2023 --pages 2000
/opt/homebrew/bin/python3.11 scrape_year.py --year 2024 --pages 2000
/opt/homebrew/bin/python3.11 scrape_year.py --year 2025 --pages 2000
echo "All years completely scraped!"
