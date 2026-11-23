# Design: transcrição sem cortes de palavras e sem estourar memória

Data: 2026-11-23 · Status: aprovado pelo dono (conversa)

## Intenção

Melhorar a transcrição por reconhecimento de voz (arquivos de áudio e vídeos sem legenda), em dois pontos:

1. Parar de cortar palavras na emenda entre trechos.
2. Não ocupar ~1,3 GB de RAM numa aula de 2 h.

A interface e o caminho da legenda do YouTube não mudam.

## Metas

- **Cortes no silêncio.** Para cada corte, analisar só a janela de 7 s a 13 s a partir do início do trecho, em quadros de 50 ms. Cortar no quadro mais silencioso (menor RMS, o volume médio do quadro).
  - Em empate, vale o quadro mais perto de 10 s.
  - Se a janela não tiver pausa, cortar em 13 s. "Não ter pausa" quer dizer: o quadro mais baixo tem RMS ≥ 60% da média da janela.
  - O último trecho vai até o fim do áudio, mesmo que seja curto.
- **Carregar enxuto.** Decodificar com o ffmpeg direto em mono, 16 kHz, 16 bits (`ffmpeg -nostdin -i <arquivo> -vn -ac 1 -ar 16000 -f s16le -`). Montar um `AudioSegment` com esses bytes. Fica em ~32 KB por segundo de áudio, ~230 MB em 2 h.

## Não-metas

- Paralelizar as chamadas ao Google.
- Whisper ou transcrição offline.
- Ler o áudio em pedaços direto do disco (streaming). O ganho já é suficiente sem isso.

## Abordagens

| Abordagem | Decisão |
|---|---|
| Corte no quadro mais silencioso de uma janela curta | **escolhida**: barata mesmo em áudio longo |
| `pydub.silence.split_on_silence` | descartada: analisa o áudio inteiro milissegundo a milissegundo, leva minutos em 2 h |
| Trechos sobrepostos | descartada: duplicaria palavras no texto |
| Parâmetro `parameters` do `AudioSegment.from_file` | descartada: o pydub põe as opções depois da saída e o ffmpeg as ignora |

## Decisões

- `calcular_trechos(duracao_ms, tamanho_trecho_ms)` é substituída por `escolher_cortes(audio, ...)`, que recebe o áudio.
- Falha do ffmpeg (código ≠ 0 ou saída vazia) vira `RuntimeError("Não foi possível ler este arquivo de áudio.")`.
- ffmpeg ausente continua gerando `FileNotFoundError`, que o `mensagem_de_erro_amigavel` já traduz.
- Testes usam áudio sintético (tons e silêncio do pydub, sem ffmpeg) e um executor de comando injetável para o carregamento.
- A verificação de ponta a ponta com ffmpeg real usa um ffmpeg descartável (`imageio-ffmpeg`) num ambiente temporário, fora do projeto.
