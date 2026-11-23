# Aba "Converter documentos" — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ao app uma terceira aba que junta, divide e comprime PDFs, converte PDF→Word, PDF→JPG e Imagens→PDF, tudo localmente.

**Architecture:** Funções puras por ferramenta em `analisador/ferramentas_pdf.py` (sem Tkinter). Um orquestrador de lote em `analisador/conversor.py` cuida de pasta temporária, cancelamento, nomes de saída e da coleta de sucessos e falhas, no mesmo molde do `TranscritorEmLote`. A aba entra no `gui.py` reaproveitando `ListaDeItens`, `_iniciar_tarefa`, `_na_ui` e o rodapé.

**Tech Stack:** Python ≥ 3.10, Tkinter/ttk, PyMuPDF (`import pymupdf`), pdf2docx, Pillow (rotação EXIF), python-docx (vem com o pdf2docx; usado para validar o .docx), pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-aba-converter-documentos-design.md`

## Global Constraints

- `requirements.txt` ganha exatamente: `pymupdf>=1.26.7,<2`, `pdf2docx>=0.5.13`, `Pillow>=10`. O teto `<2` do PyMuPDF é obrigatório (2.x exige Python 3.11 e não tem wheel para macOS Intel).
- Pillow é dependência nova, não prevista no spec: o PyMuPDF não aplica a rotação EXIF (verificado). Por isso entra explícita.
- Nada vai para a internet. Os arquivos originais nunca são alterados.
- Saída em `config.PASTA_CONVERTIDOS = os.path.join(PASTA_BASE, "Convertidos")`. Nada é sobrescrito (`utils.caminho_sem_conflito`).
- Tudo é gerado numa pasta temporária com prefixo começando por `"analisador-"` (para `limpar_sobras_temporarias` achar sobras) e só depois movido para a saída.
- Mensagens ao usuário em português, sem traceback. Mensagens fixas do spec:
  - `"Este PDF é protegido por senha."`
  - `"Não foi possível abrir este arquivo como PDF."`
  - `"Não foi possível converter este PDF para Word."`
  - `"O arquivo tem {total} páginas; a página {n} não existe."`
  - aviso de comprimir sem ganho: `"já estava otimizado, nenhuma cópia gerada"`
  - aviso de PDF escaneado: `"parece ser um PDF escaneado; o Word terá só imagens"`
- Valores fixos:
  - PDF→JPG a 150 DPI, JPEG qualidade 85.
  - Comprimir: `rewrite_images(dpi_threshold=160, dpi_target=150, quality=75)` + `save(garbage=4, deflate=True)`; ganho mínimo de 5%.
  - Imagens→PDF: lado maior da página = 842 pt.
  - Páginas numeradas com zeros à esquerda, largura `max(2, len(str(total)))`.
- Padrões do projeto:
  - docstrings Args/Returns/Raises em toda função pública;
  - threads de trabalho nunca tocam em widget (usar `_na_ui`);
  - cancelamento por `threading.Event`;
  - variáveis Tk lidas só na thread principal.
- Ambiente de teste: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`. Rodar os testes com `.venv/bin/python -m pytest`.

## Review Focus

1. Caminho com acento e espaço (`Relatório ção.pdf`) funciona em todas as ferramentas. Teste na Task 2.
2. Arquivo apagado ou movido depois de entrar na lista falha só aquele item, com `"Arquivo não encontrado: <nome>"`. Teste na Task 6.
3. Dois arquivos com o mesmo nome vindos de pastas diferentes (ex.: comprimir `a/relatorio.pdf` e `b/relatorio.pdf`) geram `relatorio (comprimido).pdf` e `relatorio (comprimido) (2).pdf`, sem sobrescrever. Teste na Task 6.
4. Imagem corrompida, ou que não é imagem, no Imagens→PDF falha a operação nomeando o arquivo. Teste na Task 4.
5. Cancelar no meio de um lote não deixa nenhum arquivo na pasta de saída do item em andamento. Teste na Task 6.

---

### Task 1: Dependências, erros e intervalo de páginas

**Files:**
- Modify: `requirements.txt`
- Create: `analisador/ferramentas_pdf.py`
- Create: `tests/conftest.py`
- Test: `tests/test_ferramentas_pdf.py`

**Interfaces:**
- Produces:
  - `class ErroDocumento(Exception)`: a mensagem (`str(erro)`) já é o texto para o usuário.
  - `class IntervaloInvalido(ErroDocumento)`.
  - `class ConversaoCancelada(Exception)`.
  - `interpretar_intervalo(texto: str) -> list[int]`: páginas 1-based, na ordem digitada, sem repetição; levanta `IntervaloInvalido`.
  - `normalizar_intervalo(texto: str) -> str`: ex. `" 1 - 3 , 5 "` → `"1-3,5"`; levanta `IntervaloInvalido`.
  - `abrir_pdf(caminho: str) -> pymupdf.Document`: levanta `ErroDocumento` com `"Arquivo não encontrado: <basename>"`, `"Este PDF é protegido por senha."` ou `"Não foi possível abrir este arquivo como PDF."`.
  - Fixture `criar_pdf(nome="doc.pdf", paginas=3, texto=True, senha=None, pasta=None) -> str` em `tests/conftest.py`.
    - Cria um PDF com PyMuPDF em `pasta` (criada se preciso; padrão `tmp_path`), escrevendo `"Pagina N"` em cada página quando `texto=True`.
    - Salva sempre com `garbage=4, deflate=True`, já otimizado, para que o teste "comprimir sem ganho" seja determinístico.
    - Com `senha`, salva com `encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=senha, owner_pw=senha`.

- [ ] **Step 1: Criar o venv e acrescentar ao `requirements.txt`** as três linhas das Global Constraints. Rodar `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`. Esperado: termina sem erro, e `.venv/bin/python -c "import pymupdf, pdf2docx, PIL"` não imprime nada.

- [ ] **Step 2: Escrever os testes que devem falhar**

```python
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
    lixo = tmp_path / "lixo.pdf"; lixo.write_text("nao sou pdf")
    with pytest.raises(ErroDocumento, match="Não foi possível abrir este arquivo como PDF."):
        abrir_pdf(str(lixo))

def test_abrir_arquivo_inexistente(tmp_path):
    with pytest.raises(ErroDocumento, match="Arquivo não encontrado: some.pdf"):
        abrir_pdf(str(tmp_path / "some.pdf"))
```

- [ ] **Step 3: Rodar** `.venv/bin/python -m pytest tests/test_ferramentas_pdf.py -v`. Esperado: FAIL (ImportError).

- [ ] **Step 4: Implementar** as interfaces acima em `analisador/ferramentas_pdf.py`.
  - `abrir_pdf` checa `os.path.exists` antes de abrir.
  - Captura `pymupdf.FileDataError` (e `RuntimeError` genérico do `open`) → "Não foi possível abrir...".
  - Se `doc.needs_pass`, fecha o documento e levanta "protegido por senha".

- [ ] **Step 5: Rodar** a mesma linha de teste. Esperado: PASS. Depois rodar `.venv/bin/python -m pytest -q`: os 101 testes antigos também passam.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt analisador/ferramentas_pdf.py tests/conftest.py tests/test_ferramentas_pdf.py
git commit -m "feat(conversor): adiciona base de ferramentas PDF e intervalo de páginas"
```

---

### Task 2: Juntar e dividir

**Files:**
- Modify: `analisador/ferramentas_pdf.py`
- Test: `tests/test_ferramentas_pdf.py`

**Interfaces:**
- Consumes: `abrir_pdf`, `ErroDocumento`, `ConversaoCancelada` (Task 1).
- Produces (todas aceitam `ao_progredir: Callable[[float], None] | None = None` e `verificar_cancelamento: Callable[[], None] | None = None`; o segundo levanta `ConversaoCancelada` e é chamado antes de cada página/arquivo):
  - `juntar_pdfs(caminhos: list[str], destino: str, ...) -> None`. Erro em qualquer arquivo vira `ErroDocumento(f"{basename}: {mensagem original}")`, e nada é salvo em `destino`.
  - `dividir_pdf(caminho: str, pasta_saida: str, paginas: list[int] | None = None, ...) -> list[str]`.
    - `paginas=None`: um arquivo por página, `"<nome> - pagina 01.pdf"`.
    - Com lista: um arquivo `"<nome> - paginas <rotulo>.pdf"`. O rótulo é o parâmetro `rotulo: str = ""` (o texto normalizado vindo do orquestrador).
    - Página além do total → `ErroDocumento("O arquivo tem {total} páginas; a página {n} não existe.")`.

- [ ] **Step 1: Escrever os testes que devem falhar**

```python
def test_juntar_respeita_ordem(criar_pdf, tmp_path):
    a = criar_pdf("a.pdf", paginas=2); b = criar_pdf("b.pdf", paginas=1)
    destino = str(tmp_path / "saida.pdf")
    juntar_pdfs([b, a], destino)
    doc = pymupdf.open(destino)
    assert [p.get_text().strip() for p in doc] == ["Pagina 1", "Pagina 1", "Pagina 2"]
    assert doc.page_count == 3

def test_juntar_com_senha_nomeia_arquivo_e_nao_salva(criar_pdf, tmp_path):
    a = criar_pdf("a.pdf"); b = criar_pdf("trancado.pdf", senha="x")
    destino = tmp_path / "saida.pdf"
    with pytest.raises(ErroDocumento, match="trancado.pdf: Este PDF é protegido por senha."):
        juntar_pdfs([a, b], str(destino))
    assert not destino.exists()

def test_dividir_cada_pagina(criar_pdf, tmp_path):
    saidas = dividir_pdf(criar_pdf("Relatório ção.pdf", paginas=3), str(tmp_path / "out"))
    assert [os.path.basename(s) for s in saidas] == [
        "Relatório ção - pagina 01.pdf", "Relatório ção - pagina 02.pdf", "Relatório ção - pagina 03.pdf"]
    assert all(pymupdf.open(s).page_count == 1 for s in saidas)

def test_dividir_largura_do_numero_acompanha_total(criar_pdf, tmp_path):
    saidas = dividir_pdf(criar_pdf(paginas=100), str(tmp_path / "out"))
    assert os.path.basename(saidas[0]).endswith("pagina 001.pdf")

def test_dividir_paginas_escolhidas(criar_pdf, tmp_path):
    saidas = dividir_pdf(criar_pdf("doc.pdf", paginas=5), str(tmp_path / "out"), paginas=[5, 1, 2], rotulo="5,1-2")
    assert [os.path.basename(s) for s in saidas] == ["doc - paginas 5,1-2.pdf"]
    assert [p.get_text().strip() for p in pymupdf.open(saidas[0])] == ["Pagina 5", "Pagina 1", "Pagina 2"]

def test_dividir_pagina_inexistente(criar_pdf, tmp_path):
    with pytest.raises(ErroDocumento, match="O arquivo tem 4 páginas; a página 9 não existe."):
        dividir_pdf(criar_pdf(paginas=4), str(tmp_path / "out"), paginas=[9], rotulo="9")

def test_juntar_cancelado(criar_pdf, tmp_path):
    def cancelar(): raise ConversaoCancelada()
    with pytest.raises(ConversaoCancelada):
        juntar_pdfs([criar_pdf("a.pdf"), criar_pdf("b.pdf")], str(tmp_path / "s.pdf"), verificar_cancelamento=cancelar)
```

- [ ] **Step 2: Rodar** `.venv/bin/python -m pytest tests/test_ferramentas_pdf.py -v`. Esperado: FAIL nos testes novos.

- [ ] **Step 3: Implementar** `juntar_pdfs` e `dividir_pdf`.
  - Juntar: `saida.insert_pdf(doc)` para cada arquivo; salva só no fim.
  - Dividir: `novo.insert_pdf(doc, from_page=i, to_page=i)` por página. No modo lista, `novo.select`, ou `insert_pdf` página a página na ordem dada.
  - Progresso: `indice / total * 100` após cada página/arquivo.

- [ ] **Step 4: Rodar** de novo. Esperado: PASS.

- [ ] **Step 5: Commit** `feat(conversor): juntar e dividir PDFs`.

---

### Task 3: Comprimir e formatar tamanho

**Files:**
- Modify: `analisador/ferramentas_pdf.py`
- Modify: `analisador/utils.py`
- Test: `tests/test_ferramentas_pdf.py`
- Test: `tests/test_utils.py`

**Interfaces:**
- Produces:
  - `comprimir_pdf(caminho: str, destino: str, ...) -> tuple[int, int]`: devolve `(bytes_antes, bytes_depois)`; sempre grava `destino`. A regra dos 5% fica no orquestrador.
  - `utils.formatar_tamanho(num_bytes: int) -> str`: vírgula decimal, uma casa para MB e GB, inteiro para KB e bytes.

- [ ] **Step 1: Escrever os testes que devem falhar**

```python
def test_comprimir_reduz_pdf_com_imagem_grande(tmp_path):
    # PDF com uma imagem 3000x2000 aleatória numa página de 300x200 pt (DPI alto)
    origem = _pdf_com_imagem_grande(tmp_path)   # helper local do teste, usando Pillow + numpy
    antes, depois = comprimir_pdf(origem, str(tmp_path / "c.pdf"))
    assert depois < antes * 0.5
    assert os.path.getsize(origem) == antes      # original intocado

def test_comprimir_pdf_so_texto_grava_destino(criar_pdf, tmp_path):
    antes, depois = comprimir_pdf(criar_pdf(), str(tmp_path / "c.pdf"))
    assert (tmp_path / "c.pdf").exists() and antes > 0 and depois > 0

@pytest.mark.parametrize("n, esperado", [
    (0, "0 bytes"), (900, "900 bytes"), (2048, "2 KB"),
    (12_582_912, "12,0 MB"), (3_221_225_472, "3,0 GB")])
def test_formatar_tamanho(n, esperado):
    assert formatar_tamanho(n) == esperado
```

- [ ] **Step 2: Rodar** os dois arquivos de teste. Esperado: FAIL.

- [ ] **Step 3: Implementar** com os valores das Global Constraints: `rewrite_images(dpi_threshold=160, dpi_target=150, quality=75)`, depois `save(destino, garbage=4, deflate=True)`. A base de unidade é 1024.

- [ ] **Step 4: Rodar**. Esperado: PASS.

- [ ] **Step 5: Commit** `feat(conversor): comprimir PDF`.

---

### Task 4: PDF→JPG e Imagens→PDF

**Files:**
- Modify: `analisador/ferramentas_pdf.py`
- Test: `tests/test_ferramentas_pdf.py`

**Interfaces:**
- Produces:
  - `pdf_para_jpg(caminho: str, pasta_saida: str, ...) -> list[str]`: grava `pagina 01.jpg` … dentro de `pasta_saida` (que a função cria). Usa `page.get_pixmap(dpi=150).save(caminho, jpg_quality=85)`.
  - `imagens_para_pdf(caminhos: list[str], destino: str, ...) -> None`.
    - Abre cada imagem com Pillow, aplica `ImageOps.exif_transpose` e converte para RGB. Imagem com transparência (modos RGBA/LA/P) é colada sobre fundo branco.
    - Página com as proporções da imagem e lado maior de 842 pt.
    - Insere a imagem em resolução original (PNG/JPEG em memória via `insert_image(stream=...)`).
    - Imagem ilegível → `ErroDocumento(f"{basename}: Não foi possível abrir esta imagem.")`, e nada é salvo.

- [ ] **Step 1: Escrever os testes que devem falhar**

```python
def test_pdf_para_jpg_uma_imagem_por_pagina(criar_pdf, tmp_path):
    saidas = pdf_para_jpg(criar_pdf(paginas=2), str(tmp_path / "doc"))
    assert [os.path.basename(s) for s in saidas] == ["pagina 01.jpg", "pagina 02.jpg"]
    assert Image.open(saidas[0]).format == "JPEG"

def test_imagens_para_pdf_ordem_e_tamanho(tmp_path):
    larga = _salvar(tmp_path, "larga.jpg", Image.new("RGB", (4000, 3000), "red"))
    alta = _salvar(tmp_path, "alta.png", Image.new("RGBA", (300, 600), (0, 0, 0, 0)))
    destino = str(tmp_path / "s.pdf")
    imagens_para_pdf([alta, larga], destino)
    doc = pymupdf.open(destino)
    assert doc.page_count == 2
    assert round(doc[0].rect.height) == 842 and round(doc[0].rect.width) == 421
    assert round(doc[1].rect.width) == 842 and round(doc[1].rect.height) == 632

def test_imagens_para_pdf_respeita_exif(tmp_path):
    img = Image.new("RGB", (400, 200), "blue"); exif = img.getexif(); exif[0x0112] = 6  # girar 90°
    caminho = str(tmp_path / "celular.jpg"); img.save(caminho, exif=exif)
    imagens_para_pdf([caminho], str(tmp_path / "s.pdf"))
    pagina = pymupdf.open(str(tmp_path / "s.pdf"))[0]
    assert pagina.rect.height > pagina.rect.width   # retrato, como no celular

def test_imagens_para_pdf_imagem_corrompida(tmp_path):
    ruim = tmp_path / "quebrada.jpg"; ruim.write_bytes(b"lixo")
    boa = _salvar(tmp_path, "boa.png", Image.new("RGB", (10, 10)))
    with pytest.raises(ErroDocumento, match="quebrada.jpg"):
        imagens_para_pdf([boa, str(ruim)], str(tmp_path / "s.pdf"))
    assert not (tmp_path / "s.pdf").exists()
```

- [ ] **Step 2: Rodar**. Esperado: FAIL.
- [ ] **Step 3: Implementar** as duas funções.
- [ ] **Step 4: Rodar**. Esperado: PASS.
- [ ] **Step 5: Commit** `feat(conversor): PDF para JPG e imagens para PDF`.

---

### Task 5: PDF→Word

**Files:**
- Modify: `analisador/ferramentas_pdf.py`
- Test: `tests/test_ferramentas_pdf.py`

**Interfaces:**
- Produces: `pdf_para_word(caminho: str, destino: str, ..., converter=None) -> bool`.
  - Devolve `True` se o PDF tem texto extraível em alguma página. `False` significa que é escaneado; o orquestrador emite o aviso.
  - `converter` é injetável para testes: `Callable[[str, str], None]`. O padrão usa `pdf2docx.Converter(caminho).convert(destino)` e depois `.close()`.
  - Abre com `abrir_pdf` antes, para herdar as mensagens de senha e corrompido.
  - Qualquer exceção da conversão, ou `.docx` que o `docx.Document(destino)` não abre, apaga `destino` e levanta `ErroDocumento("Não foi possível converter este PDF para Word.")`.

- [ ] **Step 1: Escrever os testes que devem falhar**

```python
def test_pdf_para_word_com_texto(criar_pdf, tmp_path):
    destino = str(tmp_path / "d.docx")
    assert pdf_para_word(criar_pdf(paginas=1), destino) is True
    assert any("Pagina 1" in p.text for p in docx.Document(destino).paragraphs)

def test_pdf_para_word_escaneado_retorna_false(criar_pdf, tmp_path):
    assert pdf_para_word(criar_pdf(texto=False), str(tmp_path / "d.docx")) is False

def test_pdf_para_word_falha_da_biblioteca(criar_pdf, tmp_path):
    def explode(_o, _d): raise RuntimeError("bug interno")
    destino = tmp_path / "d.docx"
    with pytest.raises(ErroDocumento, match="Não foi possível converter este PDF para Word."):
        pdf_para_word(criar_pdf(), str(destino), converter=explode)
    assert not destino.exists()

def test_pdf_para_word_docx_corrompido(criar_pdf, tmp_path):
    def gera_lixo(_o, d): open(d, "wb").write(b"lixo")
    with pytest.raises(ErroDocumento, match="para Word"):
        pdf_para_word(criar_pdf(), str(tmp_path / "d.docx"), converter=gera_lixo)
```

- [ ] **Step 2: Rodar**. Esperado: FAIL.
- [ ] **Step 3: Implementar.** Logar o detalhe técnico com `traceback.print_exc()`, como o `gui.py` já faz.
- [ ] **Step 4: Rodar**. Esperado: PASS.
- [ ] **Step 5: Commit** `feat(conversor): PDF para Word`.

---

### Task 6: Orquestrador de lote

**Files:**
- Modify: `analisador/config.py` (acrescentar `PASTA_CONVERTIDOS` junto às outras pastas)
- Create: `analisador/conversor.py`
- Test: `tests/test_conversor.py`

**Interfaces:**
- Consumes: todas as funções das Tasks 1–5; `utils.caminho_sem_conflito`, `utils.formatar_tamanho`, `utils.mensagem_de_erro_amigavel`; `downloader.pasta_temporaria`, `downloader.mover_sem_sobrescrever`.
- Produces:
  - Constantes `JUNTAR="juntar"`, `DIVIDIR="dividir"`, `COMPRIMIR="comprimir"`, `PDF_WORD="pdf_word"`, `PDF_JPG="pdf_jpg"`, `IMAGENS_PDF="imagens_pdf"`.
  - `FERRAMENTAS: dict[str, str]` (constante → rótulo da tela, na ordem do spec: "Juntar PDFs", "Dividir PDF", "Comprimir PDF", "PDF → Word", "PDF → JPG", "Imagens → PDF").
  - `EXTENSOES_PDF = ("*.pdf",)` e `EXTENSOES_IMAGEM = ("*.jpg", "*.jpeg", "*.png")`.
  - `extensoes_da_ferramenta(ferramenta: str) -> tuple[str, ...]`.
  - `arquivo_compativel(ferramenta: str, caminho: str) -> bool`: pela extensão, sem diferenciar maiúsculas.
  - `@dataclass ItemConvertido(origens: tuple[str, ...], saidas: list[str], aviso: str = "", detalhe: str = "")`.
  - `class ConversorEmLote(pasta_saida: str, agora: Callable[[], datetime] = datetime.now)`:
    - `cancelar() -> None`;
    - `converter(ferramenta, arquivos, intervalo_texto="", ao_progredir=None, ao_iniciar_item=None) -> tuple[list[ItemConvertido], list[tuple[str, str]]]`;
    - levanta `ConversaoCancelada`.
- Regras do `converter`:
  - **JUNTAR / IMAGENS_PDF:** uma operação. Menos de 2 PDFs em JUNTAR → falha `("", "Escolha pelo menos 2 PDFs para juntar.")`. Nomes `"PDFs juntados_%Y-%m-%d_%H-%M-%S.pdf"` / `"Imagens_%Y-%m-%d_%H-%M-%S.pdf"`. Sucesso = um `ItemConvertido` com todas as origens. Falha = uma entrada `(caminho_culpado_ou_"", mensagem)`.
  - **Demais ferramentas:** um arquivo por vez. `ao_iniciar_item(indice, total, caminho)`. Erro → `falhas.append((caminho, str(erro) if isinstance(erro, ErroDocumento) else mensagem_de_erro_amigavel(erro)))` e segue para o próximo.
  - **DIVIDIR:** com `intervalo_texto` vazio, uma página por arquivo. Senão, `interpretar_intervalo` + `normalizar_intervalo`.
  - **COMPRIMIR:** saída `"<nome> (comprimido).pdf"`. Se `depois > antes * 0.95`, não move nada e o item é sucesso com `saidas=[]` e `aviso="já estava otimizado, nenhuma cópia gerada"`. Senão, `detalhe=f"antes {formatar_tamanho(antes)} → depois {formatar_tamanho(depois)}"`.
  - **PDF_WORD:** `"<nome>.docx"`. `False` → `aviso="parece ser um PDF escaneado; o Word terá só imagens"`.
  - **PDF_JPG:** gera a pasta `<nome>` na temp e move a pasta inteira para `caminho_sem_conflito(pasta_saida, nome)`.
  - Cada item (ou a operação única) roda dentro de `pasta_temporaria("analisador-conversao-")`. Só arquivos completos são movidos com `mover_sem_sobrescrever`.
  - O `verificar_cancelamento` passado às funções levanta `ConversaoCancelada` se o `Event` estiver setado. Ele também é checado antes de cada item.

- [ ] **Step 1: Escrever os testes que devem falhar** (fixture `conversor` = `ConversorEmLote(str(tmp_path / "saida"), agora=lambda: datetime(2026, 11, 23, 14, 30, 0))`)

```python
def test_juntar_gera_nome_com_data(conversor, criar_pdf):
    sucessos, falhas = conversor.converter(JUNTAR, [criar_pdf("a.pdf"), criar_pdf("b.pdf")])
    assert falhas == [] and len(sucessos) == 1 and len(sucessos[0].origens) == 2
    assert os.path.basename(sucessos[0].saidas[0]) == "PDFs juntados_2026-11-23_14-30-00.pdf"

def test_juntar_um_so_pdf_falha(conversor, criar_pdf):
    assert conversor.converter(JUNTAR, [criar_pdf()]) == ([], [("", "Escolha pelo menos 2 PDFs para juntar.")])

def test_um_arquivo_ruim_nao_para_o_lote(conversor, criar_pdf, tmp_path):
    ruim = criar_pdf("trancado.pdf", senha="x"); bom = criar_pdf("bom.pdf")
    sucessos, falhas = conversor.converter(PDF_JPG, [ruim, bom])
    assert [s.origens for s in sucessos] == [(bom,)]
    assert falhas == [(ruim, "Este PDF é protegido por senha.")]

def test_arquivo_sumiu_depois_de_entrar_na_lista(conversor, tmp_path):            # Review Focus 2
    _, falhas = conversor.converter(COMPRIMIR, [str(tmp_path / "sumiu.pdf")])
    assert falhas[0][1] == "Arquivo não encontrado: sumiu.pdf"

def test_mesmo_nome_de_pastas_diferentes_nao_sobrescreve(conversor, criar_pdf, tmp_path):  # Review Focus 3
    a = criar_pdf("relatorio.pdf", pasta=tmp_path / "a"); b = criar_pdf("relatorio.pdf", pasta=tmp_path / "b")
    sucessos, _ = conversor.converter(PDF_WORD, [a, b])
    assert sorted(os.path.basename(s.saidas[0]) for s in sucessos) == ["relatorio (2).docx", "relatorio.docx"]

def test_comprimir_sem_ganho_nao_gera_copia(conversor, criar_pdf):
    sucessos, _ = conversor.converter(COMPRIMIR, [criar_pdf()])
    assert sucessos[0].saidas == [] and sucessos[0].aviso == "já estava otimizado, nenhuma cópia gerada"

def test_pdf_escaneado_vira_aviso(conversor, criar_pdf):
    sucessos, _ = conversor.converter(PDF_WORD, [criar_pdf(texto=False)])
    assert sucessos[0].aviso == "parece ser um PDF escaneado; o Word terá só imagens"

def test_dividir_com_intervalo(conversor, criar_pdf):
    sucessos, _ = conversor.converter(DIVIDIR, [criar_pdf("doc.pdf", paginas=5)], intervalo_texto="1 - 2, 5")
    assert os.path.basename(sucessos[0].saidas[0]) == "doc - paginas 1-2,5.pdf"

def test_cancelar_no_meio_nao_deixa_parcial(conversor, criar_pdf, tmp_path):     # Review Focus 5
    arquivos = [criar_pdf(f"{i}.pdf", paginas=20) for i in range(3)]
    def ao_progredir(p):
        if p > 50: conversor.cancelar()
    with pytest.raises(ConversaoCancelada):
        conversor.converter(DIVIDIR, arquivos, ao_progredir=ao_progredir)
    assert not (tmp_path / "saida").exists() or os.listdir(tmp_path / "saida") == []

@pytest.mark.parametrize("ferramenta, caminho, esperado", [
    (JUNTAR, "x/A.PDF", True), (JUNTAR, "x/a.png", False),
    (IMAGENS_PDF, "a.JPeG", True), (IMAGENS_PDF, "a.pdf", False)])
def test_arquivo_compativel(ferramenta, caminho, esperado):
    assert arquivo_compativel(ferramenta, caminho) is esperado
```

- [ ] **Step 2: Rodar** `.venv/bin/python -m pytest tests/test_conversor.py -v`. Esperado: FAIL.
- [ ] **Step 3: Implementar** `config.PASTA_CONVERTIDOS` e `analisador/conversor.py`.
- [ ] **Step 4: Rodar** a suíte inteira, `.venv/bin/python -m pytest -q`. Esperado: tudo PASS.
- [ ] **Step 5: Commit** `feat(conversor): orquestrador de conversão em lote`.

---

### Task 7: Reordenar itens na lista

**Files:**
- Modify: `analisador/utils.py`
- Modify: `analisador/gui.py` (classe `ListaDeItens`)
- Test: `tests/test_utils.py`

**Interfaces:**
- Produces:
  - `utils.mover_itens(valores: list, indices: list[int], delta: int) -> tuple[list, list[int]]`: devolve a nova lista e os novos índices dos itens movidos (`delta` = -1 sobe, +1 desce). Mantém juntos os itens selecionados. Se algum selecionado já está na borda para onde vai, nada muda.
  - `ListaDeItens(pai, nome_item="item", altura=8, com_ordenacao=False)`. Com `com_ordenacao=True`, ganha os botões "Subir" e "Descer" antes de "Remover selecionados", e eles entram em `.botoes`. O método `mover(delta: int)` usa `mover_itens`, reconstrói o Listbox, reseleciona os itens movidos e respeita `bloqueada`.

- [ ] **Step 1: Escrever os testes que devem falhar**

```python
@pytest.mark.parametrize("indices, delta, lista, sel", [
    ([1], -1, ["b", "a", "c", "d"], [0]),
    ([1, 2], 1, ["a", "d", "b", "c"], [2, 3]),
    ([0], -1, ["a", "b", "c", "d"], [0]),       # já no topo: nada muda
    ([3], 1, ["a", "b", "c", "d"], [3]),
    ([], 1, ["a", "b", "c", "d"], []),
])
def test_mover_itens(indices, delta, lista, sel):
    assert mover_itens(["a", "b", "c", "d"], indices, delta) == (lista, sel)
```

- [ ] **Step 2: Rodar**. Esperado: FAIL.
- [ ] **Step 3: Implementar** `mover_itens` e as mudanças na `ListaDeItens`. As abas existentes continuam com `com_ordenacao=False` e nada muda nelas.
- [ ] **Step 4: Rodar** `.venv/bin/python -m pytest -q`. Esperado: tudo PASS.
- [ ] **Step 5: Commit** `feat(gui): permite reordenar itens da lista`.

---

### Task 8: Aba "Converter documentos"

**Files:**
- Modify: `analisador/gui.py`

**Interfaces:**
- Consumes: `ConversorEmLote`, `FERRAMENTAS`, `DIVIDIR`, `IMAGENS_PDF`, `extensoes_da_ferramenta`, `arquivo_compativel`, `ConversaoCancelada` (Task 6); `interpretar_intervalo`, `IntervaloInvalido` (Task 1); `ListaDeItens(com_ordenacao=True)` (Task 7); `config.PASTA_CONVERTIDOS`.
- Produces: métodos `_montar_aba_converter(abas)`, `_ao_trocar_ferramenta()`, `_escolher_arquivos_converter()`, `_converter()`, `_concluir_conversao(sucessos, falhas)`. A aba é adicionada com o texto `"  Converter documentos  "` depois das outras duas.

Comportamento (texto e layout do rascunho do spec):

- **Seção "1. Escolha o que fazer":** radiobuttons em 2 linhas de 3, ligados a `self.ferramenta = tk.StringVar(value=JUNTAR)`.
- **Seção "2. Adicione os arquivos":** botão `"Escolher arquivos..."` com `filetypes` montado a partir de `extensoes_da_ferramenta`. Abaixo, `self.lista_converter = ListaDeItens(aba, nome_item="arquivo", altura=7, com_ordenacao=True)`, registrada em `self._listas`. Valor e rótulo de cada item: `caminho` e `os.path.basename(caminho)`. Arquivos incompatíveis escolhidos por "Todos os arquivos" são ignorados com o aviso "Estes arquivos não servem para esta ferramenta e foram ignorados:".
- **Opções de Dividir:** frame com radio "Cada página vira um PDF" / "Só as páginas:" mais um `ttk.Entry`. Aparece com `grid()` só quando a ferramenta é DIVIDIR (`grid_remove()` nas outras).
- **Trocar de ferramenta** (`command` dos radiobuttons):
  1. Se algum item da lista não é compatível com a ferramenta nova, pergunta `messagebox.askokcancel("Trocar de ferramenta", "Trocar de ferramenta vai limpar a lista. Continuar?")`.
  2. Cancelar → volta o radio para a ferramenta anterior (guardar em `self._ferramenta_anterior`).
  3. OK → limpa a lista.
- **Botão "Converter"** (destaque). Validações em messagebox, sem iniciar nada:
  - lista vazia: "Adicione pelo menos um arquivo à lista.";
  - JUNTAR com menos de 2: "Escolha pelo menos 2 PDFs para juntar.";
  - DIVIDIR em "Só as páginas" com `interpretar_intervalo` levantando erro: "Digite as páginas assim: 1-3, 5".
  - Ler `StringVar`s e o Entry na thread principal. Depois, `_iniciar_tarefa(conversor, trabalho)` com `_progresso_em_lote("Convertendo: ")`, no mesmo molde de `_transcrever`. `ConversaoCancelada` → "A conversão foi cancelada."
- **`_concluir_conversao`:** mesmo molde de `_concluir_transcricao`.
  - Remove da lista as `origens` dos sucessos.
  - Linhas por sucesso: `• <nomes das saídas ou do original>  (<detalhe ou aviso>)`.
  - Falhas: `• <basename ou "Operação">: <msg>`.
  - showerror se só falhou, showwarning se teve falha ou aviso, showinfo se tudo ok.
  - Abre `config.PASTA_CONVERTIDOS` quando houve alguma saída.
- O texto do rodapé "Os arquivos são salvos em: …" continua apontando para `PASTA_BASE`, que já contém `Convertidos`.

- [ ] **Step 1: Implementar** a aba conforme acima.
- [ ] **Step 2: Rodar** `.venv/bin/python -m pytest -q`. Esperado: tudo PASS.
- [ ] **Step 3: Smoke test manual.** Rodar `.venv/bin/python main.py` (há display `:1` nesta máquina) e conferir cada item:
  - (a) Juntar 2 PDFs depois de usar Descer;
  - (b) Dividir com `1-2`;
  - (c) Comprimir um PDF só texto e ver o aviso;
  - (d) PDF→Word;
  - (e) PDF→JPG;
  - (f) Imagens→PDF;
  - (g) trocar de Juntar para Imagens→PDF com a lista cheia, cancelar e ver o radio voltar;
  - (h) Cancelar no meio de um Dividir grande;
  - (i) tema escuro aplicado na lista nova.
  - Esperado: cada item se comporta como no spec, sem traceback no terminal.
- [ ] **Step 4: Commit** `feat(gui): aba Converter documentos`.

---

### Task 9: Empacotamento e documentação

**Files:**
- Modify: `main.spec`
- Modify: `README.md`

- [ ] **Step 1: `main.spec`.** Somar `collect_data_files("pdf2docx")` às `datas` existentes. Rodar `.venv/bin/pip install pyinstaller nodejs-wheel-binaries pytubefix && .venv/bin/pyinstaller main.spec --noconfirm`. Esperado: o build termina, e `dist/AnalisadorYoutube/_internal` contém `pymupdf` e `cv2`. Se o build reclamar de hiddenimports do pdf2docx/pymupdf, acrescentar os nomes indicados no erro e repetir. Esta verificação vale para Linux; o .exe do Windows fica marcado como **pendente de validação no Windows** no resumo final.
- [ ] **Step 2: README.**
  - Na intro, acrescentar "e converter documentos (PDF)".
  - Nova seção curta "Converter documentos": as 6 ferramentas numa tabela, a pasta `Convertidos`, a limitação de PDF escaneado e o que ficou fora (Word→PDF: usar "Salvar como PDF" do Word).
  - Na tabela "O que o instalador faz", acrescentar PyMuPDF/pdf2docx às bibliotecas.
- [ ] **Step 3: Verificação final.** `.venv/bin/python -m pytest -q` → tudo PASS. `git status` não pode mostrar `build/` nem `dist/` (já estão no `.gitignore`).
- [ ] **Step 4: Commit** `docs: documenta a aba Converter documentos`.
