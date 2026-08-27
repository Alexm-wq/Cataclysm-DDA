# Crafting groups

These files define the section-title taxonomy for the modern crafting browser.

Each normal base-game `recipe` belongs to exactly one `crafting_group`. Existing
visible `nested_category` definitions are used as the curated source wherever
possible and recorded in `source_nested_category`. Recipes not covered by an
existing curated nest are still assigned explicitly and marked `fallback: true`;
those groups are the review queue for later taxonomy refinement.

The legacy nested-category data remains untouched for compatibility. The modern
browser can migrate to these flat group headings independently.
