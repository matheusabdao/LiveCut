# LiveCut: motor de highlights por sinais + interface web local

Data: 2026-10-29
Status: proposta validada com o usuario

## 1. Objetivo

Evoluir o LiveCut de um pipeline local focado em volume + palavras-chave para um produto local mais confiavel na descoberta de highlights de live, capaz de priorizar momentos de maior interesse com base em:

- reacao do chat quando houver export disponivel
- reacao do streamer no audio
- sinais verbais na transcricao
- estrutura temporal do momento (build-up, pico e rescaldo)

Ao mesmo tempo, substituir a experiencia principal de uso por uma interface web local, escura, cinematica e minimalista, sem visual generico de app de IA. A GUI Tkinter atual continua existindo como fallback durante a transicao.

## 2. Estado atual resumido

O projeto atual possui:

- pipeline linear em `livecut/pipeline.py`
- extracao de audio via FFmpeg
- transcricao local via faster-whisper
- deteccao de picos em `livecut/volume_analyzer.py`
- ranking em `livecut/clip_selector.py`
- corte final em `livecut/video_cutter.py`
- interfaces `run_cli.py` e `run_gui.py`

Limitacoes atuais observadas:

- o ranking nao entende chat
- o score favorece audio e keywords, mas ainda nao modela bem tensao, risada prolongada, explosoes coletivas ou payoff
- a GUI atual e funcional, mas tem cara de ferramenta tecnica, nao de produto de midia
- o pipeline concentra responsabilidades demais no fluxo central

## 3. Resultado esperado

Ao final desta evolucao, o LiveCut deve:

1. continuar 100% local, sem dependencia de cloud
2. aceitar VOD por URL ou arquivo local
3. aceitar upload opcional de chat exportado
4. ranquear momentos por fusao de sinais, com ou sem chat
5. gerar cortes de aproximadamente 30 segundos com melhor contexto
6. expor motivos claros para cada corte selecionado
7. oferecer uma interface web local simples de operar: entrar, analisar e sair com os cortes

## 4. Escopo desta fase

Incluido:

- refatoracao moderada do pipeline para separar sinais por responsabilidade
- suporte a ingestao e normalizacao de chat exportado
- novo motor de scoring por sinais
- preservacao do modo sem chat
- nova interface web local como experiencia principal
- manutencao da CLI e da GUI Tkinter como caminhos secundarios
- relatorios e metadados enriquecidos
- testes para parsing, scoring e selecao

Fora de escopo nesta fase:

- edicao manual fina dos cortes na interface
- timeline interativa com ajuste frame a frame
- busca automatica universal de chat em todas as plataformas
- fila multi-job persistente
- banco de dados completo de historico
- deteccao visual por cena, face ou OCR

## 5. Arquitetura proposta

### 5.1 Visao geral

O sistema passa a ter os seguintes blocos:

1. `ingest`
   - resolve URL ou arquivo local
   - recebe upload opcional de chat

2. `preprocess`
   - extrai audio
   - coleta metadados basicos do video
   - normaliza chat para um formato interno unico

3. `signal analyzers`
   - audio analyzer
   - transcript analyzer
   - chat analyzer

4. `signal fusion / ranking`
   - gera momentos candidatos
   - calcula score composto por janela
   - produz justificativas humanas

5. `clip generation`
   - posiciona janelas finais
   - evita sobreposicao excessiva
   - corta os MP4s

6. `local web app`
   - inicia jobs
   - mostra progresso
   - apresenta resultados

### 5.2 Stack da interface web local

Para manter o projeto leve e coerente com o ambiente atual, a interface web local deve ser implementada em Python, sem Node como requisito.

Proposta:

- backend local com FastAPI
- servidor local com Uvicorn
- frontend server-rendered ou estatico leve em HTML + CSS + JS vanilla
- polling simples ou SSE para progresso

Motivo:

- reduz atrito de instalacao
- reaproveita o ecossistema Python ja usado pelo projeto
- evita transformar a interface nova em um segundo projeto inteiro

## 6. Modelo de dados interno

### 6.1 Chat normalizado

Criar um formato interno unico para chat:

```json
{
  "timestamp": 123.45,
  "author": "user123",
  "text": "kkkkkkkk meu deus",
  "raw": {}
}
```

Campos obrigatorios:

- `timestamp`
- `text`

Campos opcionais:

- `author`
- `message_type`
- `raw`

### 6.2 Janela candidata

Cada momento analisado deve gerar uma estrutura semelhante a:

```json
{
  "start": 120.0,
  "end": 150.0,
  "peak_time": 138.4,
  "signals": {
    "audio_energy": 0.81,
    "audio_surge": 0.64,
    "laughter_hint": 0.52,
    "speech_density": 0.73,
    "chat_velocity": 0.89,
    "chat_laughter": 0.77,
    "chat_hype": 0.61,
    "transcript_excitement": 0.68
  },
  "score": 0.84,
  "reasons": [
    "Explosao de mensagens no chat",
    "Aumento brusco de energia no audio",
    "Linguagem de alta excitacao na transcricao"
  ]
}
```

## 7. Analise por sinais

### 7.1 Audio

Manter a deteccao atual de energia, picos e surges, mas enriquecer com:

- intensidade media na janela
- build-up antes do pico
- variacao local
- duracao da excitacao
- heuristica de risada prolongada
- heuristica de grito ou descarga emocional

Implementacao sugerida:

- novo modulo dedicado, derivado da logica atual de `volume_analyzer.py`
- separar claramente deteccao de eventos de calculo de score

### 7.2 Transcricao

Criar um analisador semantico leve sobre o output do Whisper:

- palavras de surpresa
- celebracao
- frustracao/xingamento
- urgencia/tensao
- repeticao verbal
- densidade de fala

O foco nao e NLP pesado; e um classificador heuristico local, explicavel e adaptavel por vocabulario.

### 7.3 Chat

Adicionar um novo modulo, por exemplo `livecut/chat_analyzer.py`, com:

- parser de formatos comuns (`.json`, `.jsonl`, `.csv`, `.txt` estruturado)
- normalizador de timestamp
- metricas por janela:
  - mensagens por segundo
  - burst repentino
  - repeticao coletiva
  - risadas (`kkk`, `kkkk`, `rs`, `lol`, `lmao`)
  - hype/susto/indignacao

No modo hibrido:

- se houver chat valido, o score usa esse sinal
- se nao houver chat, o score continua sem falhar
- o resultado final indica explicitamente se o chat participou do ranking

## 8. Fusao de sinais e ranking

### 8.1 Principio

O corte ideal nao e apenas um ponto alto de volume. Ele precisa refletir convergencia de interesse:

- algo aconteceu
- houve reacao do streamer, do chat ou dos dois
- o trecho tem contexto suficiente
- o payoff acontece dentro do clipe

### 8.2 Score composto

Substituir o score atual por um motor de fusao baseado em grupos de sinais:

- `audio_weight`
- `transcript_weight`
- `chat_weight`
- `structure_weight`

Comportamento adaptativo:

- com chat: pesos completos
- sem chat: redistribuicao automatica proporcional entre audio, transcript e estrutura

### 8.3 Regras de negocio

O motor deve bonificar:

- burst de chat seguido de pico de audio
- risada longa do streamer ou da audiencia
- xingamento ou explosao verbal com alta energia
- tensao crescente com payoff no final da janela
- coincidencia entre hype verbal e hype do chat

O motor deve penalizar:

- picos isolados sem contexto
- silencio demais
- janela longa com clipe "morto"
- repeticao de trechos muito proximos

## 9. Geracao dos cortes

Objetivo desta fase:

- aproximar a duracao alvo de 30 segundos
- manter flexibilidade de 24 a 36 segundos por padrao
- posicionar o pico depois do build-up, nao no inicio

Regras:

- o pico principal deve aparecer aproximadamente entre 58% e 72% do clipe
- manter anti-overlap
- preservar possibilidade de duracao configuravel no `config.json`

## 10. Interface web local

### 10.1 Direcao visual

- modo escuro
- cinematica
- minimalista
- seriedade de ferramenta de midia
- sem excesso de cards, gradientes ou elementos "AI-native"

### 10.2 Telas

#### A. Tela inicial

Campos:

- URL do VOD ou seletor de arquivo local
- upload opcional de chat
- pasta de saida
- opcoes principais enxutas
- botao principal de analise

#### B. Tela de processamento

Mostrar:

- etapa atual do pipeline
- barra de progresso coerente com etapas reais
- mensagens curtas e limpas
- estimativa simples de estado

Nao mostrar:

- console cru
- excesso de logs tecnicos por padrao

#### C. Tela de resultado

Mostrar:

- lista dos cortes gerados
- horario do trecho
- score final
- principais motivos
- excerpt de transcricao
- participacao ou nao do chat
- caminho do arquivo gerado

### 10.3 Experiencia de uso

Fluxo principal:

1. abrir app local
2. informar VOD ou arquivo
3. anexar chat se houver
4. rodar analise
5. receber cortes e relatorio

Sem etapa de revisao manual nesta fase.

## 11. Compatibilidade com a base atual

### 11.1 Reaproveitar

- `VodDownloader`
- `AudioExtractor`
- `WhisperTranscriber`
- `VideoCutter`
- partes de `VolumeAnalyzer`
- fluxo de configuracao existente

### 11.2 Refatorar

- `pipeline.py` para orquestrar modulos menores
- `clip_selector.py` para virar motor de fusao por sinais
- possivel extracao de helpers de score e heuristicas para novos arquivos

### 11.3 Adicionar

- `livecut/chat_parser.py`
- `livecut/chat_analyzer.py`
- `livecut/transcript_analyzer.py`
- `livecut/signal_fusion.py`
- `livecut/webapp/` para backend local e assets
- novo entrypoint, por exemplo `run_web.py`

## 12. Erros e degradacao graciosa

O sistema deve falhar cedo em:

- input de video invalido
- pasta de saida indisponivel
- chat fornecido mas ilegivel
- FFmpeg ausente

O sistema deve degradar sem abortar em:

- chat ausente
- chat parcialmente invalido
- heuristicas de um sinal sem confianca suficiente

Comportamento esperado:

- erro bloqueante quando nao ha como processar o video
- warning claro quando apenas um sinal opcional ficou indisponivel

## 13. Relatorios e metadados

O report e o metadata JSON devem continuar, agora com:

- participacao dos sinais por corte
- origem do score
- indicacao se houve chat
- motivos humanos ordenados
- config snapshot atualizado

## 14. Testes

Cobertura minima desta fase:

- parsing e normalizacao de chat
- ranking com chat
- ranking sem chat
- regressao de selecao de duracao alvo
- anti-overlap
- motivos coerentes para cada corte
- contrato do backend local para iniciar job e consultar status

Os testes devem focar comportamento observavel, nao apenas helpers isolados.

## 15. Plano de implementacao sugerido

1. refatorar o pipeline em etapas menores
2. adicionar parser + analyzer de chat
3. adicionar analyzer de transcricao
4. criar motor de fusao por sinais
5. ajustar selecao dos cortes para alvo de 30 segundos
6. enriquecer relatorios e metadata
7. introduzir backend web local
8. construir frontend minimalista escuro/cinematico
9. conectar progresso e resultados
10. validar regressao com CLI e GUI Tkinter

## 16. Criterios de aceite

- usuario consegue rodar o produto pela interface web local sem Node
- upload de chat e opcional
- sem chat, o sistema continua funcional
- com chat, o ranking muda de forma explicavel
- cortes ficam mais proximos do conceito de highlight com contexto + payoff
- interface nova tem apresentacao escura, cinematica e enxuta
- CLI e GUI antiga continuam utilizaveis

## 17. Decisoes fechadas nesta especificacao

- prioridade equilibrada entre inteligencia de cortes e polimento do produto
- modo hibrido para chat
- nova interface web local
- GUI Tkinter continua coexistindo por enquanto
- direcao visual cinematica em modo escuro
- fluxo automatico sem etapa de revisao manual nesta fase

