(() => {
  'use strict';

  const translations = {
    de: {
      skip: 'Zum Inhalt springen', nav_next: 'Nächste Sendung', nav_listen: 'Hören', nav_about: 'Über uns', nav_archive: 'Archiv', nav_live: 'Livestream',
      hero_eyebrow: 'Radio Blau · Leipzig · seit 2011', hero_subtitle: 'Elektronische Musik, Radio und Clubkultur — alle acht Wochen aus Leipzig.',
      next_heading: 'Nächste Sendung', next_intro: 'Live auf Radio Blau. Drei Stunden mit Musik, Gesprächen und Umwegen durch elektronische Klangwelten.', on_air: 'On Air',
      listen_live: 'Live hören', schedule: 'Sendeplan', calendar: 'Zum Kalender hinzufügen', listen_heading: 'Hören',
      listen_intro: 'Wähle eine Aufnahme aus unserem SoundCloud-Archiv. Der Player wird direkt hier aktualisiert.', selected_recording: 'Ausgewählte Aufnahme', open_soundcloud: 'Auf SoundCloud öffnen ↗',
      about_heading: 'Über die Sendung', about_primary: '<strong>sounds of electronic art</strong> beschäftigt sich mit elektronischer Musik in all ihren Formen. Regelmäßig sprechen Gäste über Clubkultur, Musikszenen und die Räume, in denen sie entstehen.',
      about_secondary: 'Die Sendung wurde 2011 gegründet und wird aus dem Studio von Radio Blau in Leipzig ausgestrahlt.',
      archive_heading: 'Sendungsarchiv', search_label: 'Archiv durchsuchen', archive_empty: 'Keine passenden Sendungen gefunden.',
      archive_loading: 'SoundCloud-Archiv wird geladen …', archive_fallback: 'SoundCloud ist blockiert oder nicht erreichbar. Angezeigt wird der lokale Archivstand.',
      open_playlist: 'Playlist auf SoundCloud öffnen ↗', play_recording: 'Aufnahme abspielen ↗', recording_pending: 'Aufnahme folgt', privacy: 'Kein Tracking. Keine Cookies. Nur Radio.',
      theme_to_light: 'Helles Thema aktivieren', theme_to_dark: 'Dunkles Thema aktivieren',
    },
    en: {
      skip: 'Skip to content', nav_next: 'Next show', nav_listen: 'Listen', nav_about: 'About', nav_archive: 'Archive', nav_live: 'Live stream',
      hero_eyebrow: 'Radio Blau · Leipzig · since 2011', hero_subtitle: 'Electronic music, radio and club culture — broadcast every eight weeks from Leipzig.',
      next_heading: 'Next transmission', next_intro: 'Live on Radio Blau. Three hours of selections, conversations and detours through electronic music.', on_air: 'On air',
      listen_live: 'Listen live', schedule: 'Radio Blau schedule', calendar: 'Add to calendar', listen_heading: 'Listen',
      listen_intro: 'Choose a recording from our SoundCloud archive. The player updates directly on this page.', selected_recording: 'Selected recording', open_soundcloud: 'Open on SoundCloud ↗',
      about_heading: 'About the show', about_primary: '<strong>sounds of electronic art</strong> explores electronic music in all its forms. Guests regularly discuss club culture, music scenes and the spaces in which they emerge.',
      about_secondary: 'The programme was founded in 2011 and broadcasts from the Radio Blau studio in Leipzig.',
      archive_heading: 'Broadcast archive', search_label: 'Search archive', archive_empty: 'No matching broadcasts found.',
      archive_loading: 'Loading the SoundCloud archive …', archive_fallback: 'SoundCloud is blocked or unavailable. Showing the locally stored archive instead.',
      open_playlist: 'Open playlist on SoundCloud ↗', play_recording: 'Play recording ↗', recording_pending: 'Recording pending', privacy: 'No tracking. No cookies. Just radio.',
      theme_to_light: 'Switch to light theme', theme_to_dark: 'Switch to dark theme',
    }
  };

  const playerColor = '#ef9a55';

  const root = document.documentElement;
  const search = document.querySelector('[data-archive-search]');
  const archiveEmpty = document.querySelector('[data-archive-empty]');
  const archiveStatus = document.querySelector('[data-archive-status]');
  const episodeList = document.querySelector('[data-episode-list]');
  let episodes = [...document.querySelectorAll('[data-episode]')];
  const languageButtons = [...document.querySelectorAll('[data-language]')];
  const mixButtons = [...document.querySelectorAll('[data-mix-index]')];
  const player = document.querySelector('[data-soundcloud-player]');
  const playerTitle = document.querySelector('[data-player-title]');
  const playerSubtitle = document.querySelector('[data-player-subtitle]');
  const playerLink = document.querySelector('[data-player-link]');
  const playerLikes = document.querySelector('[data-player-likes]');
  const playerLikesCount = document.querySelector('[data-player-likes-count]');
  const themeToggle = document.querySelector('[data-theme-toggle]');
  const themeIcon = document.querySelector('[data-theme-icon]');
  const themeColorMeta = document.querySelector('meta[name="theme-color"]');
  const archiveWidgetFrame = document.querySelector('[data-archive-playlist-widget]');

  const storageGet = (key) => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const storageSet = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  const delay = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

  let language = storageGet('sofea-language') || 'de';
  let activeMix = 0;
  let archiveState = 'loading';
  let archiveCount = 0;
  let archiveTotal = 0;
  let archiveProgress = 0;
  let archiveReady = false;
  let playerWidget = null;

  const normalise = (value) => String(value || '')
    .toLocaleLowerCase(language === 'de' ? 'de' : 'en')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

  const cleanText = (value) => String(value || '')
    .normalize('NFKC')
    .replace(/[\u200B-\u200D\u2060\uFEFF]/g, '')
    .replace(/\u00a0/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const cleanTitle = (value) => cleanText(value)
    .replace(/\b(20\d{2})\s*[-_.]\s*(\d{1,2})\s*[-_.]\s*(\d{1,2})\b/g, (_, year, month, day) => (
      `${year}-${String(Number(month)).padStart(2, '0')}-${String(Number(day)).padStart(2, '0')}`
    ));

  const currentTheme = () => root.dataset.theme || 'dark';

  const updateExternalLinks = () => {
    document.querySelectorAll('a[href]').forEach((link) => {
      const href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
      try {
        const url = new URL(href, window.location.href);
        if ((url.protocol === 'http:' || url.protocol === 'https:') && url.origin !== window.location.origin) {
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
        }
      } catch (_) {}
    });
  };

  const colorisedEmbed = (embed) => {
    try {
      const url = new URL(embed);
      url.searchParams.set('color', playerColor);
      return url.toString();
    } catch (_) { return embed; }
  };

  const updatePlayerText = () => {
    const button = mixButtons[activeMix];
    if (!button) return;
    if (playerTitle) playerTitle.textContent = button.dataset.title || '';
    if (playerSubtitle) playerSubtitle.textContent = button.dataset[language === 'de' ? 'subtitleDe' : 'subtitleEn'] || '';
  };

  const updateThemeControls = () => {
    const light = currentTheme() === 'light';
    const label = translations[language][light ? 'theme_to_dark' : 'theme_to_light'];
    if (themeToggle) {
      themeToggle.setAttribute('aria-label', label);
      themeToggle.title = label;
      themeToggle.setAttribute('aria-pressed', String(light));
    }
    if (themeIcon) themeIcon.textContent = light ? '☾' : '☀';
    if (themeColorMeta) themeColorMeta.content = light ? '#f7f0e8' : '#151210';
  };

  const updateArchiveStatus = () => {
    if (!archiveStatus) return;
    if (archiveState === 'synced') {
      archiveStatus.textContent = language === 'de'
        ? `${archiveCount} Sendungen geladen.`
        : `${archiveCount} broadcasts loaded.`;
      return;
    }
    if (archiveState === 'partial') {
      archiveStatus.textContent = language === 'de'
        ? `${archiveCount} von ${archiveTotal} Sendungen geladen. Nicht lesbare Einträge wurden ausgelassen.`
        : `${archiveCount} of ${archiveTotal} broadcasts loaded. Unreadable entries were omitted.`;
      return;
    }
    if (archiveState === 'hydrating') {
      archiveStatus.textContent = language === 'de'
        ? `SoundCloud-Archiv wird vervollständigt: ${archiveProgress} / ${archiveTotal} …`
        : `Completing the SoundCloud archive: ${archiveProgress} / ${archiveTotal} …`;
      return;
    }
    archiveStatus.textContent = translations[language][archiveState === 'fallback' ? 'archive_fallback' : 'archive_loading'];
  };

  const applySearch = () => {
    if (!search) return;
    const query = normalise(search.value.trim());
    let visible = 0;
    episodes.forEach((episode) => {
      const haystack = normalise(episode.dataset.search || episode.textContent);
      const matches = !query || haystack.includes(query);
      episode.hidden = !matches;
      if (matches) visible += 1;
    });
    if (archiveEmpty) archiveEmpty.hidden = visible !== 0;
  };

  const applyLanguage = (nextLanguage) => {
    language = translations[nextLanguage] ? nextLanguage : 'de';
    root.lang = language;
    storageSet('sofea-language', language);

    document.querySelectorAll('[data-i18n]').forEach((element) => {
      const value = translations[language][element.dataset.i18n];
      if (value) element.textContent = value;
    });
    document.querySelectorAll('[data-i18n-html]').forEach((element) => {
      const value = translations[language][element.dataset.i18nHtml];
      if (value) element.innerHTML = value;
    });
    document.querySelectorAll('[data-bilingual]').forEach((element) => {
      element.textContent = element.dataset[language] || element.dataset.de || '';
    });
    document.querySelectorAll('[data-mix-subtitle]').forEach((element) => {
      const button = element.closest('[data-mix-index]');
      element.textContent = button?.dataset[language === 'de' ? 'subtitleDe' : 'subtitleEn'] || '';
    });
    document.querySelectorAll('option[data-de][data-en]').forEach((option) => {
      option.textContent = option.dataset[language] || option.dataset.de;
    });
    if (search) search.placeholder = search.dataset[language === 'de' ? 'placeholderDe' : 'placeholderEn'] || '';
    languageButtons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
    updatePlayerText();
    updateThemeControls();
    refreshPlayerLikes();
    updateArchiveStatus();
    applySearch();
  };

  const updatePlayerLikes = (sound) => {
    const rawCount = sound?.likes_count ?? sound?.favoritings_count;
    const count = Number(rawCount);
    const available = Number.isFinite(count) && count >= 0;
    if (playerLikes) playerLikes.hidden = !available;
    if (playerLikesCount) {
      playerLikesCount.textContent = available
        ? new Intl.NumberFormat(language === 'de' ? 'de-DE' : 'en-GB').format(count)
        : '';
    }
  };

  const refreshPlayerLikes = () => {
    updatePlayerLikes(null);
    if (!playerWidget) return;
    try { playerWidget.getCurrentSound(updatePlayerLikes); } catch (_) {}
  };

  const initPlayerWidget = () => {
    if (!player || !window.SC?.Widget) return;
    try {
      playerWidget = window.SC.Widget(player);
      playerWidget.bind(window.SC.Widget.Events.READY, refreshPlayerLikes);
      playerWidget.bind(window.SC.Widget.Events.PLAY, refreshPlayerLikes);
      window.setTimeout(refreshPlayerLikes, 1200);
    } catch (_) {
      playerWidget = null;
    }
  };

  const selectMix = (index, scroll = true) => {
    const button = mixButtons[index];
    if (!button) return;
    activeMix = index;
    mixButtons.forEach((item, itemIndex) => item.setAttribute('aria-pressed', String(itemIndex === index)));
    const embed = colorisedEmbed(button.dataset.embed || '');
    updatePlayerLikes(null);
    if (playerWidget && button.dataset.url) {
      try {
        playerWidget.load(button.dataset.url, {
          color: playerColor, auto_play: false, hide_related: true,
          show_comments: true, show_user: true, show_reposts: true,
          show_playcount: true, show_teaser: false, callback: refreshPlayerLikes
        });
      } catch (_) {
        if (player && player.src !== embed) player.src = embed;
      }
    } else if (player && player.src !== embed) {
      player.src = embed;
    }
    if (playerLink) playerLink.href = button.dataset.url || '#';
    updatePlayerText();
    updateExternalLinks();
    if (scroll) document.querySelector('.player-panel')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };


  const toggleTheme = () => {
    root.dataset.theme = currentTheme() === 'dark' ? 'light' : 'dark';
    storageSet('sofea-theme', root.dataset.theme);
    updateThemeControls();
  };

  const monthIndex = {
    januar: 0, january: 0, februar: 1, february: 1, marz: 2, maerz: 2, march: 2,
    april: 3, mai: 4, may: 4, juni: 5, june: 5, juli: 6, july: 6, august: 7,
    september: 8, oktober: 9, october: 9, november: 10, dezember: 11, december: 11
  };

  const validDate = (year, month, day) => {
    const numericYear = Number(year);
    const numericMonth = Number(month);
    const numericDay = Number(day);
    if (numericYear < 2011 || numericYear > new Date().getFullYear() + 1) return null;
    const date = new Date(numericYear, numericMonth - 1, numericDay, 12, 0, 0);
    if (
      Number.isNaN(date.getTime()) ||
      date.getFullYear() !== numericYear ||
      date.getMonth() !== numericMonth - 1 ||
      date.getDate() !== numericDay
    ) return null;
    return date;
  };

  const dateFromMetadata = (sound) => {
    const candidates = [sound?.release_date, sound?.display_date, sound?.published_at, sound?.created_at];
    for (const candidate of candidates) {
      if (!candidate) continue;
      const date = new Date(candidate);
      if (!Number.isNaN(date.getTime()) && date.getFullYear() >= 2011) return date;
    }
    return null;
  };

  const extractEpisodeDate = (sound) => {
    const text = cleanText(`${sound?.title || ''} ${sound?.description || ''} ${sound?.permalink_url || ''}`);
    let match = text.match(/\b(20\d{2})\s*[-_.]\s*(\d{1,2})\s*[-_.]\s*(\d{1,2})\b/);
    if (match) return validDate(match[1], match[2], match[3]);
    match = text.match(/\b(\d{1,2})\s*[.\/-]\s*(\d{1,2})\s*[.\/-]\s*(20\d{2})\b/);
    if (match) return validDate(match[3], match[2], match[1]);
    const normalisedText = normalise(text);
    match = normalisedText.match(/\b(\d{1,2})\.?\s+(januar|january|februar|february|marz|maerz|march|april|mai|may|juni|june|juli|july|august|september|oktober|october|november|dezember|december)\s+(20\d{2})\b/);
    if (match) return validDate(match[3], monthIndex[match[2]] + 1, match[1]);
    return dateFromMetadata(sound);
  };

  const soundDescription = (sound) => {
    const raw = String(sound?.description || '')
      .split(/\r?\n/)
      .map((line) => cleanText(line))
      .find((line) => line && !/^https?:\/\//i.test(line));
    if (!raw) return '';
    return raw.length > 240 ? `${raw.slice(0, 237).trim()}…` : raw;
  };

  const soundUrl = (sound) => {
    if (sound?.permalink_url) return cleanText(sound.permalink_url);
    if (sound?.user?.permalink && sound?.permalink) return `https://soundcloud.com/${sound.user.permalink}/${sound.permalink}`;
    return '';
  };

  const isReadableSound = (sound) => Boolean(cleanTitle(sound?.title) && soundUrl(sound));

  const formatArchiveDate = (date, locale) => new Intl.DateTimeFormat(locale, {
    day: '2-digit', month: locale === 'de-DE' ? 'long' : 'short', year: 'numeric'
  }).format(date);

  const createEpisode = (sound) => {
    if (!isReadableSound(sound)) return null;
    const date = extractEpisodeDate(sound);
    if (!date) return null;
    const title = cleanTitle(sound.title);
    const originalDescription = soundDescription(sound);
    const url = soundUrl(sound);
    const article = document.createElement('article');
    article.className = 'episode';
    article.dataset.episode = '';
    article.dataset.search = `${title} ${originalDescription} ${date.toISOString()} ${formatArchiveDate(date, 'de-DE')} ${formatArchiveDate(date, 'en-GB')}`;

    const time = document.createElement('time');
    time.className = 'episode-date';
    time.dateTime = date.toISOString();
    time.dataset.bilingual = '';
    time.dataset.de = formatArchiveDate(date, 'de-DE');
    time.dataset.en = formatArchiveDate(date, 'en-GB');
    time.textContent = time.dataset[language];

    const copy = document.createElement('div');
    const heading = document.createElement('h3');
    heading.textContent = title;
    copy.append(heading);
    if (originalDescription) {
      const paragraph = document.createElement('p');
      paragraph.textContent = originalDescription;
      copy.append(paragraph);
    }

    const link = document.createElement('a');
    link.className = 'episode-link';
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.dataset.i18n = 'play_recording';
    link.textContent = translations[language].play_recording;

    article.append(time, copy, link);
    article._archiveDate = date;
    article._archiveKey = String(sound?.id || sound?.urn || url);
    return article;
  };

  const widgetGetter = (widget, method, timeout = 1800) => new Promise((resolve) => {
    let complete = false;
    const finish = (value) => {
      if (complete) return;
      complete = true;
      window.clearTimeout(timer);
      resolve(value);
    };
    const timer = window.setTimeout(() => finish(null), timeout);
    try { widget[method]((value) => finish(value)); } catch (_) { finish(null); }
  });

  const hydrateSoundAt = async (widget, index, stub) => {
    if (isReadableSound(stub)) return stub;
    try { widget.skip(index); } catch (_) { return stub; }
    for (let attempt = 0; attempt < 9; attempt += 1) {
      await delay(attempt === 0 ? 100 : 130);
      const [current, currentIndex] = await Promise.all([
        widgetGetter(widget, 'getCurrentSound', 900),
        widgetGetter(widget, 'getCurrentSoundIndex', 900)
      ]);
      if (Number(currentIndex) === index && isReadableSound(current)) {
        return { ...stub, ...current, user: current.user || stub?.user };
      }
    }
    return stub;
  };

  const hydratePlaylistSounds = async (widget, sounds) => {
    const hydrated = [];
    archiveState = 'hydrating';
    archiveTotal = sounds.length;
    archiveProgress = 0;
    updateArchiveStatus();

    const originalIndex = await widgetGetter(widget, 'getCurrentSoundIndex', 1000);
    try { widget.pause(); } catch (_) {}

    for (let index = 0; index < sounds.length; index += 1) {
      const sound = await hydrateSoundAt(widget, index, sounds[index]);
      hydrated.push(sound);
      archiveProgress = index + 1;
      updateArchiveStatus();
    }

    if (Number.isInteger(Number(originalIndex))) {
      try { widget.skip(Number(originalIndex)); } catch (_) {}
    }
    return hydrated;
  };

  const populateArchiveFromPlaylist = (sounds) => {
    if (!episodeList || !Array.isArray(sounds) || sounds.length === 0) throw new Error('Playlist contains no readable tracks');
    const seen = new Set();
    const rows = sounds
      .map(createEpisode)
      .filter(Boolean)
      .filter((row) => {
        if (seen.has(row._archiveKey)) return false;
        seen.add(row._archiveKey);
        return true;
      })
      .sort((a, b) => b._archiveDate - a._archiveDate);

    if (rows.length === 0) throw new Error('Playlist metadata could not be read');
    episodeList.replaceChildren(...rows);
    episodes = rows;
    archiveCount = rows.length;
    archiveTotal = Math.max(archiveTotal, sounds.length);
    archiveState = rows.length === archiveTotal ? 'synced' : 'partial';
    archiveReady = true;
    updateArchiveStatus();
    updateExternalLinks();
    applySearch();
  };

  const markArchiveFallback = () => {
    if (archiveReady || archiveState === 'hydrating') return;
    archiveState = 'fallback';
    updateArchiveStatus();
  };

  const initPlaylistArchive = () => {
    if (!archiveWidgetFrame || !window.SC?.Widget) {
      markArchiveFallback();
      return;
    }
    try {
      const widget = window.SC.Widget(archiveWidgetFrame);
      widget.bind(window.SC.Widget.Events.READY, () => {
        widget.getSounds(async (sounds) => {
          try {
            if (!Array.isArray(sounds) || sounds.length === 0) throw new Error('Empty playlist');
            archiveTotal = sounds.length;
            const hydrated = await hydratePlaylistSounds(widget, sounds);
            populateArchiveFromPlaylist(hydrated);
          } catch (_) {
            archiveState = 'loading';
            markArchiveFallback();
          }
        });
      });
      widget.bind(window.SC.Widget.Events.ERROR, () => {
        archiveState = 'loading';
        markArchiveFallback();
      });
      window.setTimeout(() => {
        if (archiveState === 'loading') markArchiveFallback();
      }, 15000);
    } catch (_) {
      markArchiveFallback();
    }
  };

  languageButtons.forEach((button) => button.addEventListener('click', () => applyLanguage(button.dataset.language)));
  mixButtons.forEach((button, index) => button.addEventListener('click', () => selectMix(index)));
  themeToggle?.addEventListener('click', toggleTheme);
  search?.addEventListener('input', applySearch);

  const year = document.querySelector('[data-current-year]');
  if (year) year.textContent = String(new Date().getFullYear());

  updateExternalLinks();
  initPlayerWidget();
  applyLanguage(language);
  updateThemeControls();
  initPlaylistArchive();
})();
