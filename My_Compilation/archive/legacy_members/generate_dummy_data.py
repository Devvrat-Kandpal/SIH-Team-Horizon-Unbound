import csv
import random

def generate_healthy_data(filename="sample_data.csv", rows=10000):
    """
    Generates baseline parametric telemetry for space-grade ASIC/FPGA burn-in screening
    conforming to ISRO and ECSS-Q-ST-60-02C standards.
    
    Parameters:
    - voltage (V): Nominal 5.0V +/- 0.04V
    - current (A): Nominal 1.20A +/- 0.02A
    - temperature (°C): Nominal 125.0°C +/- 0.5°C (High-rel space burn-in temperature)
    - iddq (uA): Standby current, Lot Mean 10.0 uA +/- 1.5 uA (Datasheet Max: 50 uA)
    - prop_delay (ns): Propagation delay, Nominal 4.5 ns +/- 0.15 ns
    """
    print(f"Generating {rows} rows of ISRO standard baseline telemetry to {filename}...")
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "voltage", "current", "temperature", "iddq", "prop_delay"])
        
        for i in range(rows):
            voltage = 5.0 + random.uniform(-0.04, 0.04)
            current = 1.20 + random.uniform(-0.02, 0.02)
            temperature = 125.0 + random.uniform(-0.5, 0.5)
            iddq = 10.0 + random.gauss(0, 1.2)  # Lot average ~10 uA
            iddq = max(6.0, min(16.0, iddq))    # Normal distribution bounds for healthy lot
            prop_delay = 4.5 + random.uniform(-0.15, 0.15)
            
            writer.writerow([
                i, 
                round(voltage, 4), 
                round(current, 4), 
                round(temperature, 2), 
                round(iddq, 2), 
                round(prop_delay, 3)
            ])
            
    print("Generation complete.")

if __name__ == "__main__":
    generate_healthy_data()
