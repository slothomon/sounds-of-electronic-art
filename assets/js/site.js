(() => {
  'use strict';

  const translations = {
    de: {
      skip: 'Zum Inhalt springen', nav_next: 'Upcoming', nav_listen: 'Hören', nav_about: 'Über uns', nav_archive: 'Archiv', nav_live: 'Livestream',
      hero_eyebrow: 'Radio Blau · Leipzig · seit 2011', hero_subtitle: 'Elektronische Musik, Radio und Clubkultur — alle acht Wochen aus Leipzig.',
      next_heading: 'Upcoming', on_air: 'On Air',
      listen_live: 'Live hören', schedule: 'Sendeplan', calendar: 'Zum Kalender hinzufügen', listen_heading: 'Hören',
      selected_recording: 'Ausgewählte Aufnahme', open_soundcloud: 'Auf SoundCloud öffnen ↗',
      about_heading: 'Über die Sendung', about_primary: '<strong>sounds of electronic art</strong> beschäftigt sich mit elektronischer Musik in all ihren Formen. Regelmäßig sprechen Gäste über Clubkultur, Musikszenen und die Räume, in denen sie entstehen.',
      about_secondary: 'Die Sendung wurde 2011 gegründet und wird aus dem Studio von Radio Blau in Leipzig ausgestrahlt.',
      archive_heading: 'Sendungsarchiv', search_label: 'Archiv durchsuchen', archive_empty: 'Keine passenden Sendungen gefunden.',
      open_playlist: 'Playlist auf SoundCloud öffnen ↗', play_recording: 'Aufnahme abspielen ↗', privacy: 'Kein Tracking. Keine Cookies. Nur Radio.',
      theme_to_light: 'Helles Thema aktivieren', theme_to_dark: 'Dunkles Thema aktivieren',
    },
    en: {
      skip: 'Skip to content', nav_next: 'Upcoming', nav_listen: 'Listen', nav_about: 'About', nav_archive: 'Archive', nav_live: 'Live stream',
      hero_eyebrow: 'Radio Blau · Leipzig · since 2011', hero_subtitle: 'Electronic music, radio and club culture — broadcast every eight weeks from Leipzig.',
      next_heading: 'Upcoming', on_air: 'On air',
      listen_live: 'Listen live', schedule: 'Radio Blau schedule', calendar: 'Add to calendar', listen_heading: 'Listen',
      selected_recording: 'Selected recording', open_soundcloud: 'Open on SoundCloud ↗',
      about_heading: 'About the show', about_primary: '<strong>sounds of electronic art</strong> explores electronic music in all its forms. Guests regularly discuss club culture, music scenes and the spaces in which they emerge.',
      about_secondary: 'The programme was founded in 2011 and broadcasts from the Radio Blau studio in Leipzig.',
      archive_heading: 'Broadcast archive', search_label: 'Search archive', archive_empty: 'No matching broadcasts found.',
      open_playlist: 'Open playlist on SoundCloud ↗', play_recording: 'Play recording ↗', privacy: 'No tracking. No cookies. Just radio.',
      theme_to_light: 'Switch to light theme', theme_to_dark: 'Switch to dark theme',
    },
  };

  const playerColor = '#ef9a55';
  const root = document.documentElement;
  const search = document.querySelector('[data-archive-search]');
  const archiveEmpty = document.querySelector('[data-archive-empty]');
  const episodes = [...document.querySelectorAll('[data-episode]')];
  const languageButtons = [...document.querySelectorAll('[data-language]')];
  const mixButtons = [...document.querySelectorAll('[data-mix-index]')];
  const player = document.querySelector('[data-soundcloud-player]');
  const playerTitle = document.querySelector('[data-player-title]');
  const playerSubtitle = document.querySelector('[data-player-subtitle]');
  const playerLink = document.querySelector('[data-player-link]');
  const themeToggle = document.querySelector('[data-theme-toggle]');
  const themeIcon = document.querySelector('[data-theme-icon]');
  const themeColorMeta = document.querySelector('meta[name="theme-color"]');

  const storageGet = (key) => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const storageSet = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };

  let language = storageGet('sofea-language') || 'de';
  let activeMix = 0;

  const normalise = (value) => String(value || '')
    .toLocaleLowerCase(language === 'de' ? 'de' : 'en')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

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
      url.searchParams.set('show_comments', 'true');
      url.searchParams.set('show_reposts', 'true');
      url.searchParams.set('show_playcount', 'true');
      return url.toString();
    } catch (_) {
      return embed;
    }
  };

  const updatePlayerText = () => {
    const button = mixButtons[activeMix];
    if (!button) return;
    const title = button.dataset.title || '';
    if (playerTitle) playerTitle.textContent = title;
    if (playerSubtitle) playerSubtitle.textContent = button.dataset[language === 'de' ? 'subtitleDe' : 'subtitleEn'] || '';
    if (player) player.title = language === 'de' ? `${title} auf SoundCloud` : `${title} on SoundCloud`;
  };

  const selectMix = (index, scroll = true) => {
    const button = mixButtons[index];
    if (!button) return;
    activeMix = index;
    mixButtons.forEach((item, itemIndex) => item.setAttribute('aria-pressed', String(itemIndex === index)));
    const embed = colorisedEmbed(button.dataset.embed || '');
    if (player && player.src !== embed) player.src = embed;
    if (playerLink) playerLink.href = button.dataset.url || '#';
    updatePlayerText();
    updateExternalLinks();
    if (scroll) document.querySelector('.player-panel')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
    if (themeColorMeta) themeColorMeta.content = light ? '#fdf6e3' : '#151210';
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
    if (search) search.placeholder = search.dataset[language === 'de' ? 'placeholderDe' : 'placeholderEn'] || '';
    languageButtons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
    updatePlayerText();
    updateThemeControls();
    applySearch();
  };

  const toggleTheme = () => {
    root.dataset.theme = currentTheme() === 'dark' ? 'light' : 'dark';
    storageSet('sofea-theme', root.dataset.theme);
    updateThemeControls();
  };

  languageButtons.forEach((button) => button.addEventListener('click', () => applyLanguage(button.dataset.language)));
  mixButtons.forEach((button, index) => button.addEventListener('click', () => selectMix(index)));
  themeToggle?.addEventListener('click', toggleTheme);
  search?.addEventListener('input', applySearch);

  const year = document.querySelector('[data-current-year]');
  if (year) year.textContent = String(new Date().getFullYear());

  updateExternalLinks();
  applyLanguage(language);
  updateThemeControls();
})();
