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


def _nada(*_args):
    """Callback vazio, usado quando quem chama não quer progresso/cancelamento."""


def _nome_sem_extensao(caminho):
    return os.path.splitext(os.path.basename(caminho))[0]


def _largura_numero(total):
    """Quantos dígitos usar na numeração das páginas ("01", "001"...)."""
    return max(2, len(str(total)))


def juntar_pdfs(caminhos, destino, ao_progredir=None, verificar_cancelamento=None):
    """Junta vários PDFs num só, na ordem da lista.

    Args:
        caminhos (list[str]): PDFs de entrada, na ordem desejada.
        destino (str): PDF a ser criado; só é gravado se todos os arquivos derem certo.
        ao_progredir (Callable[[float], None] | None): recebe o percentual (0-100).
        verificar_cancelamento (Callable[[], None] | None): levanta ``ConversaoCancelada``.

    Raises:
        ErroDocumento: algum arquivo não pôde ser lido; a mensagem começa com o nome dele.
        ConversaoCancelada: o usuário cancelou.
    """
    progredir = ao_progredir or _nada
    verificar = verificar_cancelamento or _nada
    with pymupdf.open() as saida:
        for indice, caminho in enumerate(caminhos, start=1):
            verificar()
            try:
                with abrir_pdf(caminho) as doc:
                    saida.insert_pdf(doc)
            except ErroDocumento as erro:
                raise ErroDocumento(f"{os.path.basename(caminho)}: {erro}") from erro
            progredir(indice / len(caminhos) * 100)
        verificar()
        saida.save(destino, garbage=3, deflate=True)


def dividir_pdf(caminho, pasta_saida, paginas=None, rotulo="", ao_progredir=None, verificar_cancelamento=None):
    """Separa páginas de um PDF.

    Args:
        caminho (str): PDF de entrada.
        pasta_saida (str): pasta onde os PDFs serão criados (criada se não existir).
        paginas (list[int] | None): None = cada página vira um PDF; lista (a partir de 1) = um PDF
            só com essas páginas, nessa ordem.
        rotulo (str): texto das páginas usado no nome do arquivo (ex.: "1-3,5").
        ao_progredir (Callable[[float], None] | None): recebe o percentual (0-100).
        verificar_cancelamento (Callable[[], None] | None): levanta ``ConversaoCancelada``.

    Returns:
        list[str]: caminhos dos PDFs criados.

    Raises:
        ErroDocumento: arquivo ilegível ou página inexistente.
        ConversaoCancelada: o usuário cancelou.
    """
    progredir = ao_progredir or _nada
    verificar = verificar_cancelamento or _nada
    nome = _nome_sem_extensao(caminho)
    os.makedirs(pasta_saida, exist_ok=True)
    with abrir_pdf(caminho) as doc:
        total = doc.page_count
        if paginas is None:
            largura = _largura_numero(total)
            grupos = [([i], f"{nome} - pagina {i:0{largura}d}.pdf") for i in range(1, total + 1)]
        else:
            fora = next((p for p in paginas if p > total), None)
            if fora is not None:
                raise ErroDocumento(f"O arquivo tem {total} páginas; a página {fora} não existe.")
            grupos = [(paginas, f"{nome} - paginas {rotulo}.pdf")]

        passos = sum(len(g) for g, _ in grupos)
        feitos, saidas = 0, []
        for grupo, nome_saida in grupos:
            with pymupdf.open() as novo:
                for pagina in grupo:
                    verificar()
                    novo.insert_pdf(doc, from_page=pagina - 1, to_page=pagina - 1)
                    feitos += 1
                    progredir(feitos / passos * 100)
                destino = os.path.join(pasta_saida, nome_saida)
                novo.save(destino, garbage=3, deflate=True)
            saidas.append(destino)
    return saidas
