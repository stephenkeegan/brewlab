# Model: Alkalinity (as CaCO3)

**Module:** `brewlab.core.equilibrium.alkalinity_as_caco3_from_bicarbonate`
**Classification:** mechanistic (ASBC equivalence conversion)
**Test:** `tests/test_equilibrium.py`

## Equation

    Alkalinity (mg/L as CaCO3) = [HCO3-] (mg/L) * (EQW_CaCO3 / MW_HCO3)

because 1 mol HCO3- neutralizes 1 equivalent of acid.

- EQW_CaCO3 = 50.044 g/eq (equivalent weight of CaCO3)
- MW_HCO3 = 61.0168 g/mol

So 61.0168 mg/L HCO3- (= 1 mmol/L) = 50.044 mg/L as CaCO3.

## Parameters

| Parameter | Unit | Value |
|---|---|---|
| [HCO3-] | mg/L | input |
| EQW_CaCO3 | g/eq | 50.044 |
| MW_HCO3 | g/mol | 61.0168 |

## Assumptions

- Alkalinity is dominated by bicarbonate (no significant carbonate,
  hydroxide, or phosphate contribution at typical mash pH).
- 1 mol HCO3- = 1 eq of acid-neutralizing capacity.

## Limitations

- Ignores other alkalinity contributors (CO3--, OH-, H2PO4-, etc.).
- Temperature-independent (no temperature correction to molar masses).

## Literature source

- ASBC water-analysis methods (alkalinity expressed as CaCO3).

## Validation

- `test_alkalinity_conversion_definitional`: 61.0168 mg/L HCO3- -> 50.044 mg/L as CaCO3.
- `test_alkalinity_conversion_gram_per_liter`: unit-conversion path.
