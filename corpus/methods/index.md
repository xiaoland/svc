# Working Methods

Working Methods are small, reusable ways to improve a local return. They are Agent-facing guidance, not Task types, phases, roles, or runtime states. Use their reasoning directly, compose them recursively, and stop consulting them when they no longer help; the surrounding Task still owns every unmet obligation.

| Method                                    | Use when                                                                      | Characteristic return                                                         |
| ----------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| [Explore](explore/index.md)               | key information or a fitting path is non-obvious                              | supported key information, or an honest bounded-incomplete information return |
| [Design](design/index.md)                 | intended behavior or realization is materially underdetermined or conflicting | one coherent proposed solution at the currently useful resolution             |
| [Implementation](implementation/index.md) | one bounded intended change must become real                                  | realized change plus local feedback and material residual                     |

Choose by the missing return, not by a fixed sequence. Design may Explore; Implementation may reveal a Design mismatch; Verification may require a small Implementation or Explore move. Obvious lookup, mechanical transformation, and trivial local edits should remain direct actions rather than method ceremony.

Every method may return bounded-incomplete when no feasible, authorized, and proportionate continuation exists. That return preserves supported work, states the unmet condition and consequence, and identifies the best viable continuation without claiming success or acceptance.
