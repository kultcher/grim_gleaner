# Legacy/orphaned affix normalization references

These localized affix definitions remain in the extracted database, but the
current base-game and expansion item graph has no incoming reference to any of
their DBR records. Their raw fields are retained here and excluded from current
affix normalization. Re-run the reachability audit when importing a new game
database before assuming they are still orphaned.

| Affix | Localization tag | Retained raw fields |
|---|---|---|
| Enlightening | `tagPrefixAA002` | `characterIncreasedExperience` |
| Invigorating | `tagPrefixAA020` | `characterConstitutionModifier` |
| Rugged | `tagPrefixAD022` | `defensiveProtection` |
| of Coagulation | `tagSuffixA023` | `defensiveBleedingDuration` |
| of Detoxification | `tagSuffixA022` | `defensivePoisonDuration` |
| of the Arctic | `tagSuffixA055` | `offensiveFreezeChance`, `offensiveFreezeMin` |
| of the Swamp | `tagSuffixA057` | `offensiveSlowDefensiveReductionChance`, `offensiveSlowDefensiveReductionDurationMin`, `offensiveSlowDefensiveReductionMin` |
| of the Wastes | `tagSuffixA056` | `offensiveTotalResistanceReductionAbsoluteChance` |
| of the Wraith | `tagSuffixA059` | `offensiveSlowManaLeachChance`, `offensiveSlowManaLeachDurationMin`, `offensiveSlowManaLeachMin` |

For comparison, `Soldier's` (`tagPrefixAA011`) is not in this zero-reference
group: its affix records are referenced by intermediate prefix tables, but those
tables are themselves unreachable from the retained gear loot-table roots.
