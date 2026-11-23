# Transcrição sem cortes — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cortar o áudio da transcrição nas pausas (sem partir palavras) e carregá-lo em mono 16 kHz para caber na memória.

**Architecture:** Tudo em `analisador/transcriber.py`. `escolher_cortes` substitui `calcular_trechos`, e `carregar_audio_mono_16k` substitui `_carregar_audio_padrao`. O `Transcritor` mantém a mesma interface pública.

**Tech Stack:** Python ≥ 3.10, pydub (`AudioSegment`, `pydub.generators.Sine` nos testes), ffmpeg via `subprocess`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-transcricao-sem-cortes-design.md`

## Global Constraints

- Janela de corte de 7 000 a 13 000 ms a partir do início do trecho, em quadros de 50 ms. Alvo = `config.TAMANHO_TRECHO_MS` (10 000).
- Há pausa quando a janela é toda silenciosa (média de RMS = 0) **ou** quando o menor RMS fica abaixo de 60% da média da janela. Sem pausa, o corte é em 13 000 ms.
- O corte cai no centro do quadro escolhido. Em empate, vale o centro mais perto do alvo e, persistindo o empate, o primeiro.
- Comando do ffmpeg: `[ffmpeg, "-nostdin", "-i", caminho, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]`, com `ffmpeg = shutil.which("ffmpeg") or "ffmpeg"`.
- Falha de decodificação → `RuntimeError("Não foi possível ler este arquivo de áudio.")`.
- Docstrings Args/Returns/Raises. Rodar os testes com `.venv/bin/python -m pytest`.

## Review Focus

1. Áudio com ruído de fundo constante (sem silêncio absoluto), mas com pausas de fala mais baixas: o corte deve cair na pausa. Teste na Task 1.
2. Áudio com menos de 13 s, ou exatamente 13 s, vira um trecho só. Teste na Task 1.
3. Áudio longo (30 min) é cortado rápido, em menos de 5 s. Teste na Task 1.
4. Arquivo que o ffmpeg não decodifica gera mensagem clara, não traceback. Teste na Task 2.
5. Nenhum trecho passa de 13 s. Teste na Task 1.

---

### Task 1: Cortes no silêncio

**Files:**
- Modify: `analisador/transcriber.py`
- Test: `tests/test_transcriber.py`

**Interfaces:**
- Produces: `escolher_cortes(audio: AudioSegment, alvo_ms=TAMANHO_TRECHO_MS, minimo_ms=7_000, maximo_ms=13_000, quadro_ms=50) -> list[tuple[int, int]]`, com intervalos contíguos de 0 até `len(audio)`. Levanta `ValueError` se não valer `0 < minimo_ms <= alvo_ms <= maximo_ms`.
- `Transcritor.__init__`: o parâmetro `tamanho_trecho_ms` continua existindo e passa a ser o alvo.

- [ ] **Step 1: Escrever os testes que devem falhar.** Substituir os testes de `calcular_trechos` e o `AudioFalso` por áudio real do pydub. O helper `_fala(ms)` usa `Sine(440, sample_rate=16000).to_audio_segment(duration=ms)`; o helper `_pausa(ms, volume=None)` gera silêncio, ou um tom 30 dB mais baixo quando `volume="ruido"`.
  - `test_corte_cai_na_pausa`: fala 8 000 + pausa 500 + fala 10 000 + pausa 500 + fala 6 000. O primeiro corte fica em `8 000 < c < 8 500`; o segundo, em `18 500 < c < 19 000`.
  - `test_corte_na_pausa_com_ruido_de_fundo`: o mesmo, com as pausas "ruído". Os cortes ficam nas mesmas faixas.
  - `test_sem_pausa_corta_em_13s`: tom contínuo de 30 000 → `[(0, 13000), (13000, 26000), (26000, 30000)]`.
  - `test_audio_curto_um_trecho`: tom de 5 000 → `[(0, 5000)]`; exatamente 13 000 → `[(0, 13000)]`; `AudioSegment.empty()` → `[]`.
  - `test_nenhum_trecho_passa_de_13s_e_cobre_tudo`: fala e pausas alternadas de tamanhos variados (60 s). Cada trecho é ≤ 13 000, o primeiro começa em 0, os trechos são contíguos e o último termina em `len(audio)`.
  - `test_audio_longo_e_rapido`: `AudioSegment.silent(30 * 60_000, frame_rate=8000)` sai em menos de 5 s, e todo trecho tem ≤ 13 000.
  - `test_parametros_invalidos`: `minimo_ms=0` → `ValueError`.
  - Testes do `Transcritor`: trocar `AudioFalso(30_000)` por `AudioSegment.silent(30_000, frame_rate=16000)`. Silêncio total corta perto do alvo, então continuam sendo 3 trechos e os testes atuais seguem válidos.
- [ ] **Step 2: Rodar** `.venv/bin/python -m pytest tests/test_transcriber.py -q`. Esperado: FAIL (ImportError de `escolher_cortes`).
- [ ] **Step 3: Implementar** `escolher_cortes`, remover `calcular_trechos` e fazer o `Transcritor.transcrever` usar `escolher_cortes(audio, self.tamanho_trecho_ms)`. RMS por quadro com `audio[t:t + quadro_ms].rms`, analisando só a janela.
- [ ] **Step 4: Rodar** a suíte inteira. Esperado: tudo PASS.
- [ ] **Step 5: Commit** `feat(transcricao): corta o áudio nas pausas para não partir palavras`.

### Task 2: Carregar em mono 16 kHz

**Files:**
- Modify: `analisador/transcriber.py`
- Test: `tests/test_transcriber.py`

**Interfaces:**
- Produces: `carregar_audio_mono_16k(caminho: str, executar=subprocess.run) -> AudioSegment`.
  - Chama `executar(comando, capture_output=True, stdin=subprocess.DEVNULL)` e monta `AudioSegment(data=stdout, sample_width=2, frame_rate=16000, channels=1)`.
  - Vira o padrão de `carregar_audio` no `Transcritor`, no lugar de `_carregar_audio_padrao`, que é removido.

- [ ] **Step 1: Escrever os testes que devem falhar** (o executor é falso e devolve `subprocess.CompletedProcess`):
  - `test_carregar_monta_comando_e_audio_mono_16k`: o executor devolve `b"\x00\x00" * 16000` → áudio com `len == 1000`, `channels == 1` e `frame_rate == 16000`. O comando contém `"-ac", "1"`, `"-ar", "16000"` e `"-f", "s16le"`, e o caminho vem logo após `"-i"`.
  - `test_carregar_ffmpeg_falha`: com `returncode=1`, levanta `RuntimeError` e a mensagem "Não foi possível ler este arquivo de áudio.".
  - `test_carregar_saida_vazia`: com `returncode=0` e `stdout=b""`, o mesmo `RuntimeError`.
- [ ] **Step 2: Rodar**. Esperado: FAIL (ImportError).
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** a suíte inteira. Esperado: tudo PASS.
- [ ] **Step 5: Verificação real.**
  - Num venv descartável do scratchpad, instalar `imageio-ffmpeg` e expor o binário como `ffmpeg` no `PATH`.
  - Gerar um `.m4a` estéreo 44,1 kHz de 60 s (tom com pausas) e chamar `carregar_audio_mono_16k`.
  - Esperado: `channels == 1`, `frame_rate == 16000`, duração de ~60 000 ms, e `escolher_cortes` cortando nas pausas.
- [ ] **Step 6: Commit** `feat(transcricao): carrega o áudio em mono 16 kHz para economizar memória`.
