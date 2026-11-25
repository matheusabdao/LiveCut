# LiveCut

O LiveCut transforma o VOD de uma live em clipes prontos pra postar, sozinho e 100% no seu
computador. Sem upload, sem conta, sem nuvem, sem chave de API. Meu objetivo aqui é atingir e ajudar streamers e clipadores.

[English](README.md) · **Português**

---

## O que ele faz

Você dá pra ele um VOD da Kick, Twitch ou YouTube (ou um vídeo que já está no seu PC). O
LiveCut acha os momentos mais interessantes e corta eles em clipes curtos pra você postar.

Ele procura os momentos que realmente importam, não só as partes altas:

- reações altas, gritos e subidas bruscas no áudio
- palavras fortes no que o streamer fala (xingamento, hype, surpresa, tensão)
- quanto se fala em volta daquele momento
- fala mais empolgada

Tudo roda offline. Seu vídeo nunca sai da sua máquina.

## Pra quem é

Pra streamers e clipadores que querem clipes rápido, sem programa de edição e sem precisar de ter uma grande técnica.

---

## Instalar no Windows (mais fácil)

1. Abra a [última versão](https://github.com/matheusabdao/livecut/releases/latest).
2. Baixe o **`LiveCut-Setup-<versão>.exe`**.
3. Rode ele. Você pode instalar **só pra você** (sem admin) ou **pra todos os usuários**.
4. Deixe marcada a opção **"baixar FFmpeg e o modelo do Whisper agora"**. Ela usa sua
   internet uma vez e deixa tudo pronto pra funcionar offline.
5. Abra o **LiveCut** no Menu Iniciar, cole o link do VOD e clique em **Run pipeline**.

O Windows pode avisar que o "editor é desconhecido", porque o instalador ainda não tem
assinatura digital. Clique em **Mais informações → Executar assim mesmo**. O app confere no
GitHub se tem versão nova e te avisa quando tiver atualização.

O instalador é o caminho recomendado. Se você preferir rodar pelo código, continue lendo.

---

## Como começar pelo código (manual)

Bom, você só precisa instalar duas coisas uma vez: **Python** e **FFmpeg**.

### 1. Instale o Python

Baixe o Python 3.10 ou mais novo em [python.org](https://www.python.org/downloads/) e
instale.

- No Windows, marque a opção **"Add Python to PATH"** durante a instalação.

### 2. Pegue o FFmpeg

Baixe o ZIP `essentials_build` [aqui](https://www.gyan.dev/ffmpeg/builds/), extraia e jogue
a pasta extraída dentro da pasta do projeto LiveCut.

No fim vai ficar mais ou menos assim:

```
Live Cut/
├── ffmpeg-2026-08-09-git-6bbc22dc09-essentials_build/
│   └── bin/          <-- é aqui que ficam o ffmpeg.exe e o ffprobe.exe
├── livecut/
├── config/
├── run_gui.py
└── run_cli.py
```

Se você já tem o FFmpeg instalado no sistema, ele também funciona. Mas a pasta acima é o
jeito mais simples.

### 3. Instale o projeto

Abra um terminal **dentro da pasta do LiveCut** e rode os comandos abaixo, um por um:

```bash
# cria um ambiente Python isolado
python -m venv .venv

# ativa ele
#   Windows PowerShell:  .venv\Scripts\Activate.ps1
#   Windows CMD:         .venv\Scripts\activate.bat
#   macOS / Linux:       source .venv/bin/activate

# instala tudo que o LiveCut precisa
pip install -r requirements.txt
```

### 4. Rode

```bash
python run_gui.py
```

Vai abrir uma janela. Cole o link do VOD (ou escolha um arquivo do seu PC), escolha onde
salvar os clipes e clique em **Run pipeline**.

---

## Como usar a tela

A janela tem três partes simples:

1. **Input source** — cole o link do VOD, ou clique em **Browse file** pra escolher um vídeo do seu PC.
2. **Output directory** — onde os clipes vão ser salvos. Use **Open in Explorer** pra abrir a pasta depois.
3. **Options**
   - **Quality** — `Best` mantém a qualidade original do vídeo (recomendado).
   - **Keep downloaded VOD** — guarda o vídeo baixado na pasta `temp/` depois do trabalho.
   - **Skip Whisper transcription** — bem mais rápido, mas escolhe os clipes só pelo áudio.
   - **Skip final FFmpeg cut** — só analisa e gera o relatório, sem cortar os clipes.

Depois clique em **Run pipeline**. O progresso e as mensagens aparecem no log embaixo.

A primeira vez é a mais lenta, porque o Whisper precisa baixar o modelo uma vez. Depois
disso, roda tudo local.

---

## O que você recebe

Tudo fica salvo na sua pasta de saída:

| Arquivo | O que é |
|---|---|
| `clip_01_..._score0.84.mp4` | os clipes em si, prontos pra postar |
| `report_*.txt` | por que cada momento foi escolhido (notas e motivos) |
| `metadata_*.json` | a mesma informação em formato de dados |

---

## Pelo terminal (opcional)

Se você preferir a linha de comando:

```bash
# um link de VOD, melhor qualidade
python run_cli.py https://kick.com/SEU_CANAL/videos/ID -q best

# um link, pasta de saída própria, mantendo o vídeo baixado
python run_cli.py https://www.twitch.tv/videos/1234567890 -q 720p -o "D:\Clipes" -k

# um arquivo do seu PC, sem transcrição (rápido)
python run_cli.py "E:\Gravacoes\Sessao 07.mp4" --skip-transcription

# ver todas as opções
python run_cli.py --help
```

Opções úteis:

| Opção | O que faz |
|---|---|
| `-q, --quality` | `best`, `720p`, `480p` ou `worst` |
| `-o, --output-dir` | onde os clipes são salvos |
| `-k, --keep-downloaded` | mantém o VOD baixado em `temp/` |
| `--skip-transcription` | mais rápido; escolhe só pelo áudio |
| `--skip-cut` | só analisa e gera o relatório, não corta |
| `--only-download` | só baixa o VOD e para |

---

## Ajustando do seu jeito

Todas as configurações ficam em `config/config.json`. Você não precisa mexer nisso pra usar
o LiveCut, mas é assim que você faz os clipes combinarem com a sua live.

As mais úteis:

- **`clip.max_clips`** — quantos clipes gerar (padrão `8`).
- **`clip.min_duration_seconds` / `max_duration_seconds`** — tamanho do clipe (padrão 20 a 50s).
- **`clip.target_aspect_ratio`** — coloque `9:16` pra clipes verticais (Shorts, TikTok, Reels).
- **`transcription.language`** — `pt` pra português, `en` pra inglês, `es` pra espanhol.
- **`keywords`** — palavras que marcam um bom momento. Adicione os seus termos ("clutch", "ace", nomes do jogo, etc.).
- **`excitement_words`** — palavras de reação usadas pra medir empolgação (xingamento, surpresa, hype).
- **`scoring`** — o peso de cada sinal. A soma deve dar `1.0`.

Se você fala outra língua ou joga outro jogo, as listas `keywords` e `excitement_words` são
a primeira coisa a editar.

---

## Plataformas suportadas

- **Kick** (caminho recomendado, download nativo)
- **Twitch**, **YouTube**, **Facebook**, **Rumble** (via yt-dlp)
- qualquer outro site que o yt-dlp suporte
- arquivos locais (`.mp4`, `.mkv`, `.mov`, `.ts` e outros)

Se alguma plataforma parar de funcionar, atualize o baixador:

```bash
pip install -U yt-dlp
```

---

## Perguntas frequentes

**Meu vídeo vai pra nuvem?**
Não. Download, transcrição, análise e corte acontecem tudo no seu computador.

**Funciona sem placa NVIDIA?**
Funciona. Ele foi feito pra rodar na CPU, então vai bem em notebooks e desktops AMD.

**Dá pra fazer clipes verticais pra Shorts / TikTok / Reels?**
Dá. Coloque `clip.target_aspect_ratio` como `9:16` no `config.json`.

**Está faltando momento bom nos clipes. O que eu faço?**
Abra o `report_*.txt` na pasta de saída. Ele diz por que cada momento foi escolhido.
Geralmente o ajuste é adicionar `keywords` melhores pro seu jogo ou streamer.

**Dá pra rodar agendado?**
Dá. O `run_cli.py` retorna `0` quando dá certo e `1` quando falha, então funciona com cron
ou com o Agendador de Tarefas do Windows.

**Deu um erro e fechou. Onde vejo os detalhes?**
Abre uma janela com o erro e um botão pra reportar no GitHub. O arquivo de diagnóstico e o
log ficam em `%APPDATA%\LiveCut\logs` (procure o `crash_*.zip`). Nada é enviado sozinho.

---

## Para quem mexe no código

As peças principais:

```
livecut/
├── pipeline.py          orquestra a execução inteira
├── vod_downloader.py    baixa os VODs (Kick nativo + yt-dlp de reserva)
├── audio_extractor.py   extrai a faixa de áudio
├── transcriber.py       transcrição local com Whisper
├── volume_analyzer.py   detecção de volume e picos
├── clip_selector.py     pontua os momentos e escolhe os clipes
├── video_cutter.py      corta os clipes com FFmpeg
├── config_loader.py     carrega o config (do projeto ou do usuário)
├── app_paths.py         resolve as pastas no modo dev e empacotado
├── provisioning.py      baixa o FFmpeg + o modelo do Whisper
├── updater.py           confere no GitHub se tem versão nova
├── crash.py             monta o relatório de erro e o link da Issue
├── logging_setup.py     log em arquivo rotativo
└── app.py               entrada única (GUI / CLI / --provision)
run_cli.py               entrada por linha de comando
run_gui.py               interface desktop (Tkinter)
packaging/               spec do PyInstaller, script do Inno Setup, ícone
tests/                   suíte de testes
```

Rodar os testes e o linter:

```bash
pip install -r requirements-dev.txt
pytest -q
ruff check .
```

A CI roda os mesmos testes em cada push e pull request (`.github/workflows/ci.yml`). Dá pra
rodar direto pelo pacote também: `python -m livecut --version`, `python -m livecut --help`,
`python -m livecut --provision`.

Gerar o instalador do Windows (só precisa quando for lançar uma versão):

```bash
pip install pyinstaller
python packaging/make_icon.py
pyinstaller packaging/livecut.spec --noconfirm
iscc packaging/installer.iss /DAppVersion=1.0.0
```

Criar uma tag `v*` roda o `.github/workflows/release.yml`, que testa, compila e publica o
instalador nas Releases do GitHub. Suba o `__version__` em `livecut/__init__.py` antes de
criar a tag.

Próximos passos planejados: detecção melhor de highlights (usando a reação do chat) e uma
interface web local mais simples. O design está em
[`docs/superpowers/specs/`](docs/superpowers/specs/2026-10-29-livecut-web-highlight-design.md).

---

## Licença

MIT. Use como quiser.
