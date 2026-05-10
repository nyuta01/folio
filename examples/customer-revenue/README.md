# customer-revenue — sibling of customers

This sheet exists to demonstrate the **1:1 sidecar** pattern that
[`../customers`](../customers) reads through the `cross_sheet`
derivation kind. Each row's primary key (`id`) matches the
corresponding row in `customers/`.

| Field | Editor | Notes |
|---|---|---|
| `id` | (PK) | Must equal customers.id. |
| `revenue_usd` | `agent:finance` | Latest fiscal-year revenue. |
| `contract_value_usd` | `agent:finance` | Active contract value. |
| `as_of` | `agent:finance` | Date the revenue figure was confirmed. |

## Try it

```bash
uv run folio validate examples/customer-revenue
uv run folio query examples/customer-revenue \
  "SELECT id, revenue_usd FROM records ORDER BY revenue_usd DESC"
```

## Why a separate sheet?

`x-editable-by` operates per field, not per actor-class. Splitting
the financial figures into a sidecar gives the finance agent a
sheet of its own (no risk of overwriting customer-master fields
that operations owns) while still letting customers/ pull the
authoritative revenue figure on demand.
