# Sounds of Electronic Art — GitHub Pages site

A dependency-light static site for the Sounds of Electronic Art radio show.

## What is included

- Responsive one-page design
- Next-show card and calendar link
- SoundCloud player
- Searchable broadcast archive
- RSS feed, sitemap, robots.txt and custom 404 page
- Automatic deployment with GitHub Actions and GitHub Pages
- No analytics, cookies or external web fonts

## Edit content

- General information, team and links: `content/site.json`
- Broadcast dates and recordings: `content/episodes.json`

Use ISO 8601 dates including the Leipzig time offset, for example:

```json
{
  "date": "2026-08-29T21:00:00+02:00",
  "title": "Next transmission",
  "status": "upcoming",
  "summary": "Live on Radio Blau.",
  "guests": ["Guest name"],
  "audio_url": null
}
```

Change `status` to `past` after the broadcast and add a recording URL when available.

## Preview locally

```bash
python scripts/build.py
python -m http.server 8000 --directory public
```

Open `http://localhost:8000`.

To test the repository sub-path used by a GitHub project site:

```bash
SITE_URL=https://YOUR-USERNAME.github.io/sounds-of-electronic-art \
  python scripts/build.py
python -m http.server 8000 --directory public
```

## Deploy to GitHub Pages

1. Create a new GitHub repository, preferably named `sounds-of-electronic-art`.
2. Push this repository to the `main` branch.
3. Open **Settings > Pages** in the GitHub repository.
4. Under **Build and deployment**, select **GitHub Actions** as the source.
5. Open the **Actions** tab and wait for the `Deploy GitHub Pages` workflow to finish.

The included workflow is `.github/workflows/pages.yml`. It builds the site, obtains the correct GitHub Pages base URL, uploads the `public` directory and deploys it.

A normal project repository is published at:

```text
https://YOUR-USERNAME.github.io/sounds-of-electronic-art/
```

A repository named exactly `YOUR-USERNAME.github.io` is published at the root URL:

```text
https://YOUR-USERNAME.github.io/
```

A custom domain also removes the repository sub-path.

## Initial Git commands

```bash
git init
git add .
git commit -m "Initial Sounds of Electronic Art website"
git branch -M main
git remote add origin git@github.com:YOUR-USERNAME/sounds-of-electronic-art.git
git push -u origin main
```

## Custom domain

1. Open **Settings > Pages**.
2. Enter the chosen name under **Custom domain**.
3. Add the DNS records requested by GitHub.
4. After the certificate is ready, enable **Enforce HTTPS**.

GitHub recommends verifying the domain before assigning it and generally recommends configuring the `www` subdomain even when the apex domain is also used. Do not add a `CNAME` file manually for this repository: custom GitHub Actions deployments use the domain configured in the repository settings, and the workflow automatically supplies that URL to the build script.

## Migrating the Blogger archive

Export the Blogger site from **Settings > Manage blog > Back up content**. Historic posts can then be converted into structured episode records. Keep the old Blogspot address online during migration and add a final post linking to the new domain.
