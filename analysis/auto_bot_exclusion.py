import pandas as pd
import numpy as np

df = pd.read_parquet('../data/parquet/2019-Oct.parquet')

# Exclude confirmed bot
BOT_USER = 512475445
df = df[df['user_id'] != BOT_USER].copy()

auto = df[df.category_code.str.startswith('auto', na=False)].copy()

sessions = auto.groupby('user_session').agg(
    user_id=('user_id', 'first'),
    purchased=('event_type', lambda x: (x == 'purchase').any()),
    events=('event_type', 'count')
).reset_index()

spu = auto.groupby('user_id')['user_session'].nunique()
sessions['user_session_count'] = sessions['user_id'].map(spu)

n = len(sessions)
conv = sessions['purchased'].sum()
rate = conv / n
de_users = sessions['user_session_count'].var() / sessions['user_session_count'].mean()

print(f'Sessions after bot removal: {n:,}')
print(f'Conversions:                {conv:,}')
print(f'Conversion rate:            {rate:.4f}')
print(f'Max sessions per user:      {sessions["user_session_count"].max()}')
print(f'Mean sessions per user:     {sessions["user_session_count"].mean():.2f}')
print()
print('Sessions per user distribution:')
print(sessions['user_session_count'].describe(percentiles=[.5,.75,.9,.95,.99]))
