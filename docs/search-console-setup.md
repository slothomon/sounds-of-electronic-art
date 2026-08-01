# Google Search Console setup for sofea.radio

This is the one part of the SEO work that cannot be completed from the repository because it requires access to the domain's DNS zone and to a Google account.

## 1. Add the domain property

1. Open Google Search Console and select **Add property**.
2. Choose **Domain** rather than URL prefix.
3. Enter only:

   ```text
   sofea.radio
   ```

The Domain property covers the apex domain, `www`, HTTP and HTTPS variants.

## 2. Verify ownership through DNS

Google provides a TXT record similar to:

```text
Type:  TXT
Name:  @
Value: google-site-verification=...
```

Add that record to the existing DNS zone. Do not remove the GitHub Pages verification TXT record; multiple TXT records can coexist.

After DNS propagation, return to Search Console and select **Verify**.

## 3. Submit the sitemap

Open **Sitemaps** for the property and submit:

```text
https://sofea.radio/sitemap.xml
```

The generated sitemap includes the homepage, legal pages, all public broadcast detail pages and all public event detail pages.

## 4. Inspect representative URLs

Use **URL inspection** for:

```text
https://sofea.radio/
https://sofea.radio/sendungen/<one-generated-slug>/
https://sofea.radio/termine/<one-generated-slug>/
```

Use **Request indexing** for the homepage and one representative detail page after the first deployment. Normal discovery through the sitemap should handle the remaining pages.

## 5. Ongoing checks

Review Search Console monthly for:

- indexing errors
- unexpected canonical URLs
- sitemap processing errors
- mobile usability issues
- Core Web Vitals
- search terms and pages that receive impressions

A sitemap submission and indexing request are discovery signals, not a guarantee of ranking or immediate indexing.
