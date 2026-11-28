import io
import json
import os

import pytest

from analisador import atualizador


def _criar_app(pasta, commit="antigo"):
    os.makedirs(os.path.join(pasta, "analisador"), exist_ok=True)
    with open(os.path.join(pasta, "analisador", "velho.py"), "w", encoding="utf-8") as f:
        f.write("velho = True\n")
    with open(os.path.join(pasta, "main.py"), "w", encoding="utf-8") as f:
        f.write("# app antigo\n")
    with open(os.path.join(pasta, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("pytest\n")
    os.makedirs(os.path.join(pasta, "ffmpeg", "bin"), exist_ok=True)
    with open(os.path.join(pasta, "ffmpeg", "bin", "ffmpeg.exe"), "wb") as f:
        f.write(b"ffmpeg")
    atualizador.escrever_versao(pasta, commit)
    return pasta


def _criar_fonte(pasta):
    os.makedirs(os.path.join(pasta, "analisador"), exist_ok=True)
    with open(os.path.join(pasta, "analisador", "novo.py"), "w", encoding="utf-8") as f:
        f.write("novo = True\n")
    with open(os.path.join(pasta, "main.py"), "w", encoding="utf-8") as f:
        f.write("# app novo\n")
    with open(os.path.join(pasta, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("pytest>=8\n")
    return pasta


def test_commit_local_le_versao_json(tmp_path):
    _criar_app(str(tmp_path / "app"), commit="abc123")
    assert atualizador.commit_local(str(tmp_path / "app")) == "abc123"


def test_commit_local_le_head_do_git(tmp_path):
    git = tmp_path / "repo" / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text("sha-local\n", encoding="utf-8")
    assert atualizador.commit_local(str(tmp_path / "repo")) == "sha-local"


def test_verificar_atualizacao_quando_esta_na_versao(tmp_path):
    _criar_app(str(tmp_path / "app"), commit="igual")
    resultado = atualizador.verificar_atualizacao(
        str(tmp_path / "app"), consultar_commit=lambda: "igual")
    assert resultado["status"] == atualizador.ATUALIZADO


def test_verificar_atualizacao_quando_ha_versao_nova(tmp_path):
    _criar_app(str(tmp_path / "app"), commit="velho")
    resultado = atualizador.verificar_atualizacao(
        str(tmp_path / "app"), consultar_commit=lambda: "novo")
    assert resultado["status"] == atualizador.DESATUALIZADO
    assert resultado["local"] == "velho" and resultado["remoto"] == "novo"


def test_verificar_atualizacao_sem_consultar_versao(tmp_path):
    _criar_app(str(tmp_path / "app"))
    resultado = atualizador.verificar_atualizacao(
        str(tmp_path / "app"), consultar_commit=lambda: None)
    assert resultado["status"] == atualizador.ERRO


def test_atualizar_substitui_codigo_mantem_ffmpeg_e_grava_versao(tmp_path):
    app = _criar_app(str(tmp_path / "app"), commit="velho")
    fonte = _criar_fonte(str(tmp_path / "fonte"))
    dependencias = []

    resultado = atualizador.atualizar(
        app, fonte=fonte, commit="novo", instalar_dependencias=dependencias.append)

    assert resultado["status"] == atualizador.ATUALIZADO
    assert dependencias == [os.path.join(fonte, "requirements.txt")]
    assert os.path.exists(os.path.join(app, "analisador", "novo.py"))
    assert not os.path.exists(os.path.join(app, "analisador", "velho.py"))
    assert os.path.exists(os.path.join(app, "ffmpeg", "bin", "ffmpeg.exe"))
    assert atualizador.commit_local(app) == "novo"
    with open(os.path.join(app, "versao.json"), encoding="utf-8") as f:
        assert json.load(f)["repositorio"] == atualizador.REPOSITORIO


def test_atualizar_falha_nas_dependencias_nao_substitui_codigo(tmp_path):
    app = _criar_app(str(tmp_path / "app"))
    fonte = _criar_fonte(str(tmp_path / "fonte"))

    def falhar(_requirements):
        raise RuntimeError("pip falhou")

    with pytest.raises(RuntimeError, match="pip falhou"):
        atualizador.atualizar(app, fonte=fonte, commit="novo", instalar_dependencias=falhar)

    assert os.path.exists(os.path.join(app, "analisador", "velho.py"))
    assert atualizador.commit_local(app) == "antigo"


def test_atualizar_em_codigo_fonte_nao_se_auto_modifica(tmp_path):
    app = _criar_app(str(tmp_path / "repo"))
    os.makedirs(os.path.join(app, ".git"), exist_ok=True)
    fonte = _criar_fonte(str(tmp_path / "fonte"))

    resultado = atualizador.atualizar(app, fonte=fonte, commit="novo",
                                      instalar_dependencias=lambda _r: None)

    assert resultado["status"] == atualizador.CODIGO_FONTE
    assert os.path.exists(os.path.join(app, "analisador", "velho.py"))
    assert not os.path.exists(os.path.join(app, "analisador", "novo.py"))


def test_baixar_fonte_usa_url_do_commit_quando_informado(tmp_path, monkeypatch):
    urls = []

    def abrir(url, timeout=15):
        urls.append(url)
        return io.BytesIO(b"conteudo do zip")

    monkeypatch.setattr(atualizador, "_abrir_url", abrir)
    destino = tmp_path / "fonte.zip"
    atualizador.baixar_arquivo_fonte(str(destino), commit="abc123")

    assert urls == ["https://github.com/LuixCarlos00/Canivete-Digital/archive/abc123.zip"]
    assert destino.read_bytes() == b"conteudo do zip"


def test_substituir_codigo_restaura_backup_se_copia_falhar(tmp_path, monkeypatch):
    app = _criar_app(str(tmp_path / "app"))
    fonte = _criar_fonte(str(tmp_path / "fonte"))
    original = atualizador.shutil.copy2

    def falhar_depois_da_primeira(*args, **kwargs):
        if str(args[0]).endswith("main.py"):
            raise OSError("falha simulada")
        return original(*args, **kwargs)

    monkeypatch.setattr(atualizador.shutil, "copy2", falhar_depois_da_primeira)
    with pytest.raises(OSError, match="falha simulada"):
        atualizador._substituir_codigo(app, fonte)

    assert os.path.exists(os.path.join(app, "analisador", "velho.py"))
    assert os.path.exists(os.path.join(app, "main.py"))
