import pandas as pd
import numpy as np

df = pd.read_parquet('../data/parquet/2019-Oct.parquet')
auto = df[df.category_code.str.startswith('auto', na=False)].copy()

sessions = auto.groupby('user_session').agg(
    user_id=('user_id', 'first'),
    purchased=('event_type', lambda x: (x == 'purchase').any()),
    events=('event_type', 'count')
).reset_index()

spu = auto.groupby('user_id')['user_session'].nunique()
sessions['user_session_count'] = sessions['user_id'].map(spu)

for threshold in [None, 500, 100, 50, 20, 10]:
    if threshold is None:
        sub = sessions
        label = 'All sessions (raw)'
    else:
        sub = sessions[sessions['user_session_count'] < threshold]
        label = f'Exclude users >= {threshold} sessions'
    rate = sub['purchased'].sum() / len(sub)
    n = len(sub)
    conv = sub['purchased'].sum()
    print(f'{label:45s}  n={n:>8,}  conversions={conv:>6,}  rate={rate:.4f}')
