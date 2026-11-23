"""Transcrição de arquivos de áudio usando o reconhecimento de fala do Google."""

import io
import shutil
import subprocess
import threading

from .config import IDIOMA_TRANSCRICAO, TAMANHO_TRECHO_MS

TIMEOUT_SERVICO_S = 30


class TranscricaoCancelada(Exception):
    """O usuário cancelou a transcrição."""


class ErroServicoTranscricao(Exception):
    """O serviço de reconhecimento de fala ficou indisponível (rede, cota, etc.)."""


# Janela onde se procura a pausa para cortar: trechos de 7 a 13 s. A API gratuita do Google
# erra mais com trechos longos; cortar na pausa evita partir uma palavra entre dois trechos.
MINIMO_TRECHO_MS = 7_000
MAXIMO_TRECHO_MS = 13_000
QUADRO_MS = 50
# Um quadro só conta como pausa se estiver bem abaixo do volume médio da janela.
_LIMIAR_PAUSA = 0.6


def _melhor_corte(audio, inicio, alvo_ms, minimo_ms, maximo_ms, quadro_ms):
    """Posição (ms) do corte do trecho que começa em ``inicio``: o centro do quadro mais silencioso."""
    quadros = []
    for comeco in range(inicio + minimo_ms, inicio + maximo_ms, quadro_ms):
        quadros.append((audio[comeco:comeco + quadro_ms].rms, comeco + quadro_ms // 2))
    media = sum(rms for rms, _ in quadros) / len(quadros)
    menor = min(rms for rms, _ in quadros)
    if media > 0 and menor >= _LIMIAR_PAUSA * media:
        return inicio + maximo_ms  # sem pausa (ex.: música contínua): corta no limite
    alvo = inicio + alvo_ms
    return min((c for rms, c in quadros if rms == menor), key=lambda c: abs(c - alvo))


def escolher_cortes(audio, alvo_ms=TAMANHO_TRECHO_MS, minimo_ms=MINIMO_TRECHO_MS,
                    maximo_ms=MAXIMO_TRECHO_MS, quadro_ms=QUADRO_MS):
    """Divide o áudio em trechos cortando nas pausas, para não partir palavras ao meio.

    Para cada corte, só a janela entre ``minimo_ms`` e ``maximo_ms`` do trecho é analisada
    (em quadros de ``quadro_ms``), o que mantém o custo baixo mesmo em áudios de horas.

    Args:
        audio (AudioSegment): áudio inteiro.
        alvo_ms (int): tamanho preferido do trecho (desempate entre pausas igualmente silenciosas).
        minimo_ms (int): menor tamanho de trecho (exceto o último).
        maximo_ms (int): maior tamanho de trecho; sem pausa na janela, o corte é aqui.
        quadro_ms (int): resolução da busca pela pausa.

    Returns:
        list[tuple[int, int]]: intervalos (início, fim) contíguos, de 0 até ``len(audio)``.

    Raises:
        ValueError: se não valer ``0 < minimo_ms <= alvo_ms <= maximo_ms`` e ``quadro_ms > 0``.
    """
    if not (0 < minimo_ms <= alvo_ms <= maximo_ms) or quadro_ms <= 0:
        raise ValueError("Tamanhos de trecho inválidos.")
    duracao = len(audio)
    trechos, inicio = [], 0
    while duracao - inicio > maximo_ms:
        corte = _melhor_corte(audio, inicio, alvo_ms, minimo_ms, maximo_ms, quadro_ms)
        trechos.append((inicio, corte))
        inicio = corte
    if duracao > inicio:
        trechos.append((inicio, duracao))
    return trechos


TAXA_AMOSTRAGEM_HZ = 16_000  # o reconhecimento de voz trabalha nesta taxa; mais que isso só gasta memória


def carregar_audio_mono_16k(caminho, executar=subprocess.run):
    """Decodifica o áudio já em mono, 16 kHz, 16 bits, direto pelo ffmpeg.

    Carregar na qualidade original (estéreo 44,1 kHz) ocuparia ~5x mais memória: uma aula
    de 2 h passaria de 1,3 GB. Assim o áudio ocupa ~230 MB (pico de ~480 MB durante a leitura,
    enquanto a saída do ffmpeg é juntada), sem piorar a transcrição.
    (O parâmetro ``parameters`` do pydub não serve: ele põe as opções depois da saída e o
    ffmpeg as ignora.)

    Args:
        caminho (str): arquivo de áudio ou vídeo.
        executar (Callable[..., subprocess.CompletedProcess]): roda o comando; injetável para testes.

    Returns:
        AudioSegment: áudio mono, 16 kHz.

    Raises:
        FileNotFoundError: ffmpeg não encontrado.
        RuntimeError: o ffmpeg não conseguiu ler o arquivo.
    """
    from pydub import AudioSegment  # import tardio: só quem transcreve precisa

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        # No Windows o erro do sistema não cita o nome do programa; assim a mensagem amigável
        # ("O ffmpeg não foi encontrado. Rode o instalador de novo.") continua funcionando.
        raise FileNotFoundError("ffmpeg não encontrado no computador.")
    comando = [ffmpeg, "-nostdin", "-i", caminho, "-vn",
               "-ac", "1", "-ar", str(TAXA_AMOSTRAGEM_HZ), "-f", "s16le", "-"]
    resultado = executar(comando, capture_output=True, stdin=subprocess.DEVNULL)
    if resultado.returncode != 0 or not resultado.stdout:
        raise RuntimeError("Não foi possível ler este arquivo de áudio.")
    return AudioSegment(data=resultado.stdout, sample_width=2, frame_rate=TAXA_AMOSTRAGEM_HZ, channels=1)


class Transcritor:
    """Transcreve áudio dividindo-o em trechos curtos e enviando cada um ao Google.

    Os trechos são exportados em memória (BytesIO), sem gerar arquivos temporários
    na pasta onde o programa está rodando.
    """

    def __init__(self, idioma=IDIOMA_TRANSCRICAO, tamanho_trecho_ms=TAMANHO_TRECHO_MS,
                 carregar_audio=carregar_audio_mono_16k, reconhecedor=None):
        """
        Args:
            idioma (str): código do idioma (ex.: "pt-BR").
            tamanho_trecho_ms (int): tamanho preferido de cada trecho (o corte procura a pausa mais próxima).
            carregar_audio (Callable[[str], AudioSegment]): carrega o arquivo; injetável para testes.
            reconhecedor (speech_recognition.Recognizer | None): injetável para testes.
        """
        self.idioma = idioma
        self.tamanho_trecho_ms = tamanho_trecho_ms
        self._carregar_audio = carregar_audio
        self._reconhecedor = reconhecedor
        self._cancelar = threading.Event()

    def cancelar(self):
        """Interrompe a transcrição antes do próximo trecho."""
        self._cancelar.set()

    def transcrever(self, caminho_audio, ao_progredir=None):
        """Transcreve o arquivo de áudio inteiro.

        Args:
            caminho_audio (str): arquivo mp3/mp4/m4a/wav etc.
            ao_progredir (Callable[[float], None] | None): recebe o percentual (0-100).

        Returns:
            tuple[str, int]: (texto transcrito, quantidade de trechos que não foram entendidos).

        Raises:
            TranscricaoCancelada: o usuário cancelou.
            ErroServicoTranscricao: falha de comunicação com o serviço do Google.
        """
        import speech_recognition as sr

        reconhecedor = self._reconhecedor or sr.Recognizer()
        # Sem limite, uma rede instável trava o trecho para sempre (e o Cancelar só age entre trechos).
        reconhecedor.operation_timeout = TIMEOUT_SERVICO_S
        audio = self._carregar_audio(caminho_audio)
        trechos = escolher_cortes(audio, self.tamanho_trecho_ms)

        partes_texto, nao_entendidos = [], 0
        for indice, (inicio, fim) in enumerate(trechos, start=1):
            if self._cancelar.is_set():
                raise TranscricaoCancelada()

            buffer = io.BytesIO()
            audio[inicio:fim].export(buffer, format="wav")
            buffer.seek(0)
            with sr.AudioFile(buffer) as fonte:
                dados = reconhecedor.record(fonte)

            try:
                partes_texto.append(reconhecedor.recognize_google(dados, language=self.idioma))
            except sr.UnknownValueError:
                nao_entendidos += 1  # silêncio/ruído: segue para o próximo trecho
            except (sr.RequestError, OSError) as erro:  # OSError inclui timeout de rede
                raise ErroServicoTranscricao(
                    f"Falha no serviço de reconhecimento de fala (trecho {indice}): {erro}"
                ) from erro

            if ao_progredir:
                ao_progredir(indice / len(trechos) * 100)

        return " ".join(partes_texto).strip(), nao_entendidos
