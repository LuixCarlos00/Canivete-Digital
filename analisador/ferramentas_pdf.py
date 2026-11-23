"""Ferramentas de PDF (juntar, dividir, comprimir, converter), sem dependência de interface gráfica.

Cada função recebe caminhos de entrada e de saída e dois callbacks opcionais:
``ao_progredir(percentual)`` e ``verificar_cancelamento()``, que levanta
``ConversaoCancelada``. Os erros que o usuário precisa ver saem como ``ErroDocumento``,
cuja mensagem já está em português claro.
"""

import io
import os
import re

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError


class ErroDocumento(Exception):
    """Problema com um documento; ``str(erro)`` é a mensagem para o usuário.

    Attributes:
        arquivo (str | None): em operações com vários arquivos, qual deles causou o erro.
    """

    def __init__(self, mensagem, arquivo=None):
        super().__init__(mensagem)
        self.arquivo = arquivo


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
                raise ErroDocumento(f"{os.path.basename(caminho)}: {erro}", arquivo=caminho) from erro
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


# Imagens acima de 160 DPI são reamostradas para 150 DPI (boa leitura na tela e na impressora caseira).
_COMPRESSAO_DPI_LIMITE = 160
_COMPRESSAO_DPI_ALVO = 150
_COMPRESSAO_QUALIDADE_JPEG = 75


def comprimir_pdf(caminho, destino, ao_progredir=None, verificar_cancelamento=None):
    """Grava uma cópia menor do PDF (recomprime as imagens e remove objetos sem uso).

    A decisão de manter ou descartar a cópia (ganho mínimo) fica com quem chama.

    Args:
        caminho (str): PDF de entrada (nunca é alterado).
        destino (str): PDF comprimido a ser criado.
        ao_progredir (Callable[[float], None] | None): recebe o percentual (0-100).
        verificar_cancelamento (Callable[[], None] | None): levanta ``ConversaoCancelada``.

    Returns:
        tuple[int, int]: (tamanho original em bytes, tamanho comprimido em bytes).

    Raises:
        ErroDocumento: arquivo ilegível.
        ConversaoCancelada: o usuário cancelou.
    """
    progredir = ao_progredir or _nada
    verificar = verificar_cancelamento or _nada
    verificar()
    with abrir_pdf(caminho) as doc:
        doc.rewrite_images(dpi_threshold=_COMPRESSAO_DPI_LIMITE, dpi_target=_COMPRESSAO_DPI_ALVO,
                           quality=_COMPRESSAO_QUALIDADE_JPEG)
        progredir(70)
        verificar()
        doc.save(destino, garbage=4, deflate=True)
    progredir(100)
    return os.path.getsize(caminho), os.path.getsize(destino)


_JPG_DPI = 150
_JPG_QUALIDADE = 85


def pdf_para_jpg(caminho, pasta_saida, ao_progredir=None, verificar_cancelamento=None):
    """Transforma cada página do PDF numa imagem JPG.

    Args:
        caminho (str): PDF de entrada.
        pasta_saida (str): pasta onde as imagens serão criadas (criada se não existir).
        ao_progredir (Callable[[float], None] | None): recebe o percentual (0-100).
        verificar_cancelamento (Callable[[], None] | None): levanta ``ConversaoCancelada``.

    Returns:
        list[str]: caminhos das imagens ("pagina 01.jpg", "pagina 02.jpg"...).

    Raises:
        ErroDocumento: arquivo ilegível.
        ConversaoCancelada: o usuário cancelou.
    """
    progredir = ao_progredir or _nada
    verificar = verificar_cancelamento or _nada
    os.makedirs(pasta_saida, exist_ok=True)
    saidas = []
    with abrir_pdf(caminho) as doc:
        largura = _largura_numero(doc.page_count)
        for indice, pagina in enumerate(doc, start=1):
            verificar()
            destino = os.path.join(pasta_saida, f"pagina {indice:0{largura}d}.jpg")
            pagina.get_pixmap(dpi=_JPG_DPI).save(destino, jpg_quality=_JPG_QUALIDADE)
            saidas.append(destino)
            progredir(indice / doc.page_count * 100)
    return saidas


# Lado maior da página = lado maior de uma folha A4, em pontos (1 pt = 1/72 pol).
_LADO_MAIOR_PAGINA_PT = 842


def _imagem_pronta_para_pdf(caminho):
    """Abre a imagem já girada como o usuário a vê (EXIF) e em RGB com fundo branco.

    Returns:
        tuple[bytes, int, int]: (PNG/JPEG em memória, largura, altura).
    """
    with Image.open(caminho) as original:
        imagem = ImageOps.exif_transpose(original)
        imagem.load()
    if imagem.mode in ("RGBA", "LA", "P"):
        imagem = imagem.convert("RGBA")
        fundo = Image.new("RGB", imagem.size, "white")
        fundo.paste(imagem, mask=imagem.getchannel("A"))
        imagem = fundo
    elif imagem.mode != "RGB":
        imagem = imagem.convert("RGB")
    buffer = io.BytesIO()
    # JPEG continua JPEG (sem perder mais qualidade que o original); o resto vira PNG (sem perda).
    formato = "JPEG" if caminho.lower().endswith((".jpg", ".jpeg")) else "PNG"
    imagem.save(buffer, format=formato, **({"quality": 95} if formato == "JPEG" else {}))
    return buffer.getvalue(), imagem.width, imagem.height


def imagens_para_pdf(caminhos, destino, ao_progredir=None, verificar_cancelamento=None):
    """Cria um PDF com uma imagem por página, na ordem da lista.

    Cada página tem as proporções da imagem, com o lado maior do tamanho do lado maior de
    uma A4, para fotos de celular não virarem páginas gigantes.

    Args:
        caminhos (list[str]): imagens JPG/PNG.
        destino (str): PDF a ser criado; só é gravado se todas as imagens derem certo.
        ao_progredir (Callable[[float], None] | None): recebe o percentual (0-100).
        verificar_cancelamento (Callable[[], None] | None): levanta ``ConversaoCancelada``.

    Raises:
        ErroDocumento: alguma imagem não pôde ser lida; a mensagem começa com o nome dela.
        ConversaoCancelada: o usuário cancelou.
    """
    progredir = ao_progredir or _nada
    verificar = verificar_cancelamento or _nada
    with pymupdf.open() as doc:
        for indice, caminho in enumerate(caminhos, start=1):
            verificar()
            nome = os.path.basename(caminho)
            if not os.path.isfile(caminho):
                raise ErroDocumento(f"Arquivo não encontrado: {nome}", arquivo=caminho)
            try:
                dados, largura, altura = _imagem_pronta_para_pdf(caminho)
            except (UnidentifiedImageError, OSError, ValueError) as erro:
                raise ErroDocumento(f"{nome}: Não foi possível abrir esta imagem.", arquivo=caminho) from erro
            escala = _LADO_MAIOR_PAGINA_PT / max(largura, altura)
            pagina = doc.new_page(width=largura * escala, height=altura * escala)
            pagina.insert_image(pagina.rect, stream=dados)
            progredir(indice / len(caminhos) * 100)
        verificar()
        doc.save(destino, garbage=3, deflate=True)


def _converter_com_pdf2docx(caminho, destino):
    """Conversão padrão PDF→Word (import tardio: a biblioteca é pesada e avisa sobre o "fitz")."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from pdf2docx import Converter

    conversor = Converter(caminho)
    try:
        conversor.convert(destino)
    finally:
        conversor.close()


def _docx_legivel(caminho):
    import docx

    try:
        docx.Document(caminho)
        return True
    except Exception:  # noqa: BLE001 - qualquer falha ao abrir = arquivo inútil para o usuário
        return False


def pdf_para_word(caminho, destino, ao_progredir=None, verificar_cancelamento=None, converter=None):
    """Converte um PDF num documento do Word (.docx).

    Args:
        caminho (str): PDF de entrada.
        destino (str): .docx a ser criado; é apagado se a conversão falhar.
        ao_progredir (Callable[[float], None] | None): recebe o percentual (0-100). A biblioteca
            não informa progresso por página, então só há 0 e 100.
        verificar_cancelamento (Callable[[], None] | None): levanta ``ConversaoCancelada``.
        converter (Callable[[str, str], None] | None): faz a conversão; injetável para testes.

    Returns:
        bool: True se o PDF tem texto; False se parece escaneado (o Word terá só imagens).

    Raises:
        ErroDocumento: PDF ilegível ou falha na conversão.
        ConversaoCancelada: o usuário cancelou antes de começar.
    """
    import traceback

    progredir = ao_progredir or _nada
    (verificar_cancelamento or _nada)()
    with abrir_pdf(caminho) as doc:
        tem_texto = any(pagina.get_text().strip() for pagina in doc)
    progredir(0)
    try:
        (converter or _converter_com_pdf2docx)(caminho, destino)
        if not _docx_legivel(destino):
            raise RuntimeError("o .docx gerado não abre")
    except Exception as erro:  # noqa: BLE001 - a biblioteca falha de formas variadas em PDFs complexos
        traceback.print_exc()
        if os.path.exists(destino):
            os.remove(destino)
        raise ErroDocumento("Não foi possível converter este PDF para Word.") from erro
    progredir(100)
    return tem_texto
