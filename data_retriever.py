#!/usr/bin/python3

from datetime import datetime, timedelta
from data import LeagueStats, TeamStats
import calendar
import os

teams = {
    "Oakland Athletics": "OAK",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "Seattle Mariners": "SEA",
    "San Francisco Giants": "SF",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Minnesota Twins": "MIN",
    "Philadelphia Phillies": "PHI",
    "Atlanta Braves": "ATL",
    "Chicago White Sox": "CWS",
    "Miami Marlins": "MIA",
    "New York Yankees": "NYY",
    "Milwaukee Brewers": "MIL",
    "Los Angeles Angels": "LAA",
    "Arizona Diamondbacks": "AZ",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Dodgers": "LAD",
    "Washington Nationals": "WSH",
    "New York Mets": "NYM",
}


def split_date_range(start_date, end_date):
    # Convert start_date and end_date strings to datetime objects
    start_date = datetime.strptime(start_date, "%m/%d/%Y")
    end_date = datetime.strptime(end_date, "%m/%d/%Y")

    # Split date range into intervals
    intervals = []
    current_date = start_date
    while current_date <= end_date:
        month_end = current_date.replace(
            day=calendar.monthrange(current_date.year, current_date.month)[1]
        )
        if current_date.day <= 15:
            interval_end = current_date.replace(day=15)
        else:
            interval_end = month_end

        intervals.append((current_date, interval_end))
        current_date = interval_end + timedelta(days=1)

    return intervals


def generate_file_path(year, month, index):
    return f"data/seasons/{year}/{month}_{index}.xlsx"


def retrieve_data(start_date, end_date, team_name="mlb"):
    intervals = split_date_range(start_date, end_date)
    if team_name == "mlb":
        data_object = LeagueStats()
    else:
        data_object = TeamStats(team_name)

    for index, (interval_start, interval_end) in enumerate(intervals):
        file_path = generate_file_path(
            interval_start.year, interval_start.strftime("%B").lower(), index + 1
        )

        if os.path.isfile(file_path):
            print(
                f"Skipping data retrieval for {interval_start.strftime('%B %Y')}"
                f"(already exists)"
            )
            continue

        success = False
        while not success:
            try:
                data_object.get_data(
                    start_date=interval_start.strftime("%m/%d/%Y"),
                    end_date=interval_end.strftime("%m/%d/%Y"),
                    file_path=file_path,
                )
                success = True
            except Exception as e:
                print(
                    f"Exception occurred during data retrieval for "
                    f"{interval_start.strftime('%B %Y')}:",
                    e,
                )
                print("Retrying...")

        print(f"\nData retrieved for {interval_start.strftime('%B %Y')}\n")

    print("Data retrieval complete.")


def main():
    start_date = input("Enter start date (MM/DD/YYYY): ")
    end_date = input("Enter end date (MM/DD/YYYY): ")
    retrieve_data(start_date, end_date)


if __name__ == "__main__":
    main()
