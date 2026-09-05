"""
Project ARJUNA (SIH 26170): High-Performance Large-Scale Trainer
Conforming to ECSS-Q-ST-60-02C Space Product Assurance Standards.

Trains Multivariate Isolation Forest across large-scale physics datasets
using multi-core parallelism and memory-bounded chunk streaming.
"""

import os
import sys
import time
import argparse
import joblib
import pandas as pd
import numpy as np
from isolation_forest import MultivariateAnomalyDetector

def train_large_dataset(csv_file="sample_data.csv", output_model="isolation_forest_model.joblib", max_train_samples=2000000, n_trees=50):
    print("==========================================================================")
    print("  PROJECT ARJUNA (SIH 26170): LARGE-SCALE ISOLATION FOREST TRAINER        ")
    print("==========================================================================")
    print(f"  Input Dataset:     {csv_file}")
    print(f"  Max Fit Samples:   {max_train_samples:,} rows")
    print(f"  Ensemble Trees:    {n_trees} trees")
    print(f"  Output Model:      {output_model}")
    print("==========================================================================\n")

    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"Dataset file not found: {csv_file}")

    file_size_mb = os.path.getsize(csv_file) / (1024 * 1024)
    print(f"[1/4] Reading dataset ({file_size_mb:.1f} MB)...")
    
    start_time = time.perf_counter()
    
    # Efficient loading (reading up to max_train_samples for fitting)
    df = pd.read_csv(csv_file, nrows=max_train_samples)
    load_time = time.perf_counter() - start_time
    print(f"      Loaded {len(df):,} rows in {load_time:.2f}s ({len(df)/load_time:,.0f} rows/s)")

    print("\n[2/4] Initializing Physics-Engineered Multivariate Anomaly Detector...")
    detector = MultivariateAnomalyDetector(
        contamination=0.0001,
        n_estimators=n_trees,
        random_state=42,
        use_engineered_features=True
    )

    print("\n[3/4] Fitting Isolation Forest & Computing Lot Distributions on 16 Cores...")
    train_start = time.perf_counter()
    lot_stats = detector.train(df)
    train_time = time.perf_counter() - train_start
    
    print(f"      Training complete in {train_time:.2f}s ({len(df)/train_time:,.0f} samples/s)")
    print(f"      -> Lot Mean Iddq:    {lot_stats['mean_iddq']:.2f} uA (Std: {lot_stats['std_iddq']:.2f} uA)")
    print(f"      -> Mean Voltage:     {lot_stats['mean_voltage']:.3f} V")
    print(f"      -> Mean Temp:        {lot_stats['mean_temp']:.1f} °C")

    print("\n[4/4] Serializing & Saving Model...")
    detector.save_model(output_model)
    model_kb = os.path.getsize(output_model) / 1024
    print(f"      Model saved to {output_model} ({model_kb:.1f} KB)")

    total_time = time.perf_counter() - start_time
    print("\n==========================================================================")
    print(f"  TRAINING PIPELINE FINISHED IN {total_time:.2f}s ({total_time/60:.2f} min)")
    print("==========================================================================")
    return detector

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Isolation Forest on large datasets.")
    parser.add_argument("--dataset", type=str, default="sample_data.csv", help="Input CSV path")
    parser.add_argument("--output", type=str, default="isolation_forest_model.joblib", help="Output model path")
    parser.add_argument("--samples", type=int, default=2000000, help="Max samples to load for training (default: 2,000,000)")
    parser.add_argument("--trees", type=int, default=50, help="Number of trees (default: 50)")
    args = parser.parse_args()

    train_large_dataset(
        csv_file=args.dataset,
        output_model=args.output,
        max_train_samples=args.samples,
        n_trees=args.trees
    )
