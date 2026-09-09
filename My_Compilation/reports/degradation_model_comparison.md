# Degradation Model Comparison — Linear (A) vs Accumulated-Arrhenius (B)

Phase 3.3 bounded experiment (measure-only). Model switch applied
in-memory and restored; the shipped default (`linear`) is unchanged.

| Metric | A: linear (DEFAULT) | B: accumulated_arrhenius (candidate) |
|---|---|---|
| Final degradation state | 1.0 | 1.4805 |
| Destroyed by 168 h | False | False |
| T @ 24 h [C] | 126.5 | 126.32 |
| Iddq @ 24 h [uA] | 21.63 | 21.57 |
| Rth_eff @ 24 h [C/W] | 17.467 | 17.4786 |
| T @ 48 h [C] | 129.57 | 130.21 |
| Iddq @ 48 h [uA] | 34.77 | 35.97 |
| Rth_eff @ 48 h [C/W] | 18.267 | 18.3445 |
| T @ 96 h [C] | 138.25 | 139.57 |
| Iddq @ 96 h [uA] | 73.86 | 75.86 |
| Rth_eff @ 96 h [C/W] | 19.8671 | 20.3764 |
| T @ 168 h [C] | 151.62 | 159.87 |
| Iddq @ 168 h [uA] | 150.0 | 150.0 |
| Rth_eff @ 168 h [C/W] | 22.2671 | 24.6747 |
| CUSUM first alarm [h] | 17 | 17 |
| Module B 168h forecast [uA] | 144.029 | 152.723 |
| Module B error vs true endpoint [uA] | -5.97 | 2.72 |
| Module B hours-to-violation | 61.1 | 59.1 |
| Module B R^2 | 0.9785 | 0.9731 |

## Interpretation

- NOTE: Model A's 'final degradation state' shows 1.0 because the
  linear path computes r_effective analytically (1 + 0.002h) and never
  touches the D state variable; its effective D(168h) = 1.336 by design.
- Model B is temperature-activated (positive feedback): as junction T
  rises, D accelerates, so its trajectory is expected to exceed the
  linear surrogate's. Any divergence quantifies the calibration risk
  documented in SL-3/SL-4 of docs/SCIENTIFIC_LIMITATIONS.md.
- Detection/forecast differences measure downstream sensitivity to the
  degradation law — evidence for the judge question 'why linear?'.
- This experiment does NOT validate either model physically
  (SIMULATED / ASSUMED classification; see SCIENTIFIC_LIMITATIONS.md).
