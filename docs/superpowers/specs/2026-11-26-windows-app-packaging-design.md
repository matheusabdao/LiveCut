# LiveCut: aplicativo instalavel para Windows + Releases no GitHub

Data: 2026-11-26
Status: proposta validada com o usuario

## 1. Objetivo

Transformar o LiveCut (hoje um projeto Python que exige terminal e instalacao manual) em um
aplicativo Windows que qualquer pessoa instala com um clique, e publicar as versoes
automaticamente no GitHub.

Tres entregas concretas:

- Um instalador `.exe` que instala o LiveCut, cria atalhos e desinstalador.
- Durante a instalacao, o instalador baixa os recursos necessarios (FFmpeg + modelo do
  Whisper) usando a internet do usuario, deixando o app pronto para uso offline depois.
- O app verifica se existe versao nova no GitHub e avisa, e captura erros para facilitar
  correcao futura.

Foco do publico: streamers e cliperos. A maioria nao programa. O caminho principal deve ser
"baixar, instalar, abrir, colar o link".

## 2. Nao-objetivos (fora de escopo)

- Assinatura de codigo (certificado pago). O instalador sai sem assinatura; ver Riscos.
- Sugestao automatica de correcao de crash via IA/backend. Sem servidor.
- Envio automatico de relatorios. Nada e enviado sem acao do usuario.
- MacOS/Linux. Esta spec e so Windows.
- Atualizacao automatica completa (baixar e instalar sozinho).

## 3. Arquitetura geral

O nucleo (`pipeline`, analise de audio, transcricao, ranking, corte) nao muda. A novidade e
uma camada de empacotamento, provisionamento, atualizacao e diagnostico.

Arquivos novos no repositorio:

- `pyproject.toml` - metadados, dependencias e ponto de entrada. Versao unica vinda de
  `livecut/__init__.py:__version__`.
- `packaging/livecut.spec` - receita do PyInstaller (build em pasta).
- `packaging/installer.iss` - script do Inno Setup (o instalador).
- `packaging/assets/livecut.ico` - icone do app e do instalador.
- `.github/workflows/release.yml` - build e publicacao a cada tag `v*`.
- `livecut/app_paths.py` - resolve todas as pastas (install, dados, componentes, logs).
- `livecut/provisioning.py` - baixa e instala FFmpeg + modelo do Whisper.
- `livecut/updater.py` - verifica versao nova no GitHub.
- `livecut/crash.py` - captura erros e monta o pacote de diagnostico.
- `livecut/logging_setup.py` - log em arquivo rotativo.
- `livecut/app.py` - launcher unico (abre GUI por padrao, CLI quando ha argumentos).

Fluxo de distribuicao:

```
tag v1.0.0 (push)
   -> GitHub Actions: testes, PyInstaller, Inno Setup
   -> Release no GitHub com LiveCut-Setup-1.0.0.exe
   -> usuario baixa e instala (instalador baixa FFmpeg + modelo)
   -> ao abrir, o app avisa se ha versao nova
```

A build acontece apenas no GitHub Actions; nao e necessario um Windows configurado para
gerar uma versao.

## 4. Componentes novos

### 4.1 app_paths.py

Fonte unica de verdade para localizacao de pastas, funcionando tanto no modo
desenvolvimento quanto empacotado (`sys.frozen`).

- `is_frozen()`
- `install_dir()` - pasta do executavel quando empacotado; raiz do projeto em dev.
- `bundle_dir()` - `sys._MEIPASS` quando empacotado; raiz do projeto em dev.
- `user_data_dir()` - `%APPDATA%\LiveCut` (Windows); `~/.livecut` nos demais.
- `components_dir()` - `<install_dir>\components` se gravavel, senao
  `user_data_dir()\components`.
- `ffmpeg_dir()` - `components_dir()\ffmpeg\bin`.
- `models_dir()` - `components_dir()\models`.
- `logs_dir()` - `user_data_dir()\logs`.
- `default_config_path()` - `user_data_dir()\config.json`.
- `default_output_dir()` - `Documentos\LiveCut` no Windows; `~/LiveCut` nos demais.
- `bundled_default_config()` - `bundle_dir()\config\config.json`.

### 4.2 provisioning.py

Responsavel por deixar o app utilizavel. Idempotente: pula o que ja existe.

- `ffmpeg_ready()` / `model_ready(name)` - checagens rapidas.
- `install_ffmpeg(progress)` - baixa o ZIP `essentials_build` (gyan.dev) e extrai para
  `ffmpeg_dir()`.
- `install_model(name, progress)` - baixa o modelo via `huggingface_hub.snapshot_download`
  para `models_dir()\faster-whisper-<name>`.
- `ensure_components(progress)` - roda o que faltar.
- `provision_main()` - entrada usada pelo instalador (`LiveCut.exe --provision`), com
  janela de progresso; retorna 0/1.

Falha de rede nao quebra o app: os recursos ficam pendentes e o app oferece baixar na
abertura (auto-cura).

### 4.3 updater.py

- `fetch_latest_release()` - `GET https://api.github.com/repos/matheusabdao/livecut/releases/latest`.
- `is_newer(latest, current)` - comparacao de versao (x.y.z), tolerante a prefixo `v`.
- `check_for_update()` - checa no maximo 1x a cada 24h (guarda a data em
  `user_data_dir()\last_update_check`), respeita `check_for_updates` no config.
- `open_release_page(url)` - abre no navegador padrao.

Sem envio de dados pessoais; e uma leitura publica. Pode ser desligado no `config.json`.

### 4.4 crash.py

- Instala handlers globais: `sys.excepthook`, `threading.excepthook` e
  `Tk.report_callback_exception`.
- Monta `logs\crash_<timestamp>.zip` com: traceback, versao do app, Windows/Python, status
  dos componentes, ultimas 200 linhas do log e a config sem campos sensiveis.
- Mostra dialogo com: **Reportar no GitHub** (abre Issue pre-preenchida com resumo),
  **Abrir pasta do log** e **Fechar**.
- Nada e enviado automaticamente.

## 5. Layout apos instalacao e provisionamento

```
<install_dir>\                      (per-user: %LOCALAPPDATA%\Programs\LiveCut)
  LiveCut.exe                       GUI (windowed)
  LiveCut-cli.exe                   console
  components\
    ffmpeg\bin\ffmpeg.exe, ffprobe.exe
    models\faster-whisper-small\
  config\config.json                padrao empacotado (semente)

%APPDATA%\LiveCut\                  (dados do usuario)
  config.json
  last_update_check
  logs\livecut.log, crash_*.zip

Documentos\LiveCut\                 (saida padrao dos clipes; pode ser trocada)
```

Instalacao oferece "so para mim" (sem admin) ou "para todos" via
`PrivilegesRequiredOverridesAllowed=dialog` do Inno Setup. Os componentes ficam na pasta de
instalacao (gravavel nos dois casos: per-user em `%LOCALAPPDATA%`, all-users com admin).
Se a pasta nao for gravavel, cai para `%APPDATA%\LiveCut\components`.

O instalador, como ultimo passo, roda `LiveCut.exe --provision` com barra de progresso
(marcado por padrao; pode ser desmarcado). Se falhar ou for pulado, o app detecta
componentes ausentes ao abrir e oferece baixar.

## 6. Erros, logs e robustez

- `logging_setup.py` substitui `print` por log em arquivo rotativo + console.
- `ffmpeg_utils.py` passa a resolver o FFmpeg nesta ordem: variavel `LIVECUT_FFMPEG_DIR`
  -> `ffmpeg_dir()` -> PATH do sistema.
- `config_loader.load_config` passa a usar `app_paths` quando nao recebe caminho: cria/le
  `%APPDATA%\LiveCut\config.json` a partir da semente empacotada; `paths.output_dir` e
  `paths.temp_dir` viram absolutos sob a pasta de dados/`Documentos`.
- `pipeline` continua retornando `PipelineResult(ok=False, ...)`; o launcher direciona a
  excecao fatal para `crash.py`.

## 7. Testes

Novos testes (pytest, sem dependencias pesadas):

- `app_paths`: resolucao em modo dev e modo empacotado (simulado).
- `provisioning`: `ensure_components` idempotente e tolerante a falha de rede (download
  simulado).
- `updater`: `is_newer` com casos `v1.2.3`, `1.10.0` vs `1.9.9`, iguais, invalidos.
- `crash`: o ZIP e criado com os campos esperados e sem dados sensiveis.

Os testes existentes continuam validos. CI atual (ruff + pytest) permanece.

## 8. CI e Releases

`.github/workflows/release.yml`, disparado por tag `v*`:

1. `pip install -r requirements.txt -r requirements-dev.txt`
2. `ruff check .` e `pytest -q`
3. build PyInstaller (`packaging/livecut.spec`) -> pasta `dist/LiveCut`
4. Inno Setup (`packaging/installer.iss`) -> `LiveCut-Setup-<versao>.exe`
5. Publica Release com o instalador e um `SHA256SUMS.txt`

Processo de versao: subir `__version__` em `livecut/__init__.py`, criar a tag correspondente
e fazer push. O `release.yml` injeta a versao no instalador.

## 9. Riscos e licencas

- **SmartScreen**: instalador sem assinatura pode exibir "editor desconhecido". Aceitavel no
  inicio; documentar no README. Resolver exige certificado pago.
- **FFmpeg (GPL)**: o build `essentials_build` inclui componentes GPL (x264). Vamos baixar
  do upstream, sem modificar, e incluir o aviso e o link da licenca no app e no instalador.
- **Antivirus**: PyInstaller as vezes gera falso positivo; o formato "pasta" reduz isso.
- **Icone**: comeca com um icone simples gerado; o usuario pode trocar.
- **Tamanho**: o build empacotado fica com algumas centenas de MB (deps cientificas). O
  instalador em si e pequeno; o modelo baixa na instalacao.

## 10. Criterios de aceite

- Existe `pyproject.toml` e a versao do pacote vem de `livecut/__init__.py`.
- `python -m livecut` abre a GUI; com argumentos, roda a CLI.
- `LiveCut.exe --provision` baixa FFmpeg e modelo de forma idempotente e reporta progresso.
- Sem FFmpeg/modelo, o app abre, detecta a ausencia e oferece baixar (auto-cura).
- O app avisa quando existe versao mais nova no GitHub e abre a pagina da Release.
- Um erro fatal gera `crash_<ts>.zip` e abre o dialogo de report, sem enviar nada sozinho.
- Criar uma tag `v*` gera uma Release com `LiveCut-Setup-<versao>.exe`.
- `ruff check .` e `pytest -q` passam.
