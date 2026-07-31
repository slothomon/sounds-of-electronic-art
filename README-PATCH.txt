SOFEA ASCII + ARCHIVE FIX PATCH

Copy the contents of this directory into the root of the existing
sofea-github-pages repository and overwrite existing files.

The patch does not contain content/site.json or content/episodes.json and
therefore does not overwrite the site's content.

Then run:
  python scripts\build.py
  git add .
  git commit -m "Add ASCII design and fix SoundCloud archive loading"
  git push
