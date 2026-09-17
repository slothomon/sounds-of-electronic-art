# Search visibility and stable URLs

The homepage identifies the show as **sounds of electronic art (sofea)** and
connects it to Radio Blau and Leipzig. German remains the default language.
Existing editorial descriptions take precedence over generated summaries.
Where an episode has no prose, the build adds a factual summary with its title,
broadcast date, number where known, and a recording link only when one exists.
This summary appears on the episode page and supplies its meta-description
fallback. It does not invent genres, biographical details or audio availability.

## Published addresses

Archive addresses are based on the persisted `episode_id`, not the editable
display title. Do not change an episode ID after publication. The two existing
addresses that differ from their IDs are preserved by `url_path` in the local
archive entries. Leave that compatibility field in place.

When `scripts/archive_broadcasts.py` archives a broadcast, it records the
announcement address in `redirect_from`. The build then writes a redirect at
that old address. Ended announcements remain accessible between the end of a
broadcast and the next archive job, even though they disappear from Demnächst.

GitHub Pages does not provide per-path server redirect rules. These generated
pages use an **instant HTML meta refresh**, an identical canonical target and a
normal link. They return HTTP 200 from Pages, not HTTP 301. Google documents
instant meta-refresh redirects as a permanent redirect signal:
<https://developers.google.com/search/docs/crawling-indexing/301-redirects>.
Redirect pages are excluded from the sitemap. Conflicts, self-redirects and
missing targets fail the build. Historical links predating the supplied source
can be added to the appropriate episode's `redirect_from` once identified.

The URL compatibility fields are hidden in Pages CMS. Keep them in the source
when editing JSON by hand. Display titles and editorial texts remain editable.

## Sitemap dates

`lastmod` uses only an episode's explicit, valid `updated_at` date. Unknown dates
are omitted. Updating the SoundCloud cache does not mark every episode as new.
Set “Inhalt zuletzt wesentlich geändert” in Pages CMS when significantly
changing an episode's content. Never use the broadcast date as a substitute for
the page's last modification date.

## Search Console

Inspect `https://sofea.radio/` after deployment and request indexing once.
Keep `https://sofea.radio/sitemap.xml` submitted. “Page with redirect” for the
HTTP homepage, `www` or an archived announcement is expected. Check the final
canonical page's indexing status instead of removing the redirect.

Compare branded queries (`sofea`, `sounds of electronic art`) separately from
guest-name searches over the following weeks. With a six-week-old site and
57 recorded impressions, the overall average position is not a reliable measure
of ranking for either individual brand query.
