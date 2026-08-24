const API = "/api";

const els = {
  searchForm: document.getElementById("search-form"),
  searchInput: document.getElementById("search-input"),
  results: document.getElementById("results"),
  emptyState: document.getElementById("empty-state"),
  loadingState: document.getElementById("loading-state"),
  tagList: document.getElementById("tag-list"),
  modal: document.getElementById("modal"),
  modalClose: document.getElementById("modal-close"),
  modalVideo: document.getElementById("modal-video"),
  modalFile: document.getElementById("modal-file"),
  downloadLink: document.getElementById("download-link"),
  currentTags: document.getElementById("current-tags"),
  tagSuggestions: document.getElementById("tag-suggestions"),
  tagForm: document.getElementById("tag-form"),
  tagInput: document.getElementById("tag-input"),
  navPrev: document.getElementById("nav-prev"),
  navNext: document.getElementById("nav-next"),
  videoCounter: document.getElementById("video-counter"),
  similarRow: document.getElementById("similar-row"),
};

let activeTags = new Set();
let currentVideoId = null;
let currentResults = [];
let currentIndex = -1;

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

async function runSearch() {
  els.loadingState.hidden = false;
  els.emptyState.hidden = true;
  els.results.innerHTML = "";

  const q = els.searchInput.value.trim();
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("limit", "2000");
  if (activeTags.size) params.set("tags", [...activeTags].join(","));

  try {
    const res = await fetch(`${API}/search?${params.toString()}`);
    const data = await res.json();
    els.loadingState.hidden = true;

    if (!data.results.length) {
      els.emptyState.hidden = false;
      return;
    }
    renderResults(data.results);
  } catch (err) {
    els.loadingState.hidden = true;
    els.emptyState.hidden = false;
    els.emptyState.textContent = "Erro ao buscar. Verifique se o backend está no ar.";
  }
}

async function loadTopTags() {
  try {
    const res = await fetch(`${API}/tags/top`);
    const data = await res.json();
    renderTagSidebar(data.tags);
  } catch (err) {
    // silencioso: a barra lateral só não aparece, o resto do app continua ok
  }
}

function renderTagSidebar(tags) {
  els.tagList.innerHTML = "";
  if (!tags.length) {
    els.tagList.innerHTML = `<div class="tag-empty">Nenhuma tag criada ainda</div>`;
    return;
  }
  tags.forEach(({ tag, count }) => {
    const row = document.createElement("div");
    row.className = "tag-row" + (activeTags.has(tag) ? " active" : "");
    row.innerHTML = `<span>${tag}</span><span class="count">${count}</span>`;
    row.addEventListener("click", () => {
      activeTags.has(tag) ? activeTags.delete(tag) : activeTags.add(tag);
      runSearch();
      loadTopTags();
    });
    els.tagList.appendChild(row);
  });
}

function renderResults(results) {
  currentResults = results;
  els.results.innerHTML = "";

  for (const video of results) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <button class="card-rename" title="Renomear vídeo">✏️</button>
      <button class="card-delete" title="Deletar vídeo">🗑</button>
      <img src="${API}/thumbnail/${video.video_id}" loading="lazy">
      <div class="card-meta">
        <div class="card-filename">${video.filename}</div>
        <div class="card-time">${formatTime(video.duration)}</div>
        <div class="card-tags">${video.tags.map(t => `<span>${t}</span>`).join("")}</div>
      </div>`;
    card.querySelector(".card-rename").addEventListener("click", async (e) => {
      e.stopPropagation();
      const novo = prompt("Novo nome para o vídeo:", video.filename);
      if (novo === null || novo.trim() === "" || novo.trim() === video.filename) return;
      try {
        const res = await fetch(`${API}/admin/rename/${video.video_id}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: novo.trim() })
        });
        if (res.ok) {
          video.filename = novo.trim();
          const idx = currentResults.findIndex(v => v.video_id === video.video_id);
          if (idx >= 0) currentResults[idx].filename = novo.trim();
          card.querySelector(".card-filename").textContent = novo.trim();
        } else {
          alert("Erro ao renomear. Tente de novo.");
        }
      } catch (err) { alert("Erro ao renomear: " + err.message); }
    });
    card.querySelector(".card-delete").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(`Deletar "${video.filename}"? Esta ação não pode ser desfeita.`)) return;
      try {
        const res = await fetch(`${API}/admin/delete/${video.video_id}`, { method: "DELETE" });
        if (res.ok) {
          currentResults = currentResults.filter(v => v.video_id !== video.video_id);
          card.remove();
          loadStats();
        } else {
          alert("Erro ao deletar. Tente de novo.");
        }
      } catch (err) { alert("Erro ao deletar: " + err.message); }
    });
    card.addEventListener("click", () => openModal(video));
    els.results.appendChild(card);
  }
}

async function openModal(video) {
  currentVideoId = video.video_id;
  currentIndex = currentResults.findIndex(v => v.video_id === video.video_id);
  els.modal.hidden = false;
  els.modalFile.textContent = `${video.filename} (${formatTime(video.duration)})`;
  document.getElementById("video-error").hidden = true;
  const videoUrl = `${API}/video/${video.video_id}`;
  els.modalVideo.hidden = false;
  els.modalVideo.src = videoUrl;
  els.downloadLink.href = `${API}/download/${video.video_id}`;
  document.getElementById("video-direct-link").href = videoUrl;
  els.modalVideo.addEventListener("error", () => {
    els.modalVideo.hidden = true;
    document.getElementById("video-error").hidden = false;
  }, { once: true });
  renderTags(video.tags);
  updateNavButtons();
  loadSimilar(video.video_id);
  loadTagSuggestions(video.video_id);

  // autoplay: navegadores às vezes bloqueiam autoplay com som, então se
  // falhar tentamos de novo mudo (silenciado) — melhor que não tocar nada
  els.modalVideo.play().catch(() => {
    els.modalVideo.muted = true;
    els.modalVideo.play().catch(() => {});
  });
}

function updateNavButtons() {
  els.navPrev.disabled = currentIndex <= 0;
  els.navNext.disabled = currentIndex === -1 || currentIndex >= currentResults.length - 1;
}

function goToVideo(offset) {
  if (currentIndex === -1) return;
  const next = currentIndex + offset;
  if (next < 0 || next >= currentResults.length) return;
  openModal(currentResults[next]);
}

async function loadSimilar(videoId) {
  els.similarRow.innerHTML = `<div class="similar-empty">Buscando…</div>`;
  try {
    const res = await fetch(`${API}/similar/${videoId}`);
    const data = await res.json();
    if (!data.results.length) {
      els.similarRow.innerHTML = `<div class="similar-empty">Nenhum vídeo parecido encontrado ainda.</div>`;
      return;
    }
    els.similarRow.innerHTML = "";
    data.results.forEach(video => {
      const card = document.createElement("div");
      card.className = "similar-card";
      card.innerHTML = `
        <img src="${API}/thumbnail/${video.video_id}" loading="lazy">
        <div class="similar-name">${video.filename}</div>`;
      card.addEventListener("click", () => openModal(video));
      els.similarRow.appendChild(card);
    });
  } catch (err) {
    els.similarRow.innerHTML = `<div class="similar-empty">Não foi possível carregar sugestões agora.</div>`;
  }
}

function closeModal() {
  els.modal.hidden = true;
  els.modalVideo.pause();
  els.modalVideo.src = "";
}

async function loadTagSuggestions(videoId) {
  els.tagSuggestions.innerHTML = "";
  try {
    const res = await fetch(`${API}/suggest-tags/${videoId}`);
    const data = await res.json();
    renderTagSuggestions(data.suggestions);
  } catch (err) {
    // silencioso: sem sugestões, sem problema, o resto do editor continua ok
  }
}

function renderTagSuggestions(suggestions) {
  els.tagSuggestions.innerHTML = "";
  suggestions.forEach(({ tag, score }) => {
    const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "suggestion-chip";
    chip.innerHTML = `+ ${tag} <span class="pct">${pct}%</span>`;
    chip.addEventListener("click", async () => {
      await fetch(`${API}/tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_id: currentVideoId, tag }),
      });
      const current = [...els.currentTags.querySelectorAll("span")].map(s => s.firstChild.textContent.trim());
      renderTags([...current, tag]);
      if (currentResults[currentIndex]) { currentResults[currentIndex].tags = [...current, tag]; renderResults(currentResults); }
      loadTopTags();
      loadTagSuggestions(currentVideoId);
    });
    els.tagSuggestions.appendChild(chip);
  });
}

function renderTags(tags) {
  els.currentTags.innerHTML = tags.map(t => `
    <span>${t} <button data-tag="${t}">✕</button></span>
  `).join("");
  els.currentTags.querySelectorAll("button").forEach(btn => {
    btn.addEventListener("click", async () => {
      await fetch(`${API}/tags`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_id: currentVideoId, tag: btn.dataset.tag }),
      });
      renderTags(tags.filter(t => t !== btn.dataset.tag));
        if (currentResults[currentIndex]) { currentResults[currentIndex].tags = tags.filter(t => t !== btn.dataset.tag); renderResults(currentResults); }
      loadTopTags();
      loadTagSuggestions(currentVideoId);
    });
  });
}

els.searchForm.addEventListener("submit", (e) => { e.preventDefault(); runSearch(); });

els.modalClose.addEventListener("click", closeModal);

els.modal.addEventListener("click", (e) => {
  if (e.target === els.modal) closeModal();
});

document.addEventListener("keydown", (e) => {
  if (els.modal.hidden) return;
  if (e.key === "Escape") closeModal();
  if (e.key === "ArrowLeft") goToVideo(-1);
  if (e.key === "ArrowRight") goToVideo(1);
});

els.navPrev.addEventListener("click", () => goToVideo(-1));
els.navNext.addEventListener("click", () => goToVideo(1));

els.tagForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const tag = els.tagInput.value.trim().toLowerCase();
  if (!tag || !currentVideoId) return;
  await fetch(`${API}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_id: currentVideoId, tag }),
  });
  els.tagInput.value = "";
  const current = [...els.currentTags.querySelectorAll("span")].map(s => s.firstChild.textContent.trim());
  renderTags([...current, tag]);
      if (currentResults[currentIndex]) { currentResults[currentIndex].tags = [...current, tag]; renderResults(currentResults); }
  loadTopTags();
  loadTagSuggestions(currentVideoId);
});

async function loadStats() {
  try {
    const res = await fetch(`${API}/stats`);
    const data = await res.json();
    els.videoCounter.textContent = `${data.total_videos} vídeos no acervo`;
  } catch (e) {
    els.videoCounter.textContent = "";
  }
}

// carrega os mais recentes ao abrir a página
runSearch();
loadTopTags();
loadStats();
