(() => {
  const search = document.querySelector('[data-archive-search]');
  const episodes = [...document.querySelectorAll('[data-episode]')];

  if (search) {
    search.addEventListener('input', () => {
      const query = search.value.trim().toLocaleLowerCase();
      for (const episode of episodes) {
        episode.hidden = query !== '' && !episode.textContent.toLocaleLowerCase().includes(query);
      }
    });
  }

  const year = document.querySelector('[data-current-year]');
  if (year) year.textContent = String(new Date().getFullYear());
})();
