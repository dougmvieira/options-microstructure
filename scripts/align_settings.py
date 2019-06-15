import pandas as pd


STARTTIME = pd.to_datetime('2016-01-04 09:00:00')  # skipping first hour
ENDTIME = pd.to_datetime('2016-01-04 16:00:00')  # skipping last half hour
TIMESTEP = pd.to_timedelta('1s')
