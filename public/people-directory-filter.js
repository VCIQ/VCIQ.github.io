(() => {
  if (window.__vciqPeopleDirectoryFilterInstalled) return;
  window.__vciqPeopleDirectoryFilterInstalled = true;

  const normalize = (value) => value.trim().replace(/\s+/g, " ").toLocaleLowerCase("zh-CN");

  function initialize() {
    const controls = document.querySelector("[data-pf]:not([data-ready])");
    const grid = document.getElementById("people-research-directory");
    if (!(controls instanceof HTMLElement) || !(grid instanceof HTMLElement)) return;

    const query = controls.querySelector("[data-q]");
    const sector = controls.querySelector("[data-sel]");
    const status = controls.querySelector("[data-st]");
    const change = controls.querySelector("[data-ch]");
    const count = controls.querySelector("[data-count]");
    const reset = controls.querySelector("[data-reset]");
    const empty = controls.querySelector("[data-empty]");

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
      const sectorValue = sector.value;
      const statusValue = status.value;
      const changeValue = change.value;
      let visible = 0;

      for (const card of cards) {
        const sectors = (card.dataset.s || "").split(".").filter(Boolean);
        const recent = card.hasAttribute("data-r");
        const matches = (!needle || normalize(card.textContent || "").includes(needle))
          && (!sectorValue || sectors.includes(sectorValue))
          && (!statusValue || card.dataset.t === statusValue)
          && (!changeValue || (changeValue === "r" ? recent : !recent));
        card.hidden = !matches;
        if (matches) visible += 1;
      }

      count.textContent = `显示 ${visible} / ${total} 位人物`;
      empty.hidden = visible !== 0;
      reset.disabled = !(needle || sectorValue || statusValue || changeValue);
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
