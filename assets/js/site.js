(() => {
  const translations = {
    de: {
      skip: 'Zum Inhalt springen', nav_next: 'Nächste Sendung', nav_listen: 'Hören', nav_about: 'Über uns', nav_archive: 'Archiv', nav_live: 'Livestream',
      hero_eyebrow: 'Radio Blau · Leipzig · seit 2011', hero_subtitle: 'Elektronische Musik, Radio und Clubkultur — alle acht Wochen aus Leipzig.',
      next_heading: 'Nächste Sendung', next_intro: 'Live auf Radio Blau. Drei Stunden mit Musik, Gesprächen und Umwegen durch elektronische Klangwelten.', on_air: 'On Air',
      listen_live: 'Live hören', schedule: 'Sendeplan', calendar: 'Zum Kalender hinzufügen', listen_heading: 'Hören',
      listen_intro: 'Wähle eine Aufnahme aus unserem SoundCloud-Archiv. Der Player wird direkt hier aktualisiert.', selected_recording: 'Ausgewählte Aufnahme', open_soundcloud: 'Auf SoundCloud öffnen ↗',
      about_heading: 'Über die Sendung', about_primary: '<strong>sounds of electronic art</strong> beschäftigt sich mit elektronischer Musik in all ihren Formen. Regelmäßig sprechen Gäste über Clubkultur, Musikszenen und die Räume, in denen sie entstehen.',
      about_secondary: 'Die Sendung wurde 2011 gegründet und wird aus dem Studio von Radio Blau in Leipzig ausgestrahlt.',
      archive_heading: 'Sendungsarchiv', archive_intro: 'Das Archiv wird schrittweise um frühere Blogbeiträge und Aufnahmen ergänzt.', search_label: 'Archiv durchsuchen',
      play_recording: 'Aufnahme abspielen ↗', recording_pending: 'Aufnahme folgt', privacy: 'Kein Tracking. Keine Cookies. Nur Radio.'
    },
    en: {
      skip: 'Skip to content', nav_next: 'Next show', nav_listen: 'Listen', nav_about: 'About', nav_archive: 'Archive', nav_live: 'Live stream',
      hero_eyebrow: 'Radio Blau · Leipzig · since 2011', hero_subtitle: 'Electronic music, radio and club culture — broadcast every eight weeks from Leipzig.',
      next_heading: 'Next transmission', next_intro: 'Live on Radio Blau. Three hours of selections, conversations and detours through electronic music.', on_air: 'On air',
      listen_live: 'Listen live', schedule: 'Radio Blau schedule', calendar: 'Add to calendar', listen_heading: 'Listen',
      listen_intro: 'Choose a recording from our SoundCloud archive. The player updates directly on this page.', selected_recording: 'Selected recording', open_soundcloud: 'Open on SoundCloud ↗',
      about_heading: 'About the show', about_primary: '<strong>sounds of electronic art</strong> explores electronic music in all its forms. Guests regularly discuss club culture, music scenes and the spaces in which they emerge.',
      about_secondary: 'The programme was founded in 2011 and broadcasts from the Radio Blau studio in Leipzig.',
      archive_heading: 'Broadcast archive', archive_intro: 'The archive will gradually be extended with earlier blog posts and recordings.', search_label: 'Search archive',
      play_recording: 'Play recording ↗', recording_pending: 'Recording pending', privacy: 'No tracking. No cookies. Just radio.'
    }
  };

  const search = document.querySelector('[data-archive-search]');
  const episodes = [...document.querySelectorAll('[data-episode]')];
  const languageButtons = [...document.querySelectorAll('[data-language]')];
  const mixButtons = [...document.querySelectorAll('[data-mix-index]')];
  const player = document.querySelector('[data-soundcloud-player]');
  const playerTitle = document.querySelector('[data-player-title]');
  const playerSubtitle = document.querySelector('[data-player-subtitle]');
  const playerLink = document.querySelector('[data-player-link]');
  let language = localStorage.getItem('sofea-language') || 'de';
  let activeMix = 0;

  const applyLanguage = (nextLanguage) => {
    language = translations[nextLanguage] ? nextLanguage : 'de';
    document.documentElement.lang = language;
    localStorage.setItem('sofea-language', language);

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
      element.textContent = button?.dataset[`subtitle${language === 'de' ? 'De' : 'En'}`] || '';
    });
    if (search) search.placeholder = search.dataset[`placeholder${language === 'de' ? 'De' : 'En'}`] || '';
    languageButtons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
    updatePlayerText();
  };

  const updatePlayerText = () => {
    const button = mixButtons[activeMix];
    if (!button) return;
    if (playerTitle) playerTitle.textContent = button.dataset.title || '';
    if (playerSubtitle) playerSubtitle.textContent = button.dataset[`subtitle${language === 'de' ? 'De' : 'En'}`] || '';
  };

  const selectMix = (index) => {
    const button = mixButtons[index];
    if (!button) return;
    activeMix = index;
    mixButtons.forEach((item, itemIndex) => item.setAttribute('aria-pressed', String(itemIndex === index)));
    if (player && player.src !== button.dataset.embed) player.src = button.dataset.embed;
    if (playerLink) playerLink.href = button.dataset.url || '#';
    updatePlayerText();
    document.querySelector('.player-panel')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  languageButtons.forEach((button) => button.addEventListener('click', () => applyLanguage(button.dataset.language)));
  mixButtons.forEach((button, index) => button.addEventListener('click', () => selectMix(index)));

  if (search) {
    search.addEventListener('input', () => {
      const query = search.value.trim().toLocaleLowerCase(language === 'de' ? 'de' : 'en');
      episodes.forEach((episode) => {
        episode.hidden = query !== '' && !episode.textContent.toLocaleLowerCase().includes(query);
      });
    });
  }

  const year = document.querySelector('[data-current-year]');
  if (year) year.textContent = String(new Date().getFullYear());
  applyLanguage(language);
})();
