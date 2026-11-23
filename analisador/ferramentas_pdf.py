"""Ferramentas de PDF (juntar, dividir, comprimir, converter), sem dependência de interface gráfica.

Cada função recebe caminhos de entrada e de saída e dois callbacks opcionais:
``ao_progredir(percentual)`` e ``verificar_cancelamento()``, que levanta
``ConversaoCancelada``. Os erros que o usuário precisa ver saem como ``ErroDocumento``,
cuja mensagem já está em português claro.
"""

import os
import re

import pymupdf


class ErroDocumento(Exception):
    """Problema com um documento; ``str(erro)`` é a mensagem para o usuário."""


class IntervaloInvalido(ErroDocumento):
    """O texto de páginas digitado (ex.: "1-3, 5") não é válido."""


class ConversaoCancelada(Exception):
    """O usuário cancelou a conversão."""


_REGEX_TRECHO = re.compile(r"^(\d+)(?:-(\d+))?$")


def _trechos_do_intervalo(texto):
    """Quebra o texto em trechos normalizados ("1-3", "5"), aceitando espaços em volta do hífen."""
    compacto = re.sub(r"\s*-\s*", "-", (texto or "").strip())
    trechos = [t for t in re.split(r"[,\s]+", compacto) if t]
    if not trechos:
        raise IntervaloInvalido("Digite as páginas assim: 1-3, 5")
    return trechos


def interpretar_intervalo(texto):
    """Converte o texto de páginas na lista de páginas.

    Args:
        texto (str): ex.: "1-3, 5" (números e faixas separados por vírgula ou espaço).

    Returns:
        list[int]: páginas a partir de 1, na ordem digitada, sem repetição.

    Raises:
        IntervaloInvalido: texto vazio, faixa invertida, zero, negativo ou texto não numérico.
    """
    paginas, vistas = [], set()
    for trecho in _trechos_do_intervalo(texto):
        achado = _REGEX_TRECHO.match(trecho)
        if not achado:
            raise IntervaloInvalido(f"Não entendi as páginas \"{trecho}\". Digite assim: 1-3, 5")
        inicio = int(achado.group(1))
        fim = int(achado.group(2) or inicio)
        if inicio < 1 or fim < inicio:
            raise IntervaloInvalido(f"Não entendi as páginas \"{trecho}\". Digite assim: 1-3, 5")
        for pagina in range(inicio, fim + 1):
            if pagina not in vistas:
                vistas.add(pagina)
                paginas.append(pagina)
    return paginas


def normalizar_intervalo(texto):
    """Forma compacta do texto de páginas, usada no nome do arquivo gerado.

    Args:
        texto (str): ex.: " 1 - 3 , 5 ".

    Returns:
        str: ex.: "1-3,5".

    Raises:
        IntervaloInvalido: o texto não é válido (mesmas regras de ``interpretar_intervalo``).
    """
    interpretar_intervalo(texto)
    return ",".join(_trechos_do_intervalo(texto))


def abrir_pdf(caminho):
    """Abre um PDF, traduzindo os problemas comuns em mensagens claras.

    Args:
        caminho (str): arquivo PDF.

    Returns:
        pymupdf.Document: documento aberto (quem chama deve fechá-lo).

    Raises:
        ErroDocumento: arquivo inexistente, não é PDF/corrompido, ou protegido por senha.
    """
    nome = os.path.basename(caminho)
    if not os.path.isfile(caminho):
        raise ErroDocumento(f"Arquivo não encontrado: {nome}")
    try:
        doc = pymupdf.open(caminho, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as erro:
        raise ErroDocumento("Não foi possível abrir este arquivo como PDF.") from erro
    if doc.needs_pass:
        doc.close()
        raise ErroDocumento("Este PDF é protegido por senha.")
    return doc
