# Demo 01 - Basic readiness assessment

This demo assesses a notional unit ("2nd Battalion, 7th Cavalry") whose
personnel and training are strong but whose equipment is degraded.

## Input

`unit.yaml` describes four measured areas:

- **personnel**: 540 assigned of 600 required (90% -> C-1)
- **equipment_onhand**: 42 on-hand of 60 authorized (70% -> C-3)
- **equipment_serviceable**: 30 serviceable of 42 on-hand (~71% -> C-3)
- **training**: 11 of 12 mission-essential tasks trained (~92% -> C-1)

## Run it

```sh
python -m readiness assess demos/01-basic/unit.yaml
python -m readiness assess demos/01-basic/unit.yaml --format json
```

## Expected result

The SORTS rollup is the **worst** measured area, so the overall rating is
**C-3 (marginally ready)**, limited by equipment. The tool flags the
equipment on-hand and serviceability gaps.

Because the default `--fail-under` is `3`, an overall of C-3 is *not* worse
than the threshold, so the command exits `0`. Tighten readiness gating with
`--fail-under 2` to make this same unit fail (exit `1`).
