# Acervo — biblioteca de vídeos com busca por conteúdo

Sistema para indexar sua coleção de vídeos e permitir que os funcionários
**assistam**, **baixem** e **classifiquem por tags** cada vídeo — além de
buscar por **conteúdo visual** usando IA (ex: buscar "carro" e achar os
vídeos certos mesmo sem ninguém ter marcado essa tag).

## Como funciona, em 3 peças

1. **`process_videos.py`** — roda uma vez (na sua máquina, apontando para o
   HD externo ou pasta de vídeos). Para cada vídeo: extrai uma imagem
   (thumbnail) representativa e gera um "embedding" (uma impressão digital
   visual) usando o modelo CLIP. Tudo fica salvo em `data/catalog.db`
   (SQLite) e `data/thumbnails/`.
2. **`backend/`** — uma API (FastAPI) que expõe busca, streaming/download dos
   vídeos e edição de tags.
3. **`frontend/`** — a página que os funcionários usam: busca, grade de
   vídeos (um card por vídeo), player e botão de download.

## Passo 1 — testar localmente

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Processar uma pasta de vídeos (pode ser só uma amostra pequena primeiro):

```bash
python process_videos.py --videos /caminho/para/seus/videos --out ./data
```

Isso pode demorar — a geração do embedding CLIP é a parte mais lenta (na
primeira vez também baixa o modelo, ~350MB, então precisa de internet). Se
quiser só testar a detecção de cena e as thumbnails primeiro, sem IA:

```bash
python process_videos.py --videos /caminho/para/seus/videos --out ./data --no-embeddings
```

Depois, suba o backend (ele já serve o frontend junto):

```bash
export APP_USER=admin
export APP_PASSWORD=escolha-uma-senha
uvicorn backend.main:app --reload --port 8000
```

Abra `http://localhost:8000` no navegador.

**Importante sobre o caminho dos vídeos**: o backend serve os vídeos a partir
do caminho salvo no banco (`filepath`), então a pasta de vídeos processada
precisa continuar acessível no mesmo caminho quando o servidor rodar (ou você
processa direto no servidor final, ou copia os vídeos para lá antes).

## Passo 2 — adicionar mais vídeos depois

Rode `process_videos.py` de novo apontando para a pasta — vídeos já
processados (mesmo nome + tamanho) são pulados automaticamente. Depois, avise
o backend para recarregar o índice sem precisar reiniciar:

```bash
curl -u admin:sua-senha -X POST http://localhost:8000/api/reload-index
```

## Passo 3 — colocar no ar para os funcionários (acesso pela internet)

Como seus vídeos somam bastante espaço, o caminho mais simples e barato é:
uma **VPS com disco suficiente**, onde você copia os vídeos (do HD externo)
e roda este app diretamente nela.

Sugestão de provedores com bom custo por GB de disco: Hetzner, DigitalOcean
(com volume adicional), Contabo. Estimativa rápida: se a média dos seus
vídeos for ~500MB, 2000 vídeos ≈ 1TB — vale conferir o tamanho real da sua
pasta (`du -sh /caminho/dos/videos`) antes de escolher o plano.

Com Docker (incluso neste projeto):

```bash
# 1. copie os vídeos e este projeto para o servidor
# 2. ajuste o caminho dos vídeos no docker-compose.yml
# 3. ajuste o domínio no Caddyfile (dá HTTPS automático de graça)
# 4. processe os vídeos (pode rodar dentro do container também)
docker compose run app python process_videos.py --videos /videos --out /data

# 5. suba tudo
docker compose up -d
```

Depois disso, `https://seu-dominio.com.br` fica acessível de qualquer lugar,
com login (usuário/senha definidos no `docker-compose.yml`).

### Sobre a autenticação

O MVP usa login básico (um usuário e senha únicos para todo mundo) — simples
de configurar e já dá alguma proteção. Se depois vocês quiserem contas
individuais por funcionário (pra saber quem acessou o quê, por exemplo), dá
pra evoluir isso — é só avisar.

### Evoluindo para armazenamento em nuvem (opcional, para quando crescer)

Hoje os vídeos ficam no disco do próprio servidor. Se no futuro o volume
crescer muito ou vocês quiserem tirar a carga de banda do servidor, dá pra
migrar o armazenamento para Cloudflare R2 ou Backblaze B2 (mais baratos que
S3, sem taxa de saída) e o backend passa a redirecionar para uma URL
assinada em vez de fazer o streaming ele mesmo. É uma mudança de escopo médio
— posso ajudar quando chegar a hora.

## Estrutura do projeto

```
video-search-app/
├── process_videos.py       # pipeline: cena -> thumbnail -> embedding
├── requirements.txt
├── Dockerfile / docker-compose.yml / Caddyfile
├── backend/
│   ├── main.py              # API (busca, streaming, tags)
│   └── search.py            # lógica de busca híbrida (visual + tag)
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── data/                    # gerado pelo process_videos.py (banco + thumbnails)
```

## Limitações desta primeira versão (bom saber)

- Um usuário/senha só (sem contas individuais) — todo mundo que tiver a senha
  pode assistir, baixar e adicionar tags.
- Sem interface para apagar vídeos ou reprocessar um vídeo específico (dá pra
  fazer manualmente no banco por enquanto).
- A busca por tag é por correspondência exata da palavra; não faz plural/sinônimo.
- Vídeos maiores que alguns GB funcionam bem no streaming e no download, mas o
  *upload* inicial (copiar do HD pro servidor) é o gargalo — vale rodar por
  conexão cabeada ou deixar rodando durante a noite.
