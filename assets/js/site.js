(() => {
  'use strict';

  const root = document.documentElement;
  const body = document.body;

  const copy = {
    de: {
      skip: 'Zum Inhalt springen',
      nav_next: 'Upcoming',
      nav_listen: 'Hören',
      nav_about: 'Über uns',
      nav_archive: 'Archiv',
      nav_live: 'Livestream',
      hero_eyebrow: 'Radio Blau · Leipzig · seit 2011',
      hero_subtitle: 'Elektronische Musik, Radio und Clubkultur — alle acht Wochen aus Leipzig.',
      next_heading: 'Upcoming',
      listen_heading: 'Hören',
      selected_recording: 'Ausgewählte Aufnahme',
      open_soundcloud: 'Auf SoundCloud öffnen ↗',
      load_soundcloud: 'SoundCloud-Player laden',
      close_player: 'Player schließen',
      about_heading: 'Über die Sendung',
      about_primary: '<strong>sounds of electronic art</strong> beschäftigt sich mit elektronischer Musik in all ihren Formen. Regelmäßig sprechen Gäste über Clubkultur, Musikszenen und die Räume, in denen sie entstehen.',
      about_secondary: 'Die Sendung wurde 2011 gegründet und wird aus dem Studio von Radio Blau in Leipzig ausgestrahlt.',
      archive_heading: 'Sendungsarchiv',
      open_playlist: 'Playlist auf SoundCloud öffnen ↗',
      search_label: 'Archiv durchsuchen',
      archive_empty: 'Keine passenden Sendungen gefunden.',
      pagination_prev: '← Zurück',
      pagination_next: 'Weiter →',
      play_recording: 'Aufnahme abspielen ↗',
      imprint_link: 'Impressum',
      privacy_link: 'Datenschutz'
    },
    en: {
      skip: 'Skip to content',
      nav_next: 'Upcoming',
      nav_listen: 'Listen',
      nav_about: 'About',
      nav_archive: 'Archive',
      nav_live: 'Live stream',
      hero_eyebrow: 'Radio Blau · Leipzig · since 2011',
      hero_subtitle: 'Electronic music, radio and club culture — broadcast every eight weeks from Leipzig.',
      next_heading: 'Upcoming',
      listen_heading: 'Listen',
      selected_recording: 'Selected recording',
      open_soundcloud: 'Open on SoundCloud ↗',
      load_soundcloud: 'Load SoundCloud player',
      close_player: 'Close player',
      about_heading: 'About the show',
      about_primary: '<strong>sounds of electronic art</strong> explores electronic music in all its forms. Guests regularly discuss club culture, music scenes and the spaces in which they emerge.',
      about_secondary: 'The show was founded in 2011 and is broadcast from the Radio Blau studio in Leipzig.',
      archive_heading: 'Broadcast archive',
      open_playlist: 'Open playlist on SoundCloud ↗',
      search_label: 'Search the archive',
      archive_empty: 'No matching broadcasts found.',
      pagination_prev: '← Previous',
      pagination_next: 'Next →',
      play_recording: 'Play recording ↗',
      imprint_link: 'Legal notice',
      privacy_link: 'Privacy'
    }
  };

  const safeStorage = {
    get(key) {
      try { return localStorage.getItem(key); } catch (_) { return null; }
    },
    set(key, value) {
      try { localStorage.setItem(key, value); } catch (_) {}
    }
  };

  let language = safeStorage.get('sofea-language') === 'en' ? 'en' : 'de';

  function applyLanguage(nextLanguage, persist = true) {
    language = nextLanguage === 'en' ? 'en' : 'de';
    root.lang = language;

    document.querySelectorAll('[data-i18n]').forEach((element) => {
      const value = copy[language][element.dataset.i18n];
      if (value !== undefined) element.textContent = value;
    });
    document.querySelectorAll('[data-i18n-html]').forEach((element) => {
      const value = copy[language][element.dataset.i18nHtml];
      if (value !== undefined) element.innerHTML = value;
    });
    document.querySelectorAll('[data-bilingual]').forEach((element) => {
      const value = element.dataset[language];
      if (value !== undefined) element.textContent = value;
    });
    document.querySelectorAll('[data-language-panel]').forEach((element) => {
      element.hidden = element.dataset.languagePanel !== language;
    });
    document.querySelectorAll('[data-alt-de][data-alt-en]').forEach((image) => {
      image.alt = language === 'en' ? image.dataset.altEn : image.dataset.altDe;
    });
    document.querySelectorAll('[data-placeholder-de][data-placeholder-en]').forEach((input) => {
      input.placeholder = language === 'en' ? input.dataset.placeholderEn : input.dataset.placeholderDe;
    });
    document.querySelectorAll('[data-language]').forEach((button) => {
      const active = button.dataset.language === language;
      button.setAttribute('aria-pressed', String(active));
    });
    document.querySelectorAll('[data-detail-close]').forEach((button) => {
      button.setAttribute('aria-label', language === 'en' ? button.dataset.labelEn : button.dataset.labelDe);
    });
    document.querySelectorAll('[data-mobile-player-close]').forEach((button) => {
      const label = language === 'en' ? button.dataset.labelEn : button.dataset.labelDe;
      button.setAttribute('aria-label', label || copy[language].close_player);
      button.title = label || copy[language].close_player;
    });
    const selectedMix = document.querySelector('.mix-item[aria-pressed="true"]');
    const playerSubtitle = document.querySelector('[data-player-subtitle]');
    if (selectedMix && playerSubtitle) {
      playerSubtitle.textContent = language === 'en' ? selectedMix.dataset.subtitleEn : selectedMix.dataset.subtitleDe;
    }

    if (persist) safeStorage.set('sofea-language', language);
    document.dispatchEvent(new CustomEvent('sofea:language', { detail: { language } }));
  }

  document.querySelectorAll('[data-language]').forEach((button) => {
    button.addEventListener('click', () => applyLanguage(button.dataset.language));
  });
  applyLanguage(language, false);

  const themeToggle = document.querySelector('[data-theme-toggle]');
  const themeIcon = document.querySelector('[data-theme-icon]');

  function applyTheme(nextTheme, persist = true) {
    const theme = nextTheme === 'light' ? 'light' : 'dark';
    root.dataset.theme = theme;
    if (themeIcon) themeIcon.textContent = theme === 'dark' ? '☀' : '☾';
    if (themeToggle) {
      const label = theme === 'dark'
        ? (language === 'en' ? 'Enable light theme' : 'Helles Thema aktivieren')
        : (language === 'en' ? 'Enable dark theme' : 'Dunkles Thema aktivieren');
      themeToggle.setAttribute('aria-label', label);
      themeToggle.title = label;
    }
    if (persist) safeStorage.set('sofea-theme', theme);
  }

  applyTheme(root.dataset.theme || safeStorage.get('sofea-theme') || 'dark', false);
  themeToggle?.addEventListener('click', () => {
    applyTheme(root.dataset.theme === 'dark' ? 'light' : 'dark');
  });
  document.addEventListener('sofea:language', () => applyTheme(root.dataset.theme, false));

  document.querySelectorAll('a[href^="http://"], a[href^="https://"]').forEach((link) => {
    let url;
    try { url = new URL(link.href, location.href); } catch (_) { return; }
    if (url.origin !== location.origin) {
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
  });

  const mixButtons = [...document.querySelectorAll('.mix-item')];
  const playerPanel = document.querySelector('[data-player-panel]');
  const playerTitle = document.querySelector('[data-player-title]');
  const playerSubtitle = document.querySelector('[data-player-subtitle]');
  const playerLink = document.querySelector('[data-player-link]');
  const playerFrame = document.querySelector('[data-player-frame]');
  const mobilePlayerDialog = document.querySelector('[data-mobile-player-dialog]');
  const mobilePlayerSlot = document.querySelector('[data-mobile-player-slot]');
  const mobilePlayerClose = document.querySelector('[data-mobile-player-close]');
  const mobilePlayerMedia = window.matchMedia('(max-width: 720px)');
  const playerHomeMarker = playerPanel ? document.createComment('sofea-player-home') : null;
  const soundcloudFacadeTemplate = playerFrame?.querySelector('[data-soundcloud-facade]')?.cloneNode(true) || null;
  const mobilePlayerHash = '#listen-player';
  let soundcloudAllowed = false;
  let resetPlayerOnDialogClose = true;

  if (playerPanel && playerHomeMarker) {
    playerPanel.parentNode?.insertBefore(playerHomeMarker, playerPanel);
  }

  function selectedMix() {
    return mixButtons.find((button) => button.getAttribute('aria-pressed') === 'true') || mixButtons[0] || null;
  }

  function currentSoundCloudLoadButton() {
    return playerFrame?.querySelector('[data-soundcloud-load]') || null;
  }

  function updateSoundCloudButtonLabel(button = selectedMix()) {
    const loadButton = currentSoundCloudLoadButton();
    if (!loadButton || !button) return;
    const title = button.dataset.title || 'SoundCloud';
    const prefix = language === 'en' ? 'Load SoundCloud player for' : 'SoundCloud-Player laden für';
    loadButton.setAttribute('aria-label', `${prefix} ${title}`);
    const label = loadButton.querySelector('[data-i18n="load_soundcloud"]');
    if (label) label.textContent = copy[language].load_soundcloud;
  }

  function mountSoundCloudPlayer(button = selectedMix()) {
    if (!playerFrame || !button?.dataset.embed) return;
    const iframe = document.createElement('iframe');
    iframe.src = button.dataset.embed;
    iframe.title = language === 'en'
      ? `${button.dataset.title || 'Recording'} on SoundCloud`
      : `${button.dataset.title || 'Aufnahme'} auf SoundCloud`;
    iframe.allow = 'autoplay';
    iframe.loading = 'eager';
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    iframe.dataset.soundcloudPlayer = '';
    playerFrame.replaceChildren(iframe);
    playerFrame.classList.add('is-loaded');
  }

  function restoreSoundCloudFacade() {
    soundcloudAllowed = false;
    if (!playerFrame || !soundcloudFacadeTemplate) return;
    playerFrame.replaceChildren(soundcloudFacadeTemplate.cloneNode(true));
    playerFrame.classList.remove('is-loaded');
    updateSoundCloudButtonLabel();
  }

  function selectMix(button) {
    mixButtons.forEach((candidate) => candidate.setAttribute('aria-pressed', String(candidate === button)));
    if (playerTitle) playerTitle.textContent = button.dataset.title || '';
    if (playerSubtitle) {
      playerSubtitle.textContent = language === 'en' ? button.dataset.subtitleEn : button.dataset.subtitleDe;
    }
    if (playerLink) playerLink.href = button.dataset.url || '#';
    if (playerFrame) {
      playerFrame.dataset.embed = button.dataset.embed || '';
      playerFrame.dataset.playerName = button.dataset.title || '';
    }
    updateSoundCloudButtonLabel(button);
    if (soundcloudAllowed) mountSoundCloudPlayer(button);
  }

  function movePlayerPanelForViewport() {
    if (!playerPanel || !playerHomeMarker) return;
    if (mobilePlayerMedia.matches && mobilePlayerSlot) {
      if (playerPanel.parentNode !== mobilePlayerSlot) mobilePlayerSlot.append(playerPanel);
      return;
    }
    if (playerHomeMarker.parentNode && playerPanel.previousSibling !== playerHomeMarker) {
      playerHomeMarker.parentNode.insertBefore(playerPanel, playerHomeMarker.nextSibling);
    }
  }

  function openMobilePlayer({ updateHistory = true } = {}) {
    if (!mobilePlayerMedia.matches || !mobilePlayerDialog || !playerPanel) return;
    movePlayerPanelForViewport();
    if (!mobilePlayerDialog.open) mobilePlayerDialog.showModal();
    body.classList.add('mobile-player-open');
    if (updateHistory && location.hash !== mobilePlayerHash) {
      history.pushState({ sofeaMobilePlayer: true }, '', mobilePlayerHash);
    }
    requestAnimationFrame(() => mobilePlayerClose?.focus({ preventScroll: true }));
  }

  function closeMobilePlayer({ updateHistory = true, resetPlayer = true } = {}) {
    if (!mobilePlayerDialog?.open) return;
    if (updateHistory && location.hash === mobilePlayerHash) {
      if (history.state?.sofeaMobilePlayer) {
        history.back();
        return;
      }
      history.replaceState(null, '', `${location.pathname}${location.search}#listen`);
    }
    resetPlayerOnDialogClose = resetPlayer;
    mobilePlayerDialog.close();
  }

  function syncMobilePlayerFromLocation() {
    if (location.hash === mobilePlayerHash && mobilePlayerMedia.matches) {
      openMobilePlayer({ updateHistory: false });
      return;
    }
    if (mobilePlayerDialog?.open) closeMobilePlayer({ updateHistory: false });
  }

  playerFrame?.addEventListener('click', (event) => {
    if (!event.target.closest('[data-soundcloud-load]')) return;
    soundcloudAllowed = true;
    mountSoundCloudPlayer();
  });

  mixButtons.forEach((button) => button.addEventListener('click', () => {
    selectMix(button);
    if (mobilePlayerMedia.matches) openMobilePlayer();
  }));

  mobilePlayerClose?.addEventListener('click', () => closeMobilePlayer());
  mobilePlayerDialog?.addEventListener('cancel', (event) => {
    event.preventDefault();
    closeMobilePlayer();
  });
  mobilePlayerDialog?.addEventListener('click', (event) => {
    if (event.target === mobilePlayerDialog) closeMobilePlayer();
  });
  mobilePlayerDialog?.addEventListener('close', () => {
    body.classList.remove('mobile-player-open');
    if (resetPlayerOnDialogClose) restoreSoundCloudFacade();
    resetPlayerOnDialogClose = true;
    selectedMix()?.focus({ preventScroll: true });
  });

  const handleMobilePlayerViewportChange = () => {
    if (!mobilePlayerMedia.matches && mobilePlayerDialog?.open) {
      if (location.hash === mobilePlayerHash) {
        history.replaceState(null, '', `${location.pathname}${location.search}#listen`);
      }
      closeMobilePlayer({ updateHistory: false, resetPlayer: false });
    }
    movePlayerPanelForViewport();
  };
  mobilePlayerMedia.addEventListener?.('change', handleMobilePlayerViewportChange);
  window.addEventListener('hashchange', syncMobilePlayerFromLocation);
  window.addEventListener('popstate', syncMobilePlayerFromLocation);

  movePlayerPanelForViewport();
  syncMobilePlayerFromLocation();
  updateSoundCloudButtonLabel();

  document.addEventListener('sofea:language', () => {
    updateSoundCloudButtonLabel();
    const iframe = playerFrame?.querySelector('[data-soundcloud-player]');
    const button = selectedMix();
    if (iframe && button) {
      iframe.title = language === 'en'
        ? `${button.dataset.title || 'Recording'} on SoundCloud`
        : `${button.dataset.title || 'Aufnahme'} auf SoundCloud`;
    }
  });

  const episodeList = document.querySelector('[data-episode-list]');
  const allEpisodes = episodeList ? [...episodeList.querySelectorAll('[data-episode]')] : [];
  const searchInput = document.querySelector('[data-archive-search]');
  const emptyState = document.querySelector('[data-archive-empty]');
  const pagination = document.querySelector('[data-archive-pagination]');
  const pageNumbers = document.querySelector('[data-page-numbers]');
  const previousPage = document.querySelector('[data-page-prev]');
  const nextPage = document.querySelector('[data-page-next]');
  const pageSize = 10;
  let currentPage = 1;
  let filteredEpisodes = allEpisodes;

  const normalize = (value) => value
    .toLocaleLowerCase('de-DE')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

  function renderArchive() {
    if (!episodeList) return;
    const pageCount = Math.max(1, Math.ceil(filteredEpisodes.length / pageSize));
    currentPage = Math.min(Math.max(currentPage, 1), pageCount);
    const start = (currentPage - 1) * pageSize;
    const visible = new Set(filteredEpisodes.slice(start, start + pageSize));

    allEpisodes.forEach((episode) => { episode.hidden = !visible.has(episode); });
    if (emptyState) emptyState.hidden = filteredEpisodes.length !== 0;
    if (pagination) pagination.hidden = filteredEpisodes.length <= pageSize;
    if (previousPage) previousPage.disabled = currentPage === 1;
    if (nextPage) nextPage.disabled = currentPage === pageCount;

    if (pageNumbers) {
      pageNumbers.replaceChildren();
      for (let page = 1; page <= pageCount; page += 1) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'pagination-number';
        button.textContent = String(page);
        button.setAttribute('aria-label', language === 'en' ? `Page ${page}` : `Seite ${page}`);
        if (page === currentPage) button.setAttribute('aria-current', 'page');
        button.addEventListener('click', () => {
          currentPage = page;
          renderArchive();
          episodeList.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
        pageNumbers.append(button);
      }
    }
  }

  function applyArchiveSearch() {
    const query = normalize(searchInput?.value.trim() || '');
    filteredEpisodes = allEpisodes.filter((episode) => normalize(episode.dataset.search || '').includes(query));
    currentPage = 1;
    renderArchive();
  }

  searchInput?.addEventListener('input', applyArchiveSearch);
  previousPage?.addEventListener('click', () => {
    if (currentPage > 1) { currentPage -= 1; renderArchive(); }
  });
  nextPage?.addEventListener('click', () => {
    if (currentPage < Math.ceil(filteredEpisodes.length / pageSize)) { currentPage += 1; renderArchive(); }
  });
  document.addEventListener('sofea:language', renderArchive);
  renderArchive();

  function revealEpisode(detailId) {
    const row = allEpisodes.find((episode) => episode.dataset.detailId === detailId);
    if (!row) return;
    if (!filteredEpisodes.includes(row)) {
      if (searchInput) searchInput.value = '';
      filteredEpisodes = allEpisodes;
    }
    currentPage = Math.floor(filteredEpisodes.indexOf(row) / pageSize) + 1;
    renderArchive();
  }

  const dialogs = [...document.querySelectorAll('[data-detail-dialog]')];
  let lastDetailTrigger = null;
  const homeUrl = body?.dataset.homeUrl || '/';
  const homeTitle = body?.dataset.homeTitle || document.title;

  function dialogForId(id) {
    return id ? document.getElementById(id) : null;
  }

  function hideDialog(dialog, restoreFocus = false) {
    if (!dialog?.open) return;
    dialog.close();
    body.classList.remove('detail-open');
    document.title = homeTitle;
    if (restoreFocus && lastDetailTrigger instanceof HTMLElement) lastDetailTrigger.focus();
  }

  function hideAllDialogs(restoreFocus = false) {
    dialogs.forEach((dialog) => hideDialog(dialog, restoreFocus));
  }

  function showDialog(dialog, trigger = null) {
    if (!(dialog instanceof HTMLDialogElement)) return;
    dialogs.forEach((candidate) => {
      if (candidate !== dialog && candidate.open) candidate.close();
    });
    if (trigger instanceof HTMLElement) lastDetailTrigger = trigger;
    revealEpisode(dialog.id);
    if (!dialog.open) dialog.showModal();
    body.classList.add('detail-open');
    document.title = dialog.dataset.pageTitle || homeTitle;
  }

  function openDetailFromLink(link) {
    const id = link.dataset.detailId;
    const dialog = dialogForId(id);
    if (!(dialog instanceof HTMLDialogElement)) return false;
    showDialog(dialog, link);
    history.pushState({ sofeaDetail: id }, '', link.href);
    return true;
  }

  document.querySelectorAll('[data-detail-link]').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (openDetailFromLink(link)) event.preventDefault();
    });
  });

  function requestDialogClose(dialog) {
    if (history.state?.sofeaDetail === dialog.id) {
      history.back();
    } else {
      hideDialog(dialog, true);
      history.replaceState(null, '', homeUrl);
    }
  }

  dialogs.forEach((dialog) => {
    dialog.querySelector('[data-detail-close]')?.addEventListener('click', () => requestDialogClose(dialog));
    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      requestDialogClose(dialog);
    });
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) requestDialogClose(dialog);
    });
  });

  addEventListener('popstate', (event) => {
    const id = event.state?.sofeaDetail;
    const dialog = dialogForId(id);
    if (dialog instanceof HTMLDialogElement) {
      showDialog(dialog);
    } else {
      hideAllDialogs(true);
      document.title = homeTitle;
    }
  });

  const sectionLinks = [...document.querySelectorAll('[data-section-link]')];
  const observedSections = sectionLinks
    .map((link) => {
      try { return document.querySelector(new URL(link.href, location.href).hash); } catch (_) { return null; }
    })
    .filter(Boolean);

  const mobileSectionNavigation = window.matchMedia('(max-width: 900px)');

  function clearActiveSections() {
    sectionLinks.forEach((link) => {
      link.classList.remove('is-active');
      link.removeAttribute('aria-current');
    });
  }

  function setActiveSection(id) {
    if (!mobileSectionNavigation.matches) {
      clearActiveSections();
      return;
    }
    sectionLinks.forEach((link) => {
      let active = false;
      try { active = new URL(link.href, location.href).hash === `#${id}`; } catch (_) {}
      link.classList.toggle('is-active', active);
      if (active) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }

  mobileSectionNavigation.addEventListener?.('change', (event) => {
    if (!event.matches) clearActiveSections();
  });

  if ('IntersectionObserver' in window && observedSections.length) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible?.target.id) setActiveSection(visible.target.id);
    }, { rootMargin: '-25% 0px -60% 0px', threshold: [0.01, 0.2, 0.5] });
    observedSections.forEach((section) => observer.observe(section));
  }

  const backToTop = document.querySelector('[data-back-to-top]');
  function updateBackToTop() {
    if (!backToTop) return;
    const visible = scrollY > Math.max(500, innerHeight * 0.8);
    backToTop.classList.toggle('is-visible', visible);
    backToTop.setAttribute('aria-hidden', String(!visible));
    backToTop.tabIndex = visible ? 0 : -1;
  }
  backToTop?.addEventListener('click', () => scrollTo({ top: 0, behavior: 'smooth' }));
  addEventListener('scroll', updateBackToTop, { passive: true });
  updateBackToTop();

  document.querySelectorAll('[data-current-year]').forEach((element) => {
    element.textContent = String(new Date().getFullYear());
  });
})();
