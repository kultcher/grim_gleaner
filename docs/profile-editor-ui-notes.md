# Profile editor UI notes

## Weight control

Each stat uses a four-star, five-state control representing weights 0 through 4.

```text
All Damage     ◀  ★ ★ ★ ☆  ▶
```

- `0`: ☆ ☆ ☆ ☆ — Ignored
- `1`: ★ ☆ ☆ ☆ — Incidental
- `2`: ★ ★ ☆ ☆ — Useful
- `3`: ★ ★ ★ ☆ — Emphasized
- `4`: ★ ★ ★ ★ — Core

The left and right buttons decrement and increment the weight. Stars should also
be directly clickable for faster entry. The control exposes an accessible value
such as `Weight 3 of 4: Emphasized`; filled state must not depend on color alone.
The decrement button is disabled at 0 and the increment button is disabled at 4.

## Package accordions

All package names remain visible in their assigned tab. Optional packages start
collapsed instead of being hidden behind an add-package menu.

- Default packages are always expanded and cannot be collapsed.
- Optional packages with all weights at 0 can be expanded or collapsed.
- Changing any stat in an optional package above 0 expands and pins that package.
- A pinned package cannot be collapsed while it contains a nonzero weight.
- Returning every stat in the package to 0 makes it collapsible again.
- An optional package header shows its nonzero-stat count, for example
  `Fire (3 weighted)`.

Accordion expansion is presentation state, not scoring state. A package does not
need a separate enabled flag: only its stat weights affect relevance. Expanded
package IDs may be saved as a user-interface convenience, independently of the
profile's semantic weights.

## Confirmed placement details

- Generic flat and percentage target resistance reduction appear once in the
  Damage tab's default Base package.
- Damage-type packages expose directional conversion into their selected damage
  type rather than duplicating one generic conversion weight.
- Granted item skills remain in the dedicated Skills tab and are deferred until
  specific skill selection and scoring behavior are designed.
