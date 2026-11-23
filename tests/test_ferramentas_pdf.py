import pytest

from analisador.ferramentas_pdf import (
    ErroDocumento,
    IntervaloInvalido,
    abrir_pdf,
    interpretar_intervalo,
    normalizar_intervalo,
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
