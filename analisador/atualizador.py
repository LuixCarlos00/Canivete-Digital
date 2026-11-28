"""Verificação e atualização do app a partir do GitHub.

O repositório não usa tags/releases: a referência de versão é o commit mais
recente da branch ``main``. Instalações feitas pelo instalador guardam esse
commit em ``versao.json`` dentro da pasta do app; execuções pelo código-fonte
usam o ``HEAD`` do ``.git``.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone

from . import config

REPOSITORIO = "LuixCarlos00/Canivete-Digital"
URL_API_COMMIT = f"https://api.github.com/repos/{REPOSITORIO}/commits/main"
URL_FONTE_ZIP = f"https://github.com/{REPOSITORIO}/archive/refs/heads/main.zip"
ARQUIVO_VERSAO = "versao.json"
ITENS_INSTALACAO = ("analisador", "main.py", "requirements.txt")

ATUALIZADO = "atualizado"
DESATUALIZADO = "desatualizado"
ERRO = "erro"
CODIGO_FONTE = "codigo_fonte"
PORTATIL = "portatil"


def _pasta_app(pasta_app=None):
    return pasta_app or config.pasta_da_aplicacao()


def _ler_json(caminho):
    try:
        with open(caminho, encoding="utf-8-sig") as arquivo:
            return json.load(arquivo)
    except (OSError, ValueError):
        return {}


def _commit_git(pasta_app):
    """Lê o HEAD de um clone simples (sem precisar chamar o git)."""
    git_dir = os.path.join(pasta_app, ".git")
    try:
        with open(os.path.join(git_dir, "HEAD"), encoding="utf-8") as arquivo:
            head = arquivo.read().strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        return head or None

    ref = head.split(":", 1)[1].strip()
    ref_path = os.path.join(git_dir, *ref.split("/"))
    try:
        with open(ref_path, encoding="utf-8") as arquivo:
            return arquivo.read().strip() or None
    except OSError:
        pass

    try:
        with open(os.path.join(git_dir, "packed-refs"), encoding="utf-8") as arquivo:
            for linha in arquivo:
                if linha.startswith("#") or not linha.strip():
                    continue
                sha, nome = linha.split(None, 1)
                if nome.strip() == ref:
                    return sha
    except OSError:
        pass
    return None


def commit_local(pasta_app=None):
    """Retorna o commit instalado/conhecido localmente, ou ``None``."""
    pasta = _pasta_app(pasta_app)
    dados = _ler_json(os.path.join(pasta, ARQUIVO_VERSAO))
    if dados.get("commit"):
        return dados["commit"]
    return _commit_git(pasta)


def escrever_versao(pasta_app, commit):
    """Grava o commit da versão instalada para as próximas verificações."""
    dados = {
        "commit": commit,
        "repositorio": REPOSITORIO,
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    caminho = os.path.join(_pasta_app(pasta_app), ARQUIVO_VERSAO)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")


def _abrir_url(url, timeout=15):
    pedido = urllib.request.Request(url, headers={"User-Agent": config.NOME_APP})
    return urllib.request.urlopen(pedido, timeout=timeout)


def commit_remoto(timeout=15):
    """Consulta o commit mais recente da ``main`` no GitHub."""
    pedido = urllib.request.Request(
        URL_API_COMMIT,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": config.NOME_APP,
        },
    )
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        dados = json.load(resposta)
    sha = dados.get("sha")
    if not sha:
        raise RuntimeError("O GitHub não retornou a versão mais recente.")
    return sha


def verificar_atualizacao(pasta_app=None, consultar_commit=commit_remoto):
    """Compara o commit local com o remoto.

    Returns:
        dict: ``status`` é ``ATUALIZADO``, ``DESATUALIZADO`` ou ``ERRO``; nos dois
        primeiros casos traz ``commit``/``remoto`` para a interface exibir.
    """
    local = commit_local(pasta_app)
    remoto = consultar_commit()
    if not remoto:
        return {"status": ERRO, "mensagem": "Não foi possível consultar a versão no GitHub."}
    if local == remoto:
        return {"status": ATUALIZADO, "commit": remoto}
    return {"status": DESATUALIZADO, "local": local, "remoto": remoto}


def baixar_arquivo_fonte(destino, commit=None, timeout=60):
    """Baixa o zip do commit informado (ou da ``main``) do GitHub para ``destino``."""
    url = URL_FONTE_ZIP if not commit else f"https://github.com/{REPOSITORIO}/archive/{commit}.zip"
    with _abrir_url(url, timeout=timeout) as resposta, open(destino, "wb") as arquivo:
        shutil.copyfileobj(resposta, arquivo)


def _extrair_zip_fonte(caminho_zip, destino):
    """Extrai o zip do GitHub e devolve a pasta raiz que contém ``main.py``."""
    with zipfile.ZipFile(caminho_zip) as pacote:
        nomes = pacote.namelist()
        raiz = None
        for nome in nomes:
            partes = nome.split("/")
            if len(partes) > 1 and f"{partes[0]}/main.py" in nomes:
                raiz = partes[0]
                break
        if raiz is None:
            raise RuntimeError("O pacote baixado do GitHub não contém o código do app.")
        pacote.extractall(destino)
    return os.path.join(destino, raiz)


def _instalar_dependencias(requirements):
    """Atualiza o ambiente Python do app com o ``requirements.txt`` novo."""
    comando = [sys.executable, "-m", "pip", "install", "--upgrade", "-r", requirements,
               "--quiet", "--disable-pip-version-check"]
    resultado = subprocess.run(comando, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    if resultado.returncode != 0:
        detalhe = (resultado.stderr or resultado.stdout or "").strip()[-300:]
        raise RuntimeError(f"A atualização das dependências falhou: {detalhe}")


def _remover(caminho):
    if os.path.isdir(caminho):
        shutil.rmtree(caminho)
    elif os.path.exists(caminho):
        os.remove(caminho)


def _substituir_codigo(pasta_app, fonte):
    """Troca código e requirements com backup na mesma pasta para permitir rollback."""
    backup = tempfile.mkdtemp(prefix=".atualizacao-", dir=pasta_app)
    movidos = []
    try:
        for item in ITENS_INSTALACAO:
            origem = os.path.join(fonte, item)
            destino = os.path.join(pasta_app, item)
            reserva = os.path.join(backup, item)
            if os.path.exists(destino):
                shutil.move(destino, reserva)
            movidos.append((reserva, destino))
            if os.path.isdir(origem):
                shutil.copytree(origem, destino, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(origem, destino)
    except Exception:
        for reserva, destino in reversed(movidos):
            _remover(destino)
            if os.path.exists(reserva):
                shutil.move(reserva, destino)
        raise
    finally:
        shutil.rmtree(backup, ignore_errors=True)


def _validar_fonte(fonte):
    for item in ITENS_INSTALACAO:
        if not os.path.exists(os.path.join(fonte, item)):
            raise RuntimeError(f"A fonte baixada está incompleta: falta {item}.")


def _atualizar_com_fonte(pasta_app, fonte, commit, instalar_dependencias):
    _validar_fonte(fonte)
    instalar_dependencias(os.path.join(fonte, "requirements.txt"))
    _substituir_codigo(pasta_app, fonte)
    if commit:
        escrever_versao(pasta_app, commit)
    return {"status": ATUALIZADO, "commit": commit}


def _garantir_app_instalado(pasta_app):
    for item in ("main.py", "analisador"):
        if not os.path.exists(os.path.join(pasta_app, item)):
            raise RuntimeError("Não encontrei a instalação do app para atualizar.")


def atualizar(pasta_app=None, fonte=None, commit=None, instalar_dependencias=None):
    """Atualiza a instalação do app para a ``main`` do GitHub.

    Args:
        pasta_app (str | None): pasta do app (padrão: ``config.pasta_da_aplicacao()``).
        fonte (str | None): pasta já extraída com o código novo (injetável para testes).
            Quando ``None``, baixa o zip da ``main``.
        commit (str | None): commit remoto já conhecido (evita consultar o GitHub de novo).
        instalar_dependencias (Callable[[str], None] | None): injetável para testes.

    Returns:
        dict: ``status`` é ``ATUALIZADO``, ``CODIGO_FONTE`` ou ``PORTATIL``.
    """
    pasta = _pasta_app(pasta_app)
    if getattr(sys, "frozen", False):
        return {"status": PORTATIL,
                "mensagem": "Esta é a versão portátil. Baixe a nova versão no GitHub."}
    if os.path.isdir(os.path.join(pasta, ".git")):
        return {"status": CODIGO_FONTE,
                "mensagem": "Isto é o código-fonte. Atualize com git pull ou rode o instalador."}
    _garantir_app_instalado(pasta)

    commit = commit or commit_remoto()
    instalar_dependencias = instalar_dependencias or _instalar_dependencias

    if fonte is not None:
        return _atualizar_com_fonte(pasta, fonte, commit, instalar_dependencias)

    with tempfile.TemporaryDirectory(prefix="canivete-update-") as temp:
        caminho_zip = os.path.join(temp, "fonte.zip")
        baixar_arquivo_fonte(caminho_zip, commit=commit)
        raiz = _extrair_zip_fonte(caminho_zip, temp)
        return _atualizar_com_fonte(pasta, raiz, commit, instalar_dependencias)
