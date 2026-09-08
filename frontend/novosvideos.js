// novosvideos.js — logica da tela de upload em lote de videos.
// Fluxo: usuario escolhe/arrasta os arquivos -> fila com previa do nome
// tratado -> envio sequencial (um por vez) com barra de progresso ->
// backend sobe ao bucket, processa (thumbnail + CLIP + banco) e responde.

let senha_de_admin = null;
let fila_de_arquivos = [];   // { arquivo, elemento, status }
let envio_em_andamento = false;

const EXTENSOES_ACEITAS = [".mp4", ".mov", ".avi", ".mkv", ".webm"];

const zona_de_soltar = document.getElementById("zona-de-soltar");
const seletor_de_arquivos = document.getElementById("seletor-de-arquivos");
const fila_de_envio = document.getElementById("fila-de-envio");
const botao_enviar = document.getElementById("botao-enviar");
const botao_limpar = document.getElementById("botao-limpar");
const resumo_final = document.getElementById("resumo-final");

function toast(mensagem) {
  const elemento = document.getElementById("upload-toast");
  elemento.textContent = mensagem;
  elemento.classList.add("show");
  setTimeout(function () { elemento.classList.remove("show"); }, 3000);
}

function pedir_senha() {
  if (senha_de_admin) return true;
  const senha = window.prompt("Digite a senha de administrador:");
  if (senha === null || senha === "") return false;
  senha_de_admin = senha;
  return true;
}

// Previa do nome tratado — espelha as regras do backend (nomes.py).
// A versao final e sempre a do servidor (que tambem resolve colisoes).
function previa_nome_tratado(nome_original) {
  const ponto = nome_original.lastIndexOf(".");
  let raiz = ponto > 0 ? nome_original.slice(0, ponto) : nome_original;
  let extensao = ponto > 0 ? nome_original.slice(ponto).toLowerCase() : "";

  raiz = raiz.normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
  raiz = raiz.toLowerCase();
  raiz = raiz.replace(/[^a-z0-9_-]+/g, "_");
  raiz = raiz.replace(/_+/g, "_");
  raiz = raiz.replace(/^[_-]+|[_-]+$/g, "");
  if (!raiz) raiz = "video_sem_nome";
  return raiz + extensao;
}

function formatar_tamanho(bytes) {
  if (bytes >= 1024 * 1024 * 1024) return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return Math.round(bytes / 1024) + " KB";
}

function definir_status(item, classe, texto) {
  item.status = classe;
  const chip = item.elemento.querySelector(".fila-status");
  chip.className = "fila-status status-" + classe;
  chip.textContent = texto;
}

function adicionar_arquivos(lista) {
  const nomes_ja_na_fila = new Set(fila_de_arquivos.map(function (i) { return i.arquivo.name; }));
  let recusados = 0;

  Array.prototype.forEach.call(lista, function (arquivo) {
    const extensao = arquivo.name.slice(arquivo.name.lastIndexOf(".")).toLowerCase();
    if (EXTENSOES_ACEITAS.indexOf(extensao) === -1) { recusados++; return; }
    if (nomes_ja_na_fila.has(arquivo.name)) return;
    nomes_ja_na_fila.add(arquivo.name);

    const nome_tratado = previa_nome_tratado(arquivo.name);
    const elemento = document.createElement("div");
    elemento.className = "fila-item";
    elemento.innerHTML =
      '<div class="fila-nomes">' +
        '<div class="fila-nome-original"></div>' +
        '<div class="fila-nome-tratado"></div>' +
        '<div class="barra-progresso"><div class="barra-progresso-preenchida"></div></div>' +
      '</div>' +
      '<span class="fila-tamanho">' + formatar_tamanho(arquivo.size) + '</span>' +
      '<span class="fila-status status-aguardando">aguardando</span>';
    elemento.querySelector(".fila-nome-original").textContent = arquivo.name;
    const linha_tratado = elemento.querySelector(".fila-nome-tratado");
    if (nome_tratado !== arquivo.name) {
      linha_tratado.textContent = "sera salvo como: " + nome_tratado;
      linha_tratado.classList.add("diferente");
    } else {
      linha_tratado.textContent = "nome ja no padrao";
    }
    fila_de_envio.appendChild(elemento);
    fila_de_arquivos.push({ arquivo: arquivo, elemento: elemento, status: "aguardando" });
  });

  if (recusados > 0) toast(recusados + " arquivo(s) ignorado(s): formato nao aceito.");
  botao_enviar.disabled = fila_de_arquivos.length === 0 || envio_em_andamento;
}

function enviar_um_arquivo(item) {
  return new Promise(function (resolver) {
    const requisicao = new XMLHttpRequest();
    const dados = new FormData();
    dados.append("arquivo", item.arquivo);

    const barra = item.elemento.querySelector(".barra-progresso-preenchida");

    requisicao.upload.onprogress = function (evento) {
      if (!evento.lengthComputable) return;
      const percentual = Math.round((evento.loaded / evento.total) * 100);
      barra.style.width = percentual + "%";
      if (percentual >= 100) {
        // bytes entregues; agora o servidor sobe ao bucket e roda o CLIP
        definir_status(item, "processando", "processando...");
      } else {
        definir_status(item, "enviando", "enviando " + percentual + "%");
      }
    };

    requisicao.onload = function () {
      if (requisicao.status === 200) {
        let resposta = {};
        try { resposta = JSON.parse(requisicao.responseText); } catch (e) {}
        definir_status(item, "concluido", "no acervo");
        if (resposta.filename) {
          const linha = item.elemento.querySelector(".fila-nome-tratado");
          linha.textContent = "salvo como: " + resposta.filename;
        }
        resolver("concluido");
      } else if (requisicao.status === 401) {
        senha_de_admin = null;
        definir_status(item, "erro", "senha incorreta");
        resolver("senha_incorreta");
      } else if (requisicao.status === 409) {
        definir_status(item, "erro", "ja existe no acervo");
        resolver("duplicado");
      } else {
        let detalhe = "erro " + requisicao.status;
        try { detalhe = JSON.parse(requisicao.responseText).detail || detalhe; } catch (e) {}
        definir_status(item, "erro", String(detalhe).slice(0, 60));
        resolver("erro");
      }
    };

    requisicao.onerror = function () {
      definir_status(item, "erro", "falha de conexao");
      resolver("erro");
    };

    requisicao.open("POST", "/api/admin/upload");
    requisicao.setRequestHeader("X-Admin-Password", senha_de_admin || "");
    requisicao.send(dados);
  });
}

async function enviar_todos() {
  if (envio_em_andamento) return;
  if (!pedir_senha()) return;

  envio_em_andamento = true;
  botao_enviar.disabled = true;
  botao_limpar.disabled = true;
  resumo_final.textContent = "";

  let concluidos = 0, com_erro = 0;

  for (let i = 0; i < fila_de_arquivos.length; i++) {
    const item = fila_de_arquivos[i];
    if (item.status === "concluido") continue;

    definir_status(item, "enviando", "enviando 0%");
    const resultado = await enviar_um_arquivo(item);

    if (resultado === "concluido") { concluidos++; continue; }
    com_erro++;
    if (resultado === "senha_incorreta") {
      toast("Senha de admin incorreta. Envio interrompido.");
      break;
    }
  }

  envio_em_andamento = false;
  botao_enviar.disabled = false;
  botao_limpar.disabled = false;
  resumo_final.textContent =
    "Resultado: " + concluidos + " enviado(s) com sucesso, " + com_erro + " com problema.";
  toast("Lote finalizado.");
}

zona_de_soltar.addEventListener("click", function () { seletor_de_arquivos.click(); });
seletor_de_arquivos.addEventListener("change", function () {
  adicionar_arquivos(seletor_de_arquivos.files);
  seletor_de_arquivos.value = "";
});
zona_de_soltar.addEventListener("dragover", function (evento) {
  evento.preventDefault();
  zona_de_soltar.classList.add("arrastando");
});
zona_de_soltar.addEventListener("dragleave", function () {
  zona_de_soltar.classList.remove("arrastando");
});
zona_de_soltar.addEventListener("drop", function (evento) {
  evento.preventDefault();
  zona_de_soltar.classList.remove("arrastando");
  adicionar_arquivos(evento.dataTransfer.files);
});
botao_enviar.addEventListener("click", enviar_todos);
botao_limpar.addEventListener("click", function () {
  if (envio_em_andamento) return;
  fila_de_arquivos = [];
  fila_de_envio.innerHTML = "";
  resumo_final.textContent = "";
  botao_enviar.disabled = true;
});
