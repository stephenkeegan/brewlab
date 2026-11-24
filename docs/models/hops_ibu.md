# Model: Predicted IBU

**Module:** `brewlab.core.hops.predicted_ibu`
**Classification:** empirical (utilization efficiency)
**Test:** `tests/test_hops.py`

## Equation

    IBU = iso_alpha_concentration (mg/L) * utilization_efficiency

1 mg/L iso-alpha acid is approximately 1 IBU.

## Parameters

| Parameter | Unit | Default | Notes |
|---|---|---|---|
| iso_alpha_concentration | mg/L | input | from iso_alpha_concentration model |
| utilization_efficiency | dimensionless | 0.30 | fraction; calibration target |

## Assumptions

- IBU scales linearly with iso-alpha concentration.
- Utilization efficiency lumps trub/foam losses, extraction efficiency, and
  system geometry into one factor.

## Limitations

- **Utilization efficiency is empirical and system-specific.** The default
  (0.30) is a placeholder; typical homebrew/pilot values are ~0.2-0.4.
- Does not distinguish iso-alpha acid isomers (cis/trans) with different
  bitterness perception.
- Does not model bitterness perception thresholds or hop variety differences
  beyond alpha-acid content.

## Validation

- `test_predicted_ibu_scales_with_utilization`: IBU proportional to
  utilization efficiency.
- `test_predicted_ibu_units`: result carries IBU units.
