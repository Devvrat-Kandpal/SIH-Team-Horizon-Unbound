import os
import matplotlib.pyplot as plt
import pandas as pd

# Automatically load sample_data.csv from the same directory as read.py
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "sample_data.csv")

df = pd.read_csv(csv_path)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Create a figure with 3 subplots for temperature, voltage, and current
fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

# Define color mapping for labels
colors = {
    "normal": "tab:blue",
    "drift_anomaly": "tab:orange",
    "short_anomaly": "tab:red",
    "0h_record": "tab:cyan",
    "24h_record": "tab:purple",
    "96h_record": "tab:olive",
    "168h_record": "tab:brown",
}

# Plot metrics
metrics = [
    ("temperature", "Temperature (°C)", "tab:blue"),
    ("voltage", "Voltage (V)", "tab:green"),
    ("current", "Current (A)", "tab:purple"),
]

for i, (col, ylabel, default_color) in enumerate(metrics):
    ax = axes[i]
    for label, group in df.groupby("label"):
        ax.scatter(
            group["timestamp"],
            group[col],
            label=label,
            color=colors.get(label, default_color),
            s=5,
        )
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--", alpha=0.6)
    if i == 0:
        ax.legend(loc="upper left")

axes[-1].set_xlabel("Timestamp")
plt.suptitle(
    "Hardware Telemetry Simulation: Normal, Drift, and Short Anomalies",
    fontsize=14,
)
plt.tight_layout()
plt.show()