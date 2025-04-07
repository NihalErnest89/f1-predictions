import fastf1
import pandas as pd
from collections import defaultdict
from datetime import datetime

fastf1.Cache.enable_cache('f1_cache')  # Enable local caching

# 🏁 Points for race (top 10) and sprint (top 8)
FIA_POINTS_RACE = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
FIA_POINTS_SPRINT = [8, 7, 6, 5, 4, 3, 2, 1]

# ✅ Manual total points using race + sprint results
def get_total_driver_points(year, valid_rounds):
    points = defaultdict(float)

    for rnd in valid_rounds:
        try:
            race = fastf1.get_session(year, rnd, 'R')
            race.load()
            for i, drv in enumerate(race.results.itertuples(), start=1):
                if i <= 10:
                    points[drv.DriverNumber] += FIA_POINTS_RACE[i - 1]
        except:
            continue

        try:
            sprint = fastf1.get_session(year, rnd, 'Sprint')
            sprint.load()
            for i, drv in enumerate(sprint.results.itertuples(), start=1):
                if i <= 8:
                    points[drv.DriverNumber] += FIA_POINTS_SPRINT[i - 1]
        except:
            continue

    return points

def get_avg_finish_pos(year, valid_rounds):
    finishes = defaultdict(list)
    for rnd in valid_rounds:
        try:
            race = fastf1.get_session(year, rnd, 'R')
            race.load()
            for drv in race.results.itertuples():
                finishes[drv.DriverNumber].append(int(drv.Position))
        except:
            print(f"Couldn't get avg from Round {rnd}")
            continue
    return {driver: sum(pos_list)/len(pos_list) if pos_list else 20 for driver, pos_list in finishes.items()}

def get_past_track_performance(circuit_name, year):
    past_years = [y for y in range(year - 3, year) if y >= 2018]
    track_performance = defaultdict(list)

    for y in past_years:
        try:
            schedule = fastf1.get_event_schedule(y)
            circuit_event = schedule[schedule['EventName'].str.contains(circuit_name, case=False, na=False)]
            if circuit_event.empty:
                continue
            rnd = circuit_event.iloc[0]['RoundNumber']
            race = fastf1.get_session(y, int(rnd), 'R')
            race.load()
            for drv in race.results.itertuples():
                track_performance[drv.FullName].append(int(drv.Position))
        except:
            continue

    return {
        driver: sum(pos_list) / len(pos_list) if pos_list else 20
        for driver, pos_list in track_performance.items()
    }

def predict_race(year, circuit_name):
    schedule = fastf1.get_event_schedule(year)

    # Get round number for selected event
    circuit_event = schedule[schedule['EventName'].str.contains(circuit_name, case=False, na=False)]
    if circuit_event.empty:
        print(f"\n❌ No circuit found for '{circuit_name}' in {year}. Check spelling.")
        return

    round_num = circuit_event.iloc[0]['RoundNumber']
    print(f"\n📡 Fetching data for {circuit_name} ({year}, Round {round_num})...")

    # ✅ Get all rounds that occurred before today
    now = datetime.utcnow()
    past_races = schedule[pd.to_datetime(schedule["EventDate"]) < now]
    valid_rounds = past_races["RoundNumber"].astype(int).tolist()

    # Load only up to races that have happened
    points = get_total_driver_points(year, valid_rounds)
    avg_finish = get_avg_finish_pos(year, valid_rounds)
    track_perf = get_past_track_performance(circuit_name, year)

    season_drivers = set()
    name_lookup = {}

    for rnd in valid_rounds:
        try:
            race = fastf1.get_session(year, rnd, 'R')
            race.load()
            for drv in race.results.itertuples():
                driver_num = drv.DriverNumber
                season_drivers.add(driver_num)
                name_lookup[driver_num] = drv.FullName
        except:
            continue

    data = []
    for drv in season_drivers:
        name = name_lookup.get(drv, f"Driver #{drv}")
        pts = points.get(drv, 0)
        avg_pos = avg_finish.get(drv, 20)
        track_pos = track_perf.get(name, 20)
        data.append([name, pts, avg_pos, track_pos])

    df = pd.DataFrame(data, columns=["Driver", "Points", "AvgFinishPos", "TrackAvgPos"])

    # ⚙️ Custom weight configuration
    W_POINTS = 20
    W_AVG_FINISH = 25
    W_TRACK_AVG = 25

    df["CustomScore"] = (
        df["Points"] * W_POINTS +
        (-df["AvgFinishPos"]) * W_AVG_FINISH +
        (-df["TrackAvgPos"]) * W_TRACK_AVG
    )

    df = df.sort_values("CustomScore", ascending=False)
    df.reset_index(drop=True, inplace=True)
    df["PredictedRank"] = df.index + 1

    # ✅ Format numeric columns to 2 decimal places
    float_cols = ["Points", "AvgFinishPos", "TrackAvgPos", "CustomScore"]
    df[float_cols] = df[float_cols].applymap(lambda x: round(x, 2))

    print(f"\n🏁 Predicted Race Rankings for {circuit_name.title()}:")
    print(df[["PredictedRank", "Driver", "Points", "AvgFinishPos", "TrackAvgPos", "CustomScore"]].to_string(index=False))

# -----------------------------
# Main Execution
# -----------------------------
if __name__ == "__main__":
    try:
        year = int(input("Enter the F1 season year (e.g., 2023): "))

        schedule = fastf1.get_event_schedule(year)
        event_names = schedule["EventName"].tolist()

        print("\n📅 Available Events:")
        for i, name in enumerate(event_names, 1):
            print(f"{i:2d}. {name}")

        print()
        track = input("Enter the track or event name from the list above: ")
        predict_race(year, track)

    except Exception as e:
        print(f"\n⚠️ Error: {e}")
