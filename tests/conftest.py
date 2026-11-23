import os

import pytest


@pytest.fixture
def criar_pdf(tmp_path):
    """Fábrica de PDFs de teste gerados na hora (sem arquivos binários no repositório)."""
    import pymupdf

    def _criar(nome="doc.pdf", paginas=3, texto=True, senha=None, pasta=None):
        pasta = str(pasta or tmp_path)
        os.makedirs(pasta, exist_ok=True)
        caminho = os.path.join(pasta, nome)
        doc = pymupdf.open()
        for numero in range(1, paginas + 1):
            pagina = doc.new_page()
            if texto:
                pagina.insert_text((72, 72), f"Pagina {numero}")
        # Já salvo otimizado: assim "comprimir sem ganho" é determinístico.
        opcoes = {"garbage": 4, "deflate": True}
        if senha:
            opcoes.update(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=senha, owner_pw=senha)
        doc.save(caminho, **opcoes)
        doc.close()
        return caminho

    return _criar
