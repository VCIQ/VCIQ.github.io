(() => {
  if (window.__vciqPeopleDirectoryFilterInstalled) return;
  window.__vciqPeopleDirectoryFilterInstalled = true;

  const normalize = (value) => String(value || "").trim().replace(/\s+/g, " ").toLocaleLowerCase("zh-CN");

  function initialize() {
    const controls = document.querySelector("[data-pf]:not([data-ready])");
    const grid = document.getElementById("people-research-directory");
    if (!(controls instanceof HTMLElement) || !(grid instanceof HTMLElement)) return;

    const query = controls.querySelector("[data-q]");
    const sector = controls.querySelector("[data-sector]");
    const status = controls.querySelector("[data-status]");
    const change = controls.querySelector("[data-change]");
    const count = controls.querySelector("[data-count]");
    const reset = controls.querySelector("[data-reset]");
    const empty = document.querySelector("[data-people-empty]");
    if (!(query instanceof HTMLInputElement)
      || !(sector instanceof HTMLSelectElement)
      || !(status instanceof HTMLSelectElement)
      || !(change instanceof HTMLSelectElement)
      || !(count instanceof HTMLElement)
      || !(reset instanceof HTMLButtonElement)
      || !(empty instanceof HTMLElement)) return;

    controls.dataset.ready = "1";
    const cards = Array.from(grid.children).filter((item) => item instanceof HTMLElement);
    const total = cards.length;

    function apply() {
      const needle = normalize(query.value);
      const sectorToken = sector.value;
      const statusToken = status.value;
      const changeToken = change.value;
      let visible = 0;

      for (const card of cards) {
        const recent = card.classList.contains("tr");
        const matches = (!needle || normalize(card.textContent).includes(needle))
          && (!sectorToken || card.classList.contains(sectorToken))
          && (!statusToken || card.classList.contains(statusToken))
          && (!changeToken || (changeToken === "r" ? recent : !recent));
        card.hidden = !matches;
        if (matches) visible += 1;
      }

      count.textContent = `${visible} / ${total}`;
      empty.hidden = visible !== 0;
      reset.disabled = !(needle || sectorToken || statusToken || changeToken);
    }

    query.addEventListener("input", apply);
    sector.addEventListener("change", apply);
    status.addEventListener("change", apply);
    change.addEventListener("change", apply);
    reset.addEventListener("click", () => {
      query.value = "";
      sector.value = "";
      status.value = "";
      change.value = "";
      apply();
      query.focus();
    });
    apply();
  }

  initialize();
  new MutationObserver(initialize).observe(document.documentElement, { childList: true, subtree: true });
})();
