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
      open_playlist: 'Playlist auf SoundCloud öffnen ↗', play_recording: 'Aufnahme abspielen ↗', imprint_link: 'Impressum', privacy_link: 'Datenschutz',
      pagination_prev: '← Zurück', pagination_next: 'Weiter →', pagination_label: 'Archivseiten', pagination_pages: 'Seiten', pagination_page: 'Seite',
      theme_to_light: 'Helles Thema aktivieren', theme_to_dark: 'Dunkles Thema aktivieren', back_to_top: 'Nach oben', permalink: 'Direktlink zu dieser Sendung', detail_open: 'Details öffnen', detail_close: 'Details schließen',
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
      open_playlist: 'Open playlist on SoundCloud ↗', play_recording: 'Play recording ↗', imprint_link: 'Legal notice', privacy_link: 'Privacy',
      pagination_prev: '← Previous', pagination_next: 'Next →', pagination_label: 'Archive pages', pagination_pages: 'Pages', pagination_page: 'Page',
      theme_to_light: 'Switch to light theme', theme_to_dark: 'Switch to dark theme', back_to_top: 'Back to top', permalink: 'Direct link to this broadcast', detail_open: 'Open details', detail_close: 'Close details',
    },
  };

  const playerColor = '#ef9a55';
  const PAGE_SIZE = 10;
  const root = document.documentElement;
  const search = document.querySelector('[data-archive-search]');
  const archiveEmpty = document.querySelector('[data-archive-empty]');
  const archiveSection = document.querySelector('#archive');
  const pagination = document.querySelector('[data-archive-pagination]');
  const pageNumbers = document.querySelector('[data-page-numbers]');
  const previousPage = document.querySelector('[data-page-prev]');
  const nextPage = document.querySelector('[data-page-next]');
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
  const backToTop = document.querySelector('[data-back-to-top]');
  const detailDialogs = [...document.querySelectorAll('[data-detail-dialog]')];
  const detailLinks = [...document.querySelectorAll('[data-detail-link]')];
  const detailCloseButtons = [...document.querySelectorAll('[data-detail-close]')];
  const sectionLinks = [...document.querySelectorAll('[data-section-link]')];
  const sectionTargets = sectionLinks
    .map((link) => ({ link, target: document.querySelector(link.getAttribute('href')) }))
    .filter((entry) => entry.target);
  const mobileNavigation = window.matchMedia('(max-width: 900px)');

  const storageGet = (key) => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const storageSet = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };

  let language = storageGet('sofea-language') || 'de';
  let activeMix = 0;
  let currentPage = 1;

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


  const openDialog = () => detailDialogs.find((dialog) => dialog.open) || null;

  const revealEpisodeForDetail = (detailId) => {
    const target = episodes.find((episode) => episode.dataset.detailId === detailId);
    if (!target) return;
    if (search) search.value = '';
    const index = episodes.indexOf(target);
    if (index >= 0) {
      currentPage = Math.floor(index / PAGE_SIZE) + 1;
      applyArchive();
    }
  };

  const showDetail = (dialog, { updateHistory = true } = {}) => {
    if (!dialog) return false;
    const current = openDialog();
    if (current && current !== dialog) current.close();
    revealEpisodeForDetail(dialog.id);
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('detail-open');
    if (updateHistory && window.location.hash !== `#${dialog.id}`) {
      window.history.pushState({ sofeaDetail: dialog.id }, '', `#${dialog.id}`);
    }
    return true;
  };

  const hideDetail = (dialog, { updateHistory = true } = {}) => {
    if (!dialog) return;
    if (updateHistory && window.location.hash === `#${dialog.id}`) {
      if (window.history.state?.sofeaDetail === dialog.id) {
        window.history.back();
        return;
      }
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
    }
    if (dialog.open) dialog.close();
    if (!openDialog()) document.body.classList.remove('detail-open');
  };

  const syncDetailFromLocation = () => {
    const id = decodeURIComponent(window.location.hash.slice(1));
    const dialog = id ? document.getElementById(id) : null;
    if (dialog?.matches('[data-detail-dialog]')) {
      showDetail(dialog, { updateHistory: false });
      return true;
    }
    const current = openDialog();
    if (current) hideDetail(current, { updateHistory: false });
    return false;
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

  const updateBackToTop = () => {
    if (!backToTop) return;
    const visible = window.scrollY > Math.max(650, window.innerHeight * 0.8);
    backToTop.classList.toggle('is-visible', visible);
    backToTop.setAttribute('aria-hidden', String(!visible));
    backToTop.tabIndex = visible ? 0 : -1;
  };

  let activeSectionId = '';
  const updateActiveSection = () => {
    if (!sectionTargets.length || !mobileNavigation.matches) {
      sectionLinks.forEach((link) => link.removeAttribute('aria-current'));
      activeSectionId = '';
      return;
    }

    const headerOffset = (document.querySelector('.site-header')?.offsetHeight || 0) + 28;
    let active = null;
    sectionTargets.forEach((entry) => {
      if (entry.target.getBoundingClientRect().top <= headerOffset) active = entry;
    });
    if (!active && sectionTargets[0].target.getBoundingClientRect().top < window.innerHeight * 0.72) {
      active = sectionTargets[0];
    }
    const nextId = active?.target.id || '';
    sectionTargets.forEach((entry) => {
      if (entry.target.id === nextId) entry.link.setAttribute('aria-current', 'location');
      else entry.link.removeAttribute('aria-current');
    });
    if (nextId && nextId !== activeSectionId) {
      activeSectionId = nextId;
      active?.link.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
  };

  let scrollTicking = false;
  const updateScrollUi = () => {
    if (scrollTicking) return;
    scrollTicking = true;
    window.requestAnimationFrame(() => {
      updateBackToTop();
      updateActiveSection();
      scrollTicking = false;
    });
  };

  const paginationItems = (totalPages) => {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);

    const items = [1];
    let start = Math.max(2, currentPage - 1);
    let end = Math.min(totalPages - 1, currentPage + 1);

    if (currentPage <= 4) end = 5;
    if (currentPage >= totalPages - 3) start = totalPages - 4;
    if (start > 2) items.push('ellipsis');
    for (let page = start; page <= end; page += 1) items.push(page);
    if (end < totalPages - 1) items.push('ellipsis');
    items.push(totalPages);
    return items;
  };

  const renderPagination = (totalPages) => {
    if (!pagination || !pageNumbers || !previousPage || !nextPage) return;
    pagination.hidden = totalPages <= 1;
    pagination.setAttribute('aria-label', translations[language].pagination_label);
    pageNumbers.setAttribute('aria-label', translations[language].pagination_pages);
    pageNumbers.replaceChildren();

    if (totalPages <= 1) return;

    paginationItems(totalPages).forEach((item) => {
      if (item === 'ellipsis') {
        const ellipsis = document.createElement('span');
        ellipsis.className = 'pagination-ellipsis';
        ellipsis.textContent = '…';
        ellipsis.setAttribute('aria-hidden', 'true');
        pageNumbers.append(ellipsis);
        return;
      }

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'pagination-page';
      button.textContent = String(item);
      button.setAttribute('aria-label', `${translations[language].pagination_page} ${item}`);
      if (item === currentPage) button.setAttribute('aria-current', 'page');
      button.addEventListener('click', () => goToPage(item));
      pageNumbers.append(button);
    });

    previousPage.disabled = currentPage === 1;
    nextPage.disabled = currentPage === totalPages;
  };

  const filteredEpisodes = () => {
    const query = normalise(search?.value.trim() || '');
    return episodes.filter((episode) => {
      const haystack = normalise(episode.dataset.search || episode.textContent);
      return !query || haystack.includes(query);
    });
  };

  const applyArchive = ({ resetPage = false } = {}) => {
    if (resetPage) currentPage = 1;
    const matches = filteredEpisodes();
    const totalPages = Math.ceil(matches.length / PAGE_SIZE);
    if (totalPages > 0) currentPage = Math.min(currentPage, totalPages);
    else currentPage = 1;

    const visibleEpisodes = new Set(
      matches.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE),
    );
    episodes.forEach((episode) => { episode.hidden = !visibleEpisodes.has(episode); });
    if (archiveEmpty) archiveEmpty.hidden = matches.length !== 0;
    renderPagination(totalPages);
  };

  const revealEpisodeFromHash = ({ scroll = true } = {}) => {
    if (!window.location.hash.startsWith('#episode-')) return false;
    const target = document.getElementById(window.location.hash.slice(1));
    if (!target || !target.matches('[data-episode]')) return false;
    if (search) search.value = '';
    const index = episodes.indexOf(target);
    if (index < 0) return false;
    currentPage = Math.floor(index / PAGE_SIZE) + 1;
    applyArchive();
    if (scroll) window.requestAnimationFrame(() => target.scrollIntoView({ behavior: 'smooth', block: 'center' }));
    target.classList.add('is-linked');
    window.setTimeout(() => target.classList.remove('is-linked'), 1800);
    return true;
  };

  function goToPage(page) {
    const totalPages = Math.ceil(filteredEpisodes().length / PAGE_SIZE);
    if (!Number.isInteger(page) || page < 1 || page > totalPages || page === currentPage) return;
    currentPage = page;
    applyArchive();
    archiveSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

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
    document.querySelectorAll('[data-language-panel]').forEach((element) => {
      element.hidden = element.dataset.languagePanel !== language;
    });
    document.querySelectorAll('[data-mix-subtitle]').forEach((element) => {
      const button = element.closest('[data-mix-index]');
      element.textContent = button?.dataset[language === 'de' ? 'subtitleDe' : 'subtitleEn'] || '';
    });
    if (search) search.placeholder = search.dataset[language === 'de' ? 'placeholderDe' : 'placeholderEn'] || '';
    languageButtons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
    document.querySelectorAll('[data-episode-permalink]').forEach((link) => {
      link.setAttribute('aria-label', translations[language].permalink);
      link.title = translations[language].permalink;
    });
    detailLinks.forEach((link) => {
      link.setAttribute('aria-label', `${translations[language].detail_open}: ${link.textContent.trim()}`);
    });
    detailCloseButtons.forEach((button) => {
      const label = button.dataset[language === 'de' ? 'labelDe' : 'labelEn'] || translations[language].detail_close;
      button.setAttribute('aria-label', label);
      button.title = label;
    });
    document.querySelectorAll('[data-alt-de]').forEach((image) => {
      image.alt = image.dataset[language === 'de' ? 'altDe' : 'altEn'] || image.dataset.altDe || '';
    });
    if (backToTop) {
      backToTop.setAttribute('aria-label', translations[language].back_to_top);
      backToTop.title = translations[language].back_to_top;
    }
    updatePlayerText();
    updateThemeControls();
    applyArchive();
  };

  const toggleTheme = () => {
    root.dataset.theme = currentTheme() === 'dark' ? 'light' : 'dark';
    storageSet('sofea-theme', root.dataset.theme);
    updateThemeControls();
  };

  languageButtons.forEach((button) => button.addEventListener('click', () => applyLanguage(button.dataset.language)));
  mixButtons.forEach((button, index) => button.addEventListener('click', () => selectMix(index)));
  detailLinks.forEach((link) => link.addEventListener('click', (event) => {
    const id = decodeURIComponent((link.getAttribute('href') || '').replace(/^#/, ''));
    const dialog = document.getElementById(id);
    if (!dialog?.matches('[data-detail-dialog]')) return;
    event.preventDefault();
    showDetail(dialog);
  }));
  detailCloseButtons.forEach((button) => button.addEventListener('click', () => {
    hideDetail(button.closest('[data-detail-dialog]'));
  }));
  detailDialogs.forEach((dialog) => {
    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      hideDetail(dialog);
    });
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) hideDetail(dialog);
    });
    dialog.addEventListener('close', () => {
      if (!openDialog()) document.body.classList.remove('detail-open');
    });
  });
  themeToggle?.addEventListener('click', toggleTheme);
  search?.addEventListener('input', () => applyArchive({ resetPage: true }));
  previousPage?.addEventListener('click', () => goToPage(currentPage - 1));
  nextPage?.addEventListener('click', () => goToPage(currentPage + 1));
  backToTop?.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
  window.addEventListener('scroll', updateScrollUi, { passive: true });
  window.addEventListener('resize', updateScrollUi);
  const syncLocationUi = () => {
    if (syncDetailFromLocation()) return;
    if (!revealEpisodeFromHash()) updateScrollUi();
  };
  window.addEventListener('hashchange', syncLocationUi);
  window.addEventListener('popstate', syncLocationUi);

  const year = document.querySelector('[data-current-year]');
  if (year) year.textContent = String(new Date().getFullYear());

  updateExternalLinks();
  applyLanguage(language);
  updateThemeControls();
  if (!syncDetailFromLocation()) revealEpisodeFromHash({ scroll: false });
  updateScrollUi();
})();
