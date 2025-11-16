# Landing Page Deployment

This directory contains the Quality Gate++ marketing website.

## Quick Deploy

### Option 1: Vercel (Recommended)
```bash
npm i -g vercel
vercel --prod
# Point your domain: quality-gate.dev → vercel app
```

### Option 2: Netlify
```bash
npm i -g netlify-cli
netlify deploy --prod --dir=landing
```

### Option 3: GitHub Pages
```yaml
# .github/workflows/deploy-landing.yml
name: Deploy Landing Page
on:
  push:
    branches: [main]
    paths:
      - 'landing/**'
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./landing
```

### Option 4: Static Hosting (AWS S3, Cloudflare Pages, etc.)
```bash
# AWS S3 example
aws s3 sync landing/ s3://quality-gate-landing --acl public-read
aws cloudfront create-invalidation --distribution-id YOUR_ID --paths "/*"
```

## Setup Waitlist Form

1. Create a [Formspree](https://formspree.io/) account (free tier: 50 submissions/month)
2. Get your form endpoint (e.g., `https://formspree.io/f/xyzabc123`)
3. Replace `YOUR_FORM_ID` in `index.html` line 311:
   ```html
   <form action="https://formspree.io/f/YOUR_FORM_ID" method="POST">
   ```

**Alternative form providers:**
- **Tally.so** (unlimited free forms)
- **Typeform** (branded, better UX)
- **Google Forms** (embed iframe)
- **Custom API**: POST to your dashboard `/waitlist` endpoint

## Customization

### Update Copy
Edit `index.html` sections:
- **Hero** (line 78): Main headline and CTA
- **Stats** (line 92): Key metrics
- **Features** (line 110): Product features
- **Pricing** (line 178): Tier details and pricing
- **Comparison** (line 229): Competitor table

### Update Links
- Line 85: GitHub repo URL
- Line 311: Formspree endpoint
- Line 334: Footer links (docs, contact email)

### Branding
- Line 8: Update color scheme (CSS variables `#667eea` purple, `#764ba2` gradient)
- Add logo: Replace `<h1>Stop Shipping Bugs</h1>` with `<img src="logo.svg">`

## Analytics (Optional)

Add before `</head>`:

```html
<!-- Plausible (privacy-friendly, GDPR compliant) -->
<script defer data-domain="quality-gate.dev" src="https://plausible.io/js/script.js"></script>

<!-- OR Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

## SEO Optimization

Already included:
- Meta description (line 7)
- Semantic HTML (headings, sections)
- Mobile responsive (viewport meta, media queries)
- Fast load (no external deps except fonts)

**Next steps:**
1. Add `og:image` for social sharing (Twitter cards, LinkedIn previews)
2. Generate `sitemap.xml` and `robots.txt`
3. Submit to Google Search Console
4. Add structured data (JSON-LD schema for SoftwareApplication)

## Performance

Current score: **~95/100 Lighthouse**
- No external JavaScript (vanilla)
- Inline CSS (no blocking requests)
- Lazy-load images if added

## A/B Testing Ideas

Test these variants:
1. **Hero CTA**: "Join Waitlist" vs "Start Free Trial" vs "See Demo"
2. **Pricing anchor**: Show Enterprise first (high anchor) vs Pro first
3. **Social proof**: Add testimonials section with logo wall (GitHub, companies using it)
4. **Video**: Record 60-second demo, embed above features

---

**Launch checklist:**
- [ ] Update Formspree endpoint
- [ ] Deploy to Vercel/Netlify
- [ ] Point domain DNS
- [ ] Add analytics
- [ ] Test on mobile
- [ ] Submit to Product Hunt, HN Show, Reddit r/SideProject
