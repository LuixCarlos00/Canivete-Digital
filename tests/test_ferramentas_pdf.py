import os

import numpy
import pymupdf
import pytest
from PIL import Image

from analisador.ferramentas_pdf import (
    ConversaoCancelada,
    ErroDocumento,
    IntervaloInvalido,
    abrir_pdf,
    comprimir_pdf,
    dividir_pdf,
    imagens_para_pdf,
    juntar_pdfs,
    interpretar_intervalo,
    normalizar_intervalo,
    pdf_para_jpg,
)


@pytest.mark.parametrize("texto, esperado", [
    ("1-3, 5", [1, 2, 3, 5]), ("2,4,6", [2, 4, 6]), ("7-7", [7]),
    ("1 - 3", [1, 2, 3]), ("5 1-2", [5, 1, 2]), ("1,1,2", [1, 2]),
])
def test_interpretar_intervalo_valido(texto, esperado):
    assert interpretar_intervalo(texto) == esperado


@pytest.mark.parametrize("texto", ["", "   ", "3-1", "0", "-2", "a", "1-", "1--3", "2.5"])
def test_interpretar_intervalo_invalido(texto):
    with pytest.raises(IntervaloInvalido):
        interpretar_intervalo(texto)


def test_normalizar_intervalo():
    assert normalizar_intervalo(" 1 - 3 , 5 ") == "1-3,5"


def test_abrir_pdf_com_senha(criar_pdf):
    with pytest.raises(ErroDocumento, match="protegido por senha"):
        abrir_pdf(criar_pdf(senha="x"))


def test_abrir_arquivo_que_nao_e_pdf(tmp_path):
    lixo = tmp_path / "lixo.pdf"
    lixo.write_text("nao sou pdf")
    with pytest.raises(ErroDocumento, match="Não foi possível abrir este arquivo como PDF."):
        abrir_pdf(str(lixo))


def test_abrir_arquivo_inexistente(tmp_path):
    with pytest.raises(ErroDocumento, match="Arquivo não encontrado: some.pdf"):
        abrir_pdf(str(tmp_path / "some.pdf"))


def test_abrir_pdf_valido(criar_pdf):
    doc = abrir_pdf(criar_pdf(paginas=2))
    assert doc.page_count == 2


def _textos(caminho):
    with pymupdf.open(caminho) as doc:
        return [pagina.get_text().strip() for pagina in doc]


def test_juntar_respeita_ordem(criar_pdf, tmp_path):
    a = criar_pdf("a.pdf", paginas=2)
    b = criar_pdf("b.pdf", paginas=1)
    destino = str(tmp_path / "saida.pdf")
    progresso = []
    juntar_pdfs([b, a], destino, ao_progredir=progresso.append)
    assert _textos(destino) == ["Pagina 1", "Pagina 1", "Pagina 2"]
    assert progresso[-1] == 100


def test_juntar_com_senha_nomeia_arquivo_e_nao_salva(criar_pdf, tmp_path):
    a = criar_pdf("a.pdf")
    b = criar_pdf("trancado.pdf", senha="x")
    destino = tmp_path / "saida.pdf"
    with pytest.raises(ErroDocumento, match="trancado.pdf: Este PDF é protegido por senha."):
        juntar_pdfs([a, b], str(destino))
    assert not destino.exists()


def test_dividir_cada_pagina(criar_pdf, tmp_path):
    saidas = dividir_pdf(criar_pdf("Relatório ção.pdf", paginas=3), str(tmp_path / "out"))
    assert [os.path.basename(s) for s in saidas] == [
        "Relatório ção - pagina 01.pdf", "Relatório ção - pagina 02.pdf", "Relatório ção - pagina 03.pdf"]
    assert [_textos(s) for s in saidas] == [["Pagina 1"], ["Pagina 2"], ["Pagina 3"]]


def test_dividir_largura_do_numero_acompanha_total(criar_pdf, tmp_path):
    saidas = dividir_pdf(criar_pdf(paginas=100), str(tmp_path / "out"))
    assert os.path.basename(saidas[0]).endswith("pagina 001.pdf")


def test_dividir_paginas_escolhidas(criar_pdf, tmp_path):
    saidas = dividir_pdf(criar_pdf("doc.pdf", paginas=5), str(tmp_path / "out"), paginas=[5, 1, 2], rotulo="5,1-2")
    assert [os.path.basename(s) for s in saidas] == ["doc - paginas 5,1-2.pdf"]
    assert _textos(saidas[0]) == ["Pagina 5", "Pagina 1", "Pagina 2"]


def test_dividir_pagina_inexistente(criar_pdf, tmp_path):
    with pytest.raises(ErroDocumento, match="O arquivo tem 4 páginas; a página 9 não existe."):
        dividir_pdf(criar_pdf(paginas=4), str(tmp_path / "out"), paginas=[9], rotulo="9")


def test_juntar_cancelado(criar_pdf, tmp_path):
    def cancelar():
        raise ConversaoCancelada()

    destino = tmp_path / "s.pdf"
    with pytest.raises(ConversaoCancelada):
        juntar_pdfs([criar_pdf("a.pdf"), criar_pdf("b.pdf")], str(destino), verificar_cancelamento=cancelar)
    assert not destino.exists()


def _pdf_com_imagem_grande(tmp_path):
    """PDF com uma foto 3000x2000 de ruído numa página pequena (DPI muito acima de 150)."""
    pixels = (numpy.random.default_rng(0).random((2000, 3000, 3)) * 255).astype("uint8")
    foto = str(tmp_path / "foto.png")
    Image.fromarray(pixels).save(foto)
    caminho = str(tmp_path / "pesado.pdf")
    with pymupdf.open() as doc:
        pagina = doc.new_page(width=300, height=200)
        pagina.insert_image(pagina.rect, filename=foto)
        doc.save(caminho)
    return caminho


def test_comprimir_reduz_pdf_com_imagem_grande(tmp_path):
    origem = _pdf_com_imagem_grande(tmp_path)
    tamanho_original = os.path.getsize(origem)
    antes, depois = comprimir_pdf(origem, str(tmp_path / "c.pdf"))
    assert antes == tamanho_original
    assert depois == os.path.getsize(tmp_path / "c.pdf")
    assert depois < antes * 0.5
    assert os.path.getsize(origem) == tamanho_original  # original intocado


def test_comprimir_pdf_so_texto_grava_destino(criar_pdf, tmp_path):
    antes, depois = comprimir_pdf(criar_pdf(), str(tmp_path / "c.pdf"))
    assert (tmp_path / "c.pdf").exists() and antes > 0 and depois > 0


def _salvar(tmp_path, nome, imagem, **opcoes):
    caminho = str(tmp_path / nome)
    imagem.save(caminho, **opcoes)
    return caminho


def test_pdf_para_jpg_uma_imagem_por_pagina(criar_pdf, tmp_path):
    saidas = pdf_para_jpg(criar_pdf(paginas=2), str(tmp_path / "doc"))
    assert [os.path.basename(s) for s in saidas] == ["pagina 01.jpg", "pagina 02.jpg"]
    with Image.open(saidas[0]) as imagem:
        assert imagem.format == "JPEG"
        assert imagem.size == (1240, 1755)  # A4 (595x842 pt) a 150 DPI, arredondado para cima


def test_imagens_para_pdf_ordem_e_tamanho(tmp_path):
    larga = _salvar(tmp_path, "larga.jpg", Image.new("RGB", (4000, 3000), "red"))
    alta = _salvar(tmp_path, "alta.png", Image.new("RGBA", (300, 600), (0, 0, 0, 0)))
    destino = str(tmp_path / "s.pdf")
    imagens_para_pdf([alta, larga], destino)
    with pymupdf.open(destino) as doc:
        assert doc.page_count == 2
        assert round(doc[0].rect.height) == 842 and round(doc[0].rect.width) == 421
        assert round(doc[1].rect.width) == 842 and round(doc[1].rect.height) == 632


def test_imagens_para_pdf_transparencia_vira_fundo_branco(tmp_path):
    alta = _salvar(tmp_path, "alta.png", Image.new("RGBA", (30, 60), (0, 0, 0, 0)))
    destino = str(tmp_path / "s.pdf")
    imagens_para_pdf([alta], destino)
    with pymupdf.open(destino) as doc:
        pixel = doc[0].get_pixmap().pixel(10, 10)
    assert pixel == (255, 255, 255)


def test_imagens_para_pdf_respeita_exif(tmp_path):
    imagem = Image.new("RGB", (400, 200), "blue")
    exif = imagem.getexif()
    exif[0x0112] = 6  # celular segurado em pé: girar 90°
    caminho = _salvar(tmp_path, "celular.jpg", imagem, exif=exif)
    imagens_para_pdf([caminho], str(tmp_path / "s.pdf"))
    with pymupdf.open(str(tmp_path / "s.pdf")) as doc:
        assert doc[0].rect.height > doc[0].rect.width  # retrato, como no celular


def test_imagens_para_pdf_imagem_corrompida(tmp_path):
    ruim = tmp_path / "quebrada.jpg"
    ruim.write_bytes(b"lixo")
    boa = _salvar(tmp_path, "boa.png", Image.new("RGB", (10, 10)))
    with pytest.raises(ErroDocumento, match="quebrada.jpg: Não foi possível abrir esta imagem."):
        imagens_para_pdf([boa, str(ruim)], str(tmp_path / "s.pdf"))
    assert not (tmp_path / "s.pdf").exists()
