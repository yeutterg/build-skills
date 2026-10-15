## Connecting your stack

The audit reads touchpoints through four source types (see `schema.md`): files in a repo, live URLs, pasted text, or `manual` (a blind spot). Nothing here is required; start with URLs and add better sources as you go. Repo sources are preferred when they exist, because findings then point at the exact file and line that needs the fix.

| Platform | Discovery (crawl) | Best audit source |
|---|---|---|
| Shopify | `/products.json` and sitemap, automatic | Theme repo: `templates/*.json`, `sections/*.liquid`, `locales/en.default.json`. Pages and product descriptions via an Admin API export into a content repo |
| WordPress | Sitemap; products via WooCommerce JSON-LD | `/wp-json/wp/v2/pages` and `/posts` exported to JSON, or URL sources |
| Webflow, Squarespace, Wix | Sitemap and JSON-LD | URL sources, or a CMS collection CSV export |
| Next.js, Astro, Hugo, static sites | Sitemap | Repo globs over content (`content/**/*.md*`, `src/**/*.tsx`) |
| Headless CMS (Contentful, Sanity, Storyblok) | Sitemap | JSON export of entries |
| Mobile apps | App Store and Play listings by URL | Repo globs over screens and string files (`*.tsx`, `Localizable.strings`, `strings.xml`, i18n JSON) |
| Help centers (Zendesk, Intercom, Starlight, GitBook) | Sitemap | Article export, or docs repo globs |
| Email (Klaviyo, Mailchimp, Customer.io) | n/a | Template and flow export to HTML files, or paste the copy as a `text` source |
| Marketplaces (Amazon, Etsy) | Listing URLs | Listing export (titles, bullets, descriptions, A+ content) to JSON or text |
| Packaging, inserts, manuals | n/a | Dieline or PDF text pasted as a `text` source, or exported to a file |
| Social, ads | n/a | Exported captions and ad copy as text files |

What the collector reads in each file type:

- `.html`, `.liquid`: visible text, without tags, Liquid schema blocks, scripts, styles or comments
- `.json`: string values that read like copy; configuration keys (ids, colors, sizes, URLs) are skipped
- `.js`, `.ts`, `.tsx`, `.jsx`: string literals and JSX text, never comments or identifiers
- `.md`, `.mdx`: text outside code blocks and import lines
- anything else: line by line

Keep company-specific paths in `journey.config.yaml` `roots`, so the same workspace runs on any machine that has the repos checked out.
