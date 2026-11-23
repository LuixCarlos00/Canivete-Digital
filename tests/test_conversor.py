import os
from datetime import datetime

import pytest

from analisador.conversor import (
    COMPRIMIR,
    DIVIDIR,
    FERRAMENTAS,
    IMAGENS_PDF,
    JUNTAR,
    PDF_JPG,
    PDF_WORD,
    ConversorEmLote,
    arquivo_compativel,
    extensoes_da_ferramenta,
)
from analisador.ferramentas_pdf import ConversaoCancelada


@pytest.fixture
def pasta_saida(tmp_path):
    return tmp_path / "saida"


@pytest.fixture
def conversor(pasta_saida):
    return ConversorEmLote(str(pasta_saida), agora=lambda: datetime(2026, 11, 23, 14, 30, 0))


def test_ferramentas_na_ordem_do_spec():
    assert list(FERRAMENTAS.values()) == [
        "Juntar PDFs", "Dividir PDF", "Comprimir PDF", "PDF → Word", "PDF → JPG", "Imagens → PDF"]


def test_juntar_gera_nome_com_data(conversor, criar_pdf):
    a, b = criar_pdf("a.pdf"), criar_pdf("b.pdf")
    sucessos, falhas = conversor.converter(JUNTAR, [a, b])
    assert falhas == []
    assert len(sucessos) == 1 and sucessos[0].origens == (a, b)
    assert os.path.basename(sucessos[0].saidas[0]) == "PDFs juntados_2026-11-23_14-30-00.pdf"
    assert os.path.isfile(sucessos[0].saidas[0])


def test_juntar_um_so_pdf_falha(conversor, criar_pdf):
    assert conversor.converter(JUNTAR, [criar_pdf()]) == ([], [("", "Escolha pelo menos 2 PDFs para juntar.")])


def test_juntar_com_erro_nomeia_culpado_e_nao_salva(conversor, criar_pdf, pasta_saida):
    trancado = criar_pdf("trancado.pdf", senha="x")
    sucessos, falhas = conversor.converter(JUNTAR, [criar_pdf("a.pdf"), trancado])
    assert sucessos == []
    assert falhas == [(trancado, "trancado.pdf: Este PDF é protegido por senha.")]
    assert not pasta_saida.exists() or os.listdir(pasta_saida) == []


def test_imagens_para_pdf_nome_com_data(conversor, tmp_path):
    from PIL import Image

    foto = str(tmp_path / "foto.png")
    Image.new("RGB", (20, 10)).save(foto)
    sucessos, _ = conversor.converter(IMAGENS_PDF, [foto])
    assert os.path.basename(sucessos[0].saidas[0]) == "Imagens_2026-11-23_14-30-00.pdf"


def test_um_arquivo_ruim_nao_para_o_lote(conversor, criar_pdf):
    ruim = criar_pdf("trancado.pdf", senha="x")
    bom = criar_pdf("bom.pdf")
    inicios = []
    sucessos, falhas = conversor.converter(PDF_JPG, [ruim, bom], ao_iniciar_item=lambda *a: inicios.append(a))
    assert [s.origens for s in sucessos] == [(bom,)]
    assert falhas == [(ruim, "Este PDF é protegido por senha.")]
    assert inicios == [(1, 2, ruim), (2, 2, bom)]


def test_pdf_para_jpg_move_a_pasta_inteira(conversor, criar_pdf, pasta_saida):
    sucessos, _ = conversor.converter(PDF_JPG, [criar_pdf("doc.pdf", paginas=2)])
    assert sucessos[0].saidas == [str(pasta_saida / "doc")]
    assert sorted(os.listdir(pasta_saida / "doc")) == ["pagina 01.jpg", "pagina 02.jpg"]


def test_pdf_para_jpg_pasta_existente_ganha_sufixo(conversor, criar_pdf, pasta_saida):
    (pasta_saida / "doc").mkdir(parents=True)
    sucessos, _ = conversor.converter(PDF_JPG, [criar_pdf("doc.pdf", paginas=1)])
    assert sucessos[0].saidas == [str(pasta_saida / "doc (2)")]


def test_arquivo_sumiu_depois_de_entrar_na_lista(conversor, tmp_path):
    _, falhas = conversor.converter(COMPRIMIR, [str(tmp_path / "sumiu.pdf")])
    assert falhas == [(str(tmp_path / "sumiu.pdf"), "Arquivo não encontrado: sumiu.pdf")]


def test_mesmo_nome_de_pastas_diferentes_nao_sobrescreve(conversor, criar_pdf, tmp_path):
    a = criar_pdf("relatorio.pdf", pasta=tmp_path / "a")
    b = criar_pdf("relatorio.pdf", pasta=tmp_path / "b")
    sucessos, _ = conversor.converter(PDF_WORD, [a, b])
    assert sorted(os.path.basename(s.saidas[0]) for s in sucessos) == ["relatorio (2).docx", "relatorio.docx"]


def test_comprimir_sem_ganho_nao_gera_copia(conversor, criar_pdf, pasta_saida):
    sucessos, falhas = conversor.converter(COMPRIMIR, [criar_pdf()])
    assert falhas == []
    assert sucessos[0].saidas == []
    assert sucessos[0].aviso == "já estava otimizado, nenhuma cópia gerada"
    assert not pasta_saida.exists() or os.listdir(pasta_saida) == []


def test_comprimir_com_ganho_mostra_antes_e_depois(pasta_saida, tmp_path):
    import analisador.conversor as modulo

    def comprimir_falso(_origem, destino, **_kw):
        with open(destino, "wb") as arquivo:
            arquivo.write(b"x" * 10)
        return 12_582_912, 3_145_728

    origem = tmp_path / "grande.pdf"
    origem.write_bytes(b"%PDF")
    conversor = modulo.ConversorEmLote(str(pasta_saida), comprimir=comprimir_falso)
    sucessos, _ = conversor.converter(COMPRIMIR, [str(origem)])
    assert os.path.basename(sucessos[0].saidas[0]) == "grande (comprimido).pdf"
    assert sucessos[0].detalhe == "antes 12,0 MB → depois 3,0 MB"


def test_pdf_escaneado_vira_aviso(conversor, criar_pdf):
    sucessos, _ = conversor.converter(PDF_WORD, [criar_pdf(texto=False)])
    assert sucessos[0].aviso == "parece ser um PDF escaneado; o Word terá só imagens"


def test_dividir_cada_pagina(conversor, criar_pdf):
    sucessos, _ = conversor.converter(DIVIDIR, [criar_pdf("doc.pdf", paginas=2)])
    assert [os.path.basename(s) for s in sucessos[0].saidas] == ["doc - pagina 01.pdf", "doc - pagina 02.pdf"]


def test_dividir_com_intervalo(conversor, criar_pdf):
    sucessos, _ = conversor.converter(DIVIDIR, [criar_pdf("doc.pdf", paginas=5)], intervalo_texto="1 - 2, 5")
    assert os.path.basename(sucessos[0].saidas[0]) == "doc - paginas 1-2,5.pdf"


def test_cancelar_no_meio_nao_deixa_parcial(conversor, criar_pdf, pasta_saida):
    arquivos = [criar_pdf(f"{i}.pdf", paginas=20) for i in range(3)]

    def ao_progredir(percentual):
        if percentual > 50:
            conversor.cancelar()

    with pytest.raises(ConversaoCancelada):
        conversor.converter(DIVIDIR, arquivos, ao_progredir=ao_progredir)
    assert not pasta_saida.exists() or os.listdir(pasta_saida) == []


def test_cancelado_antes_de_comecar(conversor, criar_pdf):
    conversor.cancelar()
    with pytest.raises(ConversaoCancelada):
        conversor.converter(COMPRIMIR, [criar_pdf()])


@pytest.mark.parametrize("ferramenta, caminho, esperado", [
    (JUNTAR, "x/A.PDF", True), (JUNTAR, "x/a.png", False),
    (IMAGENS_PDF, "a.JPeG", True), (IMAGENS_PDF, "a.png", True), (IMAGENS_PDF, "a.pdf", False)])
def test_arquivo_compativel(ferramenta, caminho, esperado):
    assert arquivo_compativel(ferramenta, caminho) is esperado


def test_extensoes_da_ferramenta():
    assert extensoes_da_ferramenta(DIVIDIR) == ("*.pdf",)
    assert extensoes_da_ferramenta(IMAGENS_PDF) == ("*.jpg", "*.jpeg", "*.png")
