# Structured data templates

These are templates for a later JSON-LD integration. Replace all values in angle brackets and include the resulting block in the `<head>` of the matching canonical page.

Validate finished markup with Google's Rich Results Test and Schema.org's validator before publishing it.

## Radio programme / series

Recommended for the homepage:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "RadioSeries",
  "@id": "https://sofea.radio/#radio-series",
  "name": "sounds of electronic art",
  "alternateName": "sofea",
  "url": "https://sofea.radio/",
  "inLanguage": ["de", "en"],
  "description": "Elektronische Musik, Radio und Clubkultur — alle acht Wochen aus Leipzig.",
  "productionCompany": {
    "@type": "Organization",
    "name": "Radio Blau",
    "url": "https://www.radioblau.de/"
  },
  "sameAs": [
    "https://soundcloud.com/sounds-of-electronic-art",
    "https://www.instagram.com/sounds_of_electronic_art/"
  ]
}
</script>
```

## Archived broadcast / radio episode

Recommended for a generated page below `/sendungen/`:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "RadioEpisode",
  "@id": "https://sofea.radio/sendungen/<slug>/#episode",
  "url": "https://sofea.radio/sendungen/<slug>/",
  "name": "<episode title>",
  "description": "<episode summary>",
  "datePublished": "<YYYY-MM-DD>",
  "inLanguage": "de",
  "partOfSeries": {
    "@id": "https://sofea.radio/#radio-series"
  },
  "associatedMedia": {
    "@type": "AudioObject",
    "name": "<episode title>",
    "contentUrl": "<public SoundCloud track URL>",
    "duration": "<ISO-8601 duration, for example PT2H8M>"
  }
}
</script>
```

Omit `duration` when no reliable duration is available. Do not invent values.

## Upcoming event

Recommended for a generated page below `/termine/`:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "MusicEvent",
  "@id": "https://sofea.radio/termine/<slug>/#event",
  "url": "https://sofea.radio/termine/<slug>/",
  "name": "<event title>",
  "description": "<event summary>",
  "startDate": "<YYYY-MM-DDTHH:MM:SS+02:00>",
  "endDate": "<YYYY-MM-DDTHH:MM:SS+02:00>",
  "eventStatus": "https://schema.org/EventScheduled",
  "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
  "location": {
    "@type": "Place",
    "name": "<venue name>",
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "Leipzig",
      "addressCountry": "DE"
    }
  },
  "image": [
    "<absolute flyer or event image URL>"
  ],
  "performer": [
    {
      "@type": "Person",
      "name": "<artist name>",
      "sameAs": "<artist profile URL>"
    }
  ],
  "organizer": {
    "@type": "Organization",
    "name": "sounds of electronic art",
    "url": "https://sofea.radio/"
  }
}
</script>
```

Use `OnlineEventAttendanceMode` only for a genuinely online event. For a hybrid event, use `MixedEventAttendanceMode` and add a `VirtualLocation` as appropriate.

## Implementation notes

- The values must match visible page content.
- Use absolute canonical URLs.
- Include only data that is known and publicly visible.
- Event markup is eligible for event-specific Google features only when the page and data meet Google's current event guidelines.
- Schema.org types can still help machines understand a page even when Google does not provide a dedicated rich result for that type.
