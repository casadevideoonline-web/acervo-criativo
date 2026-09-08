// admin.js — logica da tela de gerenciamento do acervo.
let adminPassword = null;
let allVideos = [];

function askPassword() {
  const pw = window.prompt("Digite a senha de administrador:");
  if (pw === null) return false;
  adminPassword = pw;
  return true;
}

function toast(msg) {
  const el = document.getElementById("admin-toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(function () { el.classList.remove("show"); }, 2500);
}

function adminHeaders(extra) {
  const h = extra || {};
  h["X-Admin-Password"] = adminPassword || "";
  return h;
}

async function loadVideos() {
  const res = await fetch("/api/search?q=&limit=100000");
  if (!res.ok) {
    document.getElementById("admin-list").innerHTML =
      '<div class="admin-empty">Nao foi possivel carregar a lista. Faca login no acervo primeiro e recarregue.</div>';
    return;
  }
  const data = await res.json();
  allVideos = data.results || [];
  render();
}

function render() {
  const term = document.getElementById("admin-search").value.trim().toLowerCase();
  const list = document.getElementById("admin-list");
  const filtered = term ? allVideos.filter(function (v) { return (v.filename || "").toLowerCase().includes(term); }) : allVideos;
  document.getElementById("admin-count").textContent = filtered.length + " video(s)" + (term ? " (de " + allVideos.length + ")" : "");
  if (filtered.length === 0) {
    list.innerHTML = '<div class="admin-empty">Nenhum video encontrado.</div>';
    return;
  }
  list.innerHTML = "";
  for (const v of filtered) {
    const row = document.createElement("div");
    row.className = "admin-row";
    const img = document.createElement("img");
    img.src = "/api/thumbnail/" + v.video_id;
    img.loading = "lazy";
    img.alt = "";
    const name = document.createElement("div");
    name.className = "admin-row-name";
    name.textContent = v.filename || "(sem nome)";
    const actions = document.createElement("div");
    actions.className = "admin-row-actions";
    const btnRename = document.createElement("button");
    btnRename.className = "admin-btn admin-btn-rename";
    btnRename.textContent = "Renomear";
    btnRename.onclick = function () { renameVideo(v); };
    const btnDelete = document.createElement("button");
    btnDelete.className = "admin-btn admin-btn-delete";
    btnDelete.textContent = "Excluir";
    btnDelete.onclick = function () { deleteVideo(v); };
    actions.appendChild(btnRename);
    actions.appendChild(btnDelete);
    row.appendChild(img);
    row.appendChild(name);
    row.appendChild(actions);
    list.appendChild(row);
  }
}async function renameVideo(v) {
  if (!adminPassword && !askPassword()) return;
  const novo = window.prompt("Novo nome para o video:", v.filename || "");
  if (novo === null) return;
  const nome = novo.trim();
  if (!nome) { toast("O nome nao pode ficar vazio."); return; }
  if (nome === v.filename) return;
  const res = await fetch("/api/admin/rename/" + v.video_id, {
    method: "POST",
    headers: adminHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ filename: nome })
  });
  if (res.status === 401) { adminPassword = null; toast("Senha de admin incorreta."); return; }
  if (!res.ok) { toast("Erro ao renomear."); return; }
  v.filename = nome;
  render();
  toast("Nome atualizado.");
}

async function deleteVideo(v) {
  if (!adminPassword && !askPassword()) return;
  const nome = v.filename || "(sem nome)";
  const ok = window.confirm("Tem certeza que deseja EXCLUIR este video?\n\n" + nome + "\n\nIsso apaga o arquivo permanentemente e NAO pode ser desfeito.");
  if (!ok) return;
  const res = await fetch("/api/admin/delete/" + v.video_id, {
    method: "DELETE",
    headers: adminHeaders({})
  });
  if (res.status === 401) { adminPassword = null; toast("Senha de admin incorreta."); return; }
  if (!res.ok) { toast("Erro ao excluir."); return; }
  allVideos = allVideos.filter(function (x) { return x.video_id !== v.video_id; });
  render();
  toast("Video excluido.");
}

document.getElementById("admin-search").addEventListener("input", render);
loadVideos();

