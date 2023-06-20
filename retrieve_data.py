import statsapi
import pandas as pd

def get_division_standings(league, division):
    standings = pd.DataFrame(statsapi.standings_data(league)[division]['teams'])
    standings = standings[['name', 'div_rank', 'gb', 'w', 'l', 'elim_num', 'wc_rank', 'wc_gb']]
    return standings

print(get_division_standings(104,204))
