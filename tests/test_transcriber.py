import subprocess
import time

import pytest
import speech_recognition as sr
from pydub import AudioSegment
from pydub.generators import Sine

from analisador.transcriber import (
    ErroServicoTranscricao,
    TranscricaoCancelada,
    Transcritor,
    carregar_audio_mono_16k,
    escolher_cortes,
)


def _fala(ms):
    """Tom contínuo, fazendo o papel de alguém falando."""
    return Sine(440, sample_rate=16000).to_audio_segment(duration=ms)


def _pausa(ms, volume=None):
    """Pausa entre palavras: silêncio total, ou ruído de fundo 30 dB mais baixo que a fala."""
    if volume == "ruido":
        return _fala(ms) - 30
    return AudioSegment.silent(ms, frame_rate=16000)


def test_corte_cai_na_pausa():
    audio = _fala(8_000) + _pausa(500) + _fala(10_000) + _pausa(500) + _fala(6_000)
    cortes = escolher_cortes(audio)
    assert 8_000 < cortes[0][1] < 8_500
    assert 18_500 < cortes[1][1] < 19_000


def test_corte_na_pausa_com_ruido_de_fundo():
    audio = _fala(8_000) + _pausa(500, "ruido") + _fala(10_000) + _pausa(500, "ruido") + _fala(6_000)
    cortes = escolher_cortes(audio)
    assert 8_000 < cortes[0][1] < 8_500
    assert 18_500 < cortes[1][1] < 19_000


def test_sem_pausa_corta_em_13s():
    assert escolher_cortes(_fala(30_000)) == [(0, 13_000), (13_000, 26_000), (26_000, 30_000)]


def test_audio_curto_um_trecho():
    assert escolher_cortes(_fala(5_000)) == [(0, 5_000)]
    assert escolher_cortes(_fala(13_000)) == [(0, 13_000)]
    assert escolher_cortes(AudioSegment.empty()) == []


def test_nenhum_trecho_passa_de_13s_e_cobre_tudo():
    audio = AudioSegment.empty()
    for fala, pausa in [(3_000, 200), (9_000, 700), (14_000, 300), (2_000, 1_000), (11_000, 400), (20_000, 0)]:
        audio += _fala(fala) + (_pausa(pausa) if pausa else AudioSegment.empty())
    cortes = escolher_cortes(audio)
    assert cortes[0][0] == 0 and cortes[-1][1] == len(audio)
    assert all(fim == proximo for (_, fim), (proximo, _) in zip(cortes, cortes[1:]))
    assert all(0 < fim - inicio <= 13_000 for inicio, fim in cortes)


def test_audio_longo_e_rapido():
    audio = AudioSegment.silent(30 * 60_000, frame_rate=8000)
    comeco = time.perf_counter()
    cortes = escolher_cortes(audio)
    assert time.perf_counter() - comeco < 5
    assert all(fim - inicio <= 13_000 for inicio, fim in cortes)


def test_parametros_invalidos():
    with pytest.raises(ValueError):
        escolher_cortes(_fala(1_000), minimo_ms=0)


class ReconhecedorFalso(sr.Recognizer):
    def __init__(self, respostas):
        super().__init__()
        self._respostas = list(respostas)

    def recognize_google(self, _dados, language):
        assert language == "pt-BR"
        resposta = self._respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def criar(respostas, duracao_ms=30_000):
    return Transcritor(carregar_audio=lambda _c: AudioSegment.silent(duracao_ms, frame_rate=16000),
                       reconhecedor=ReconhecedorFalso(respostas))


def test_transcreve_juntando_trechos_e_conta_nao_entendidos():
    progresso = []
    texto, nao_entendidos = criar(["olá", sr.UnknownValueError(), "mundo"]).transcrever("x.mp3", progresso.append)
    assert texto == "olá mundo"
    assert nao_entendidos == 1
    assert progresso[-1] == 100


def test_erro_de_servico_vira_excecao_clara():
    with pytest.raises(ErroServicoTranscricao, match="trecho 2"):
        criar(["olá", sr.RequestError("sem internet")]).transcrever("x.mp3")


def test_timeout_de_rede_vira_erro_de_servico_e_timeout_e_configurado():
    t = criar([TimeoutError("timed out")])
    with pytest.raises(ErroServicoTranscricao, match="trecho 1"):
        t.transcrever("x.mp3")
    assert t._reconhecedor.operation_timeout == 30


def test_cancelar_interrompe():
    t = criar(["a", "b", "c"])
    with pytest.raises(TranscricaoCancelada):
        t.transcrever("x.mp3", lambda _p: t.cancelar())


def _executor(stdout=b"", returncode=0):
    chamadas = []

    def executar(comando, **opcoes):
        chamadas.append((comando, opcoes))
        return subprocess.CompletedProcess(comando, returncode, stdout=stdout, stderr=b"erro do ffmpeg")

    return executar, chamadas


@pytest.fixture
def ffmpeg_instalado(monkeypatch):
    """Os testes do carregador não dependem de a máquina ter ffmpeg."""
    import analisador.transcriber as modulo

    monkeypatch.setattr(modulo.shutil, "which", lambda _nome: "/bin/ffmpeg")


def test_carregar_monta_comando_e_audio_mono_16k(ffmpeg_instalado):
    executar, chamadas = _executor(stdout=b"\x00\x00" * 16000)
    audio = carregar_audio_mono_16k("/pasta/aula 01.mp3", executar=executar)
    assert (len(audio), audio.channels, audio.frame_rate, audio.sample_width) == (1000, 1, 16000, 2)
    comando, opcoes = chamadas[0]
    assert comando[0] == "/bin/ffmpeg"
    assert comando[comando.index("-i") + 1] == "/pasta/aula 01.mp3"
    for par in (["-ac", "1"], ["-ar", "16000"], ["-f", "s16le"]):
        indice = comando.index(par[0])
        assert comando[indice:indice + 2] == par
    assert opcoes["capture_output"] is True and opcoes["stdin"] == subprocess.DEVNULL


@pytest.mark.parametrize("stdout, returncode", [(b"", 1), (b"", 0), (b"\x00\x00", 1)])
def test_carregar_falha_do_ffmpeg_vira_mensagem_clara(stdout, returncode, ffmpeg_instalado):
    executar, _ = _executor(stdout=stdout, returncode=returncode)
    with pytest.raises(RuntimeError, match="Não foi possível ler este arquivo de áudio."):
        carregar_audio_mono_16k("x.mp3", executar=executar)


def test_ffmpeg_ausente_gera_mensagem_de_reinstalar(monkeypatch):
    import analisador.transcriber as modulo
    from analisador.utils import mensagem_de_erro_amigavel

    monkeypatch.setattr(modulo.shutil, "which", lambda _nome: None)

    def executar_windows(comando, **_opcoes):  # o Windows não cita o nome do programa no erro
        raise FileNotFoundError(2, "O sistema não pode encontrar o arquivo especificado")

    with pytest.raises(FileNotFoundError) as erro:
        carregar_audio_mono_16k("x.mp3", executar=executar_windows)
    assert mensagem_de_erro_amigavel(erro.value).startswith("O ffmpeg não foi encontrado. Rode o instalador de novo.")
