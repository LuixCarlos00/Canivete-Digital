import os
import sys

import pytest

from analisador.config import (
    NOME_APP,
    PASTA_BASE,
    PASTA_TRANSCRICOES,
    configurar_ffmpeg_local,
    migrar_pasta_antiga,
    pasta_downloads,
)

so_linux = pytest.mark.skipif(os.name == "nt" or sys.platform == "darwin", reason="regra XDG é do Linux")


@so_linux
def test_pasta_downloads_le_configuracao_xdg(tmp_path):
    (tmp_path / ".config").mkdir()
    (tmp_path / ".config" / "user-dirs.dirs").write_text(
        '# comentario\nXDG_DESKTOP_DIR="$HOME/Área de Trabalho"\nXDG_DOWNLOAD_DIR="$HOME/Baixados"\n',
        encoding="utf-8")
    assert pasta_downloads(str(tmp_path)) == str(tmp_path / "Baixados")


@so_linux
def test_pasta_downloads_desativada_aponta_para_home_e_usa_padrao(tmp_path):
    (tmp_path / ".config").mkdir()
    (tmp_path / ".config" / "user-dirs.dirs").write_text('XDG_DOWNLOAD_DIR="$HOME/"\n', encoding="utf-8")
    assert pasta_downloads(str(tmp_path)) == str(tmp_path / "Downloads")


@so_linux
def test_pasta_downloads_sem_configuracao_usa_padrao(tmp_path):
    assert pasta_downloads(str(tmp_path)) == str(tmp_path / "Downloads")


def test_arquivos_ficam_dentro_da_pasta_do_app_em_downloads():
    assert NOME_APP == "Canivete Digital"
    assert os.path.basename(PASTA_BASE) == "Canivete Digital"
    assert os.path.dirname(PASTA_TRANSCRICOES) == PASTA_BASE


def test_configura_ffmpeg_local_quando_pasta_existe(tmp_path, monkeypatch):
    pasta_bin = tmp_path / "ffmpeg" / "bin"
    pasta_bin.mkdir(parents=True)
    monkeypatch.setenv("PATH", "/usr/bin")

    assert configurar_ffmpeg_local(str(tmp_path)) is True
    assert os.environ["PATH"].split(os.pathsep)[0] == str(pasta_bin)

    configurar_ffmpeg_local(str(tmp_path))  # chamar de novo não duplica
    assert os.environ["PATH"].split(os.pathsep).count(str(pasta_bin)) == 1


def test_nao_mexe_no_path_sem_ffmpeg_local(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    assert configurar_ffmpeg_local(str(tmp_path)) is False
    assert os.environ["PATH"] == "/usr/bin"


def test_migra_pasta_antiga_com_os_arquivos(tmp_path):
    antiga, nova = tmp_path / "Analisador YouTube", tmp_path / "Canivete Digital"
    (antiga / "Videos").mkdir(parents=True)
    (antiga / "Videos" / "festa.mp4").write_text("video")
    assert migrar_pasta_antiga(str(nova), str(antiga)) is True
    assert (nova / "Videos" / "festa.mp4").read_text() == "video"
    assert not antiga.exists()


def test_nao_migra_se_a_pasta_nova_ja_existe(tmp_path):
    antiga, nova = tmp_path / "Analisador YouTube", tmp_path / "Canivete Digital"
    antiga.mkdir()
    nova.mkdir()
    assert migrar_pasta_antiga(str(nova), str(antiga)) is False
    assert antiga.exists() and nova.exists()  # nada é misturado nem apagado


def test_nao_migra_sem_pasta_antiga(tmp_path):
    assert migrar_pasta_antiga(str(tmp_path / "nova"), str(tmp_path / "antiga")) is False
    assert not (tmp_path / "nova").exists()


def test_falha_ao_migrar_nao_derruba_o_app(tmp_path, monkeypatch):
    antiga = tmp_path / "antiga"
    antiga.mkdir()

    def renomear_bloqueado(_origem, _destino):
        raise PermissionError("pasta em uso")

    monkeypatch.setattr(os, "rename", renomear_bloqueado)
    assert migrar_pasta_antiga(str(tmp_path / "nova"), str(antiga)) is False
