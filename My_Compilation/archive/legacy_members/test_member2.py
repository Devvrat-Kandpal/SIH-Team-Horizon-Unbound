import os
import sqlite3
import pandas as pd
import pytest
from simulator import ComponentSimulator, get_live_telemetry, generate_dataset, export_to_sqlite

def test_component_baseline():
    sim = ComponentSimulator(criticality_level=1)
    temp, volt, curr = sim.step(dt=1.0, mode='normal')
    assert 120.0 <= temp <= 130.0
    assert 4.85 <= volt <= 5.10
    assert 1.10 <= curr <= 1.40


def test_electrical_short_behavior():
    sim = ComponentSimulator()
    temp, volt, curr = sim.step(dt=1.0, mode='short')
    assert volt < 1.0
    assert curr > 7.0

def test_live_telemetry_frame():
    frame = get_live_telemetry(mode='normal', seconds_elapsed=10)
    assert 'timestamp' in frame
    assert 'temperature' in frame
    assert 'voltage' in frame
    assert 'current' in frame
    assert 'iddq' in frame
    assert 'prop_delay' in frame
    assert frame['criticality_level'] in [1, 2, 3]

def test_dataset_generation_and_sqlite_export(tmp_path):
    csv_file = str(tmp_path / 'test_sample.csv')
    db_file = str(tmp_path / 'test_burn_in.db')
    
    generate_dataset(filename=csv_file, n_normal=50, n_drift=20, n_short=10, criticality_level=2, seed=42)
    assert os.path.exists(csv_file)
    
    df = pd.read_csv(csv_file)
    assert len(df) == 84
    assert set(df['label'].unique()) == {'normal', 'drift_anomaly', 'short_anomaly', '0h_record', '24h_record', '96h_record', '168h_record'}
    assert 'iddq' in df.columns
    assert 'prop_delay' in df.columns
    
    export_to_sqlite(csv_filename=csv_file, db_filename=db_file, table_name='telemetry')
    assert os.path.exists(db_file)
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM telemetry')
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 84
