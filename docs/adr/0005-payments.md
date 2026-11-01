# ADR-0005: Payments: Paddle as Merchant of Record by default, behind a provider port

Status: deferred to Phase 7 (proposal unchanged; needs business confirmation) · Date: 2026-10-31. 2026-11-01 note: webhook deduplication uses the `app.webhook_events` unique constraint in Supabase. The design no longer has Redis.

## Context
- Low-priced global subscriptions: Personal 2.99 USD and Pro 5.99 USD per month. Prices are configurable server-side.
- Sold by a Malaysia-based business to consumers worldwide. Selling digital services cross-border creates indirect-tax obligations in many jurisdictions (EU VAT, UK VAT, Australian GST and others, plus Malaysian SST). Registering and filing everywhere is a large burden for a small team.
- Stripe does operate in Malaysia. Whether the specific legal entity qualifies (business type, payout bank, risk review) is unconfirmed.

## Options

| | Stripe Billing (+ Stripe Tax) | Paddle (MoR) | Lemon Squeezy (MoR) | FastSpring (MoR) |
|---|---|---|---|---|
| Who is the seller / tax liable | **We are** (Stripe Tax only calculates) | Paddle | Lemon Squeezy | FastSpring |
| Global tax registration and filing | ours | handled | handled | handled |
| Chargebacks / fraud | ours | handled | handled | handled |
| Indicative fees | lowest per transaction, plus tax and filing costs | higher (% + fixed) | higher (% + fixed) | negotiated |
| Malaysian seller | supported country; entity to be verified | supports most countries; to be verified | to be verified; roadmap tied to Stripe ownership | sales-led onboarding |
| Webhook verification | signed (HMAC) | signed (HMAC) | signed (HMAC) | signed |

## Decision
- **Default: Paddle Billing as Merchant of Record.** For a small team, offloading global tax liability, invoicing and chargebacks outweighs the higher fees.
- **Fallback: Stripe Billing + Stripe Tax**, if Paddle rejects the business or once revenue justifies handling tax in-house.
- All provider specifics sit behind a `BillingProvider` port (`backend/app/services/billing/`, Phase 7) with `create_checkout()`, `create_portal_link()`, `parse_and_verify_webhook()` and `map_event() -> SubscriptionEvent`. The domain model (`plans`, `subscriptions`, `usage`) is provider-agnostic. Switching providers is an adapter plus a data migration, not a redesign.
- **Webhooks**:
  - Raw body signature verification with a timestamp tolerance check.
  - The provider event id goes into `app.webhook_events` (unique). Duplicates are no-ops.
  - Processing is transactional.
  - Out-of-order events are resolved by the provider's `occurred_at` and subscription version.
  - Return 2xx only after commit.
  - The webhook route is exempt from CORS and session auth, but rate-limited and size-capped.
- Entitlements are always derived server-side from `app.subscriptions`. Client-provided plan or price data is never trusted.
- No card data ever touches our systems (hosted checkout or overlay).

## Consequences
- (+) Tax compliance can be launched without registrations.
- (−) At 2.99 USD the fixed per-transaction fee is a large share of revenue. Annual billing options reduce this (business decision, Q2).
- (−) Paddle's checkout overlay script must be allowed in the CSP on the pricing/checkout pages only.
