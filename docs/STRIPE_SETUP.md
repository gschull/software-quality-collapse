# Stripe Integration Guide

## Setup Checklist

### 1. Create Stripe Account
- Sign up at https://dashboard.stripe.com/register
- Complete business verification
- Add bank account for payouts
- Enable test mode initially

### 2. Create Products

#### Pro Tier
```bash
stripe products create \
  --name="Quality Gate++ Pro" \
  --description="Hosted dashboard with 90-day history" \
  --default-price-data[currency]=usd \
  --default-price-data[unit_amount]=1000 \
  --default-price-data[recurring][interval]=month

# Note the price_id (e.g., price_abc123)
```

#### Team Tier
```bash
stripe products create \
  --name="Quality Gate++ Team" \
  --description="Org-wide policy management + SAML SSO" \
  --default-price-data[currency]=usd \
  --default-price-data[unit_amount]=1500 \
  --default-price-data[recurring][interval]=month
```

#### Enterprise (Custom Pricing)
- Don't create product in Stripe
- Use `stripe invoices create` manually for custom quotes

### 3. Set Up Webhook Endpoint

Add to `dashboard/app.py`:

```python
import stripe
from fastapi import Request, HTTPException

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Handle events
    if event["type"] == "customer.subscription.created":
        handle_subscription_created(event["data"]["object"])
    elif event["type"] == "customer.subscription.deleted":
        handle_subscription_deleted(event["data"]["object"])
    elif event["type"] == "invoice.payment_succeeded":
        handle_payment_succeeded(event["data"]["object"])
    elif event["type"] == "invoice.payment_failed":
        handle_payment_failed(event["data"]["object"])
    
    return {"received": True}

def handle_subscription_created(subscription):
    # Create customer record in DB
    con = get_db()
    con.execute("""
        INSERT INTO customers (stripe_customer_id, stripe_subscription_id, plan, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        subscription["customer"],
        subscription["id"],
        subscription["items"]["data"][0]["price"]["id"],
        subscription["status"],
        datetime.utcnow()
    ))
    con.commit()

def handle_subscription_deleted(subscription):
    # Mark customer as inactive
    con = get_db()
    con.execute("""
        UPDATE customers SET status = 'canceled', canceled_at = ? WHERE stripe_subscription_id = ?
    """, (datetime.utcnow(), subscription["id"]))
    con.commit()

def handle_payment_succeeded(invoice):
    # Log successful payment
    print(f"Payment succeeded: {invoice['id']} for {invoice['customer']}")

def handle_payment_failed(invoice):
    # Send email alert
    print(f"Payment failed: {invoice['id']} for {invoice['customer']}")
```

### 4. Register Webhook in Stripe Dashboard

1. Go to https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. URL: `https://your-dashboard.fly.dev/webhook/stripe`
4. Events to listen for:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Copy webhook signing secret → set as `STRIPE_WEBHOOK_SECRET` env var

### 5. Update Database Schema

Add customers table to `dashboard/schema.sql` (or migration):

```sql
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    plan TEXT NOT NULL, -- 'pro', 'team', 'enterprise'
    status TEXT NOT NULL, -- 'active', 'trialing', 'canceled', 'past_due'
    created_at TEXT NOT NULL,
    canceled_at TEXT,
    metadata TEXT -- JSON for custom fields
);

CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_stripe_customer_id ON customers(stripe_customer_id);
```

### 6. Build Billing Portal

Add `/billing` endpoint:

```python
@app.get("/billing")
async def billing_portal(request: Request, email: str):
    # ELI5: This creates a special link where customers can update their payment info
    con = get_db()
    customer = con.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Create Stripe billing portal session
    session = stripe.billing_portal.Session.create(
        customer=customer["stripe_customer_id"],
        return_url=f"{request.base_url}billing/success"
    )
    
    return RedirectResponse(session.url)
```

### 7. Create Checkout Page

Landing page button → Stripe Checkout:

```html
<!-- landing/index.html, inside waitlist form area -->
<a href="/checkout?plan=pro" class="btn">Start Pro Trial (14 days free)</a>

<script>
async function redirectToCheckout(plan) {
    const response = await fetch(`/checkout?plan=${plan}`);
    const session = await response.json();
    window.location.href = session.url;
}
</script>
```

Backend endpoint:

```python
@app.get("/checkout")
async def create_checkout_session(plan: str, email: str = None):
    # Determine price ID based on plan
    prices = {
        "pro": "price_abc123",  # Replace with actual Stripe price ID
        "team": "price_def456"
    }
    
    if plan not in prices:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price": prices[plan],
            "quantity": 1,
        }],
        mode="subscription",
        success_url=f"{request.base_url}billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{request.base_url}",
        customer_email=email if email else None,
        subscription_data={
            "trial_period_days": 14
        }
    )
    
    return {"url": session.url}
```

### 8. Environment Variables

Update `dashboard/fly.toml` and `.env`:

```toml
[env]
  STRIPE_SECRET_KEY = "sk_live_..."  # DO NOT COMMIT THIS!
  STRIPE_WEBHOOK_SECRET = "whsec_..."
  STRIPE_PUBLISHABLE_KEY = "pk_live_..."  # For frontend if needed
```

Use Fly secrets for production:
```bash
fly secrets set STRIPE_SECRET_KEY=sk_live_...
fly secrets set STRIPE_WEBHOOK_SECRET=whsec_...
```

### 9. Testing

**Test mode:**
```bash
# Use test API keys (sk_test_..., pk_test_...)
# Test cards: https://stripe.com/docs/testing
# 4242 4242 4242 4242 (success)
# 4000 0000 0000 0002 (decline)
```

**Webhook testing:**
```bash
stripe listen --forward-to localhost:8000/webhook/stripe
# Trigger events: stripe trigger customer.subscription.created
```

### 10. Go Live Checklist

- [ ] Switch from test keys to live keys
- [ ] Update webhook endpoint URL to production domain
- [ ] Enable 3D Secure (SCA compliance)
- [ ] Set up fraud detection (Stripe Radar)
- [ ] Add terms of service + privacy policy links to checkout
- [ ] Test full flow: signup → trial → convert → cancel
- [ ] Set up billing alerts (Stripe → Slack/email)

---

## Manual Invoicing (First 10 Customers)

For early customers, skip Stripe Checkout and send invoices manually:

```bash
# Create customer
stripe customers create --email="cto@example.com" --name="Example Corp"

# Create invoice
stripe invoices create \
  --customer=cus_abc123 \
  --collection_method=send_invoice \
  --days_until_due=30

# Add line item
stripe invoice_items create \
  --customer=cus_abc123 \
  --invoice=in_xyz789 \
  --amount=25000 \
  --currency=usd \
  --description="Quality Gate++ Pro (25 devs @ $10/dev/month)"

# Send invoice
stripe invoices send_invoice in_xyz789
```

**Why manual first?**
- Faster to market (no billing UI needed)
- Flexibility for custom deals (discounts, annual prepay)
- Gather feedback before building self-service

---

## Pricing API for Landing Page

Add `/api/pricing` endpoint to query dynamically:

```python
@app.get("/api/pricing")
async def get_pricing():
    return {
        "pro": {
            "price_per_dev": 10,
            "min_seats": 5,
            "features": ["Hosted dashboard", "90-day history", "Email support"]
        },
        "team": {
            "price_per_dev": 15,
            "min_seats": 20,
            "features": ["Org-wide policies", "SAML SSO", "Audit logs"]
        },
        "enterprise": {
            "price_per_dev": 30,
            "min_seats": 200,
            "features": ["On-prem", "Compliance reports", "Dedicated CSM"]
        }
    }
```

Landing page fetches this and renders pricing cards dynamically.

---

## ROI Calculator API

Add `/api/roi` for interactive calculator:

```python
@app.get("/api/roi")
async def calculate_roi(team_size: int = 25, plan: str = "pro"):
    prices = {"pro": 10, "team": 15, "enterprise": 30}
    cost_per_month = team_size * prices[plan]
    
    # Assumptions (based on research)
    hours_saved_per_dev_per_sprint = 2
    sprints_per_year = 24
    hourly_rate = 75
    incidents_prevented = 1  # per year
    incident_cost = 50000
    
    time_savings = team_size * hours_saved_per_dev_per_sprint * sprints_per_year * hourly_rate
    incident_savings = incidents_prevented * incident_cost
    total_value = time_savings + incident_savings
    
    roi_multiple = total_value / (cost_per_month * 12)
    
    return {
        "team_size": team_size,
        "plan": plan,
        "cost_per_month": cost_per_month,
        "cost_per_year": cost_per_month * 12,
        "time_savings_per_year": time_savings,
        "incident_savings_per_year": incident_savings,
        "total_value_per_year": total_value,
        "roi_multiple": round(roi_multiple, 1),
        "payback_period_days": round(365 / roi_multiple, 0)
    }
```

Landing page usage:
```html
<input type="range" id="team-size" min="5" max="500" value="25">
<div id="roi-result"></div>

<script>
document.getElementById('team-size').addEventListener('input', async (e) => {
    const size = e.target.value;
    const res = await fetch(`/api/roi?team_size=${size}&plan=pro`);
    const data = await res.json();
    document.getElementById('roi-result').innerHTML = `
        <strong>$${data.cost_per_month}/month</strong> → 
        <strong>${data.roi_multiple}x ROI</strong> 
        (saves $${data.total_value_per_year.toLocaleString()}/year)
    `;
});
</script>
```

---

## Next Steps

1. **Week 1**: Create Stripe account, set up test products
2. **Week 2**: Add webhook handler, test subscription flow locally
3. **Week 3**: Manual invoice first 5 customers, gather feedback
4. **Week 4**: Build self-service checkout, go live with Stripe

**Resources:**
- [Stripe Billing Docs](https://stripe.com/docs/billing)
- [FastAPI + Stripe Example](https://github.com/stripe-samples/subscription-use-cases)
- [Stripe Checkout Demo](https://stripe.com/docs/payments/checkout)
