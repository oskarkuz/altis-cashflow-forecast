# Altis Groep — Financing Covenant Terms (extract)

_Facility agreement between Altis Groep B.V. and ING Bank N.V., as agent._

## 1. Liquidity covenant (tested WEEKLY — primary 13-week control)
The Group shall maintain **Available Liquidity of not less than EUR 500,000**
("the Liquidity Floor") at the end of each calendar week.

- **Available Liquidity** = Group cash and cash equivalents
  + undrawn committed Revolving Credit Facility (RCF).
- **Committed RCF** = EUR 0 undrawn for the purposes of the 13-week test
  (facility is currently fully utilised; the weekly test is on cash only).
- **Headroom** = Available Liquidity − Liquidity Floor.

### Warning bands (for the dashboard indicator)
| Band  | Condition                                   |
|-------|---------------------------------------------|
| GREEN | Headroom ≥ EUR 250,000                      |
| AMBER | 0 ≤ Headroom < EUR 250,000  (within EUR 250k of the floor) |
| RED   | Headroom < 0  (Liquidity Floor BREACHED)    |

## 2. Leverage covenant (tested QUARTERLY — informational at week 13)
**Net Debt / LTM EBITDA ≤ 3.00x**, tested on the last day of each quarter.

- **Net Debt** = total interest-bearing debt − cash. Total debt = EUR 9,800,000.
- **LTM EBITDA** = EUR 3,600,000.
- Covenant headroom at quarter end is reported alongside the liquidity test.

## Notes
- The weekly liquidity test is the binding constraint inside a 13-week horizon.
- Parameters above (floor, warning bands, debt, EBITDA) are read by the model
  from this document's values and are adjustable in config.py.
