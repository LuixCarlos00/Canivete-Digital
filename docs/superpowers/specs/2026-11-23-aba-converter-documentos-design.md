# Design: aba "Converter documentos"

Data: 2026-11-23 · Status: aguardando aprovação

## Intenção e porquê

O app (Tkinter, Python) hoje baixa vídeos/áudios do YouTube e transcreve áudio. O dono quer
uma terceira aba para converter e manipular documentos, no estilo das ferramentas do iLovePDF,
**rodando localmente**, para uso da **família** (usuários leigos). O objetivo é comodidade: não
depender de sites online para tarefas comuns com PDF.

## Escopo

### Metas (6 ferramentas)

| Ferramenta | Entrada | Saída |
|---|---|---|
| Juntar PDFs | 2+ PDFs | 1 PDF com todos, **na ordem da lista** |
| Dividir PDF | 1+ PDFs | Modo A: cada página num PDF. Modo B: só as páginas digitadas (ex.: `1-3, 5`) num PDF novo |
| Comprimir PDF | 1+ PDFs | 1 PDF menor por arquivo; informa tamanho antes → depois |
| PDF → Word | 1+ PDFs | 1 `.docx` por PDF |
| PDF → JPG | 1+ PDFs | Uma pasta por PDF (nome do PDF), 1 JPG por página |
| Imagens → PDF | 1+ imagens JPG/PNG | 1 PDF com todas as imagens, na ordem da lista |

### Fora do escopo (decidido com o dono)

- Word/PowerPoint/Excel → PDF (exige LibreOffice ou MS Office instalado: pesado demais).
- PDF → PowerPoint, PDF → Excel, HTML → PDF.
- OCR (texto de PDF escaneado). PDF escaneado convertido para Word sai sem texto editável.
- Mudanças nas abas Baixar e Transcrever.
- Renomear o app.

### Anti-metas (seria falha mesmo "funcionando")

- Enviar documentos para qualquer serviço online.
- Exigir que o usuário instale programa extra além do instalador atual.
- Sobrescrever ou alterar arquivos originais do usuário.
- Travar a janela durante uma conversão longa.

## Restrições

- Tem que funcionar em Windows, Linux e macOS (mesmos instaladores atuais, que instalam via `requirements.txt`).
- Usuários leigos: mensagens em português claro, sem jargão; erros nunca mostram traceback.
- Seguir os padrões do projeto: lógica sem dependência de interface, dependências injetáveis, docstrings
  no formato atual (Args/Returns/Raises), testes pytest, threads de trabalho nunca tocam na interface
  (fila `_na_ui`), cancelamento via `threading.Event`.

## Abordagens consideradas

1. **PyMuPDF + pdf2docx (escolhida).** PyMuPDF faz juntar, dividir, comprimir, PDF→JPG e
   imagens→PDF sem binário externo; pdf2docx faz PDF→Word e já depende do PyMuPDF. Nada extra a
   instalar. Licença AGPL: aceitável porque o repositório é público e o uso é familiar.
   **Tamanho real (verificado no PyPI em 2026-11-23):** pdf2docx 0.5.13 puxa `opencv-python-headless`
   (~47 MB), `numpy`, `python-docx`, `fonttools` e `fire`; somando o PyMuPDF, são **~100 MB** a mais na
   instalação (a estimativa inicial de ~30 MB estava errada).
2. pypdf + Pillow + pdf2image: descartada. PDF→JPG exigiria o Poppler (binário externo a baixar pelo
   instalador) e o pdf2docx traria o PyMuPDF de qualquer forma.
3. Serviços/APIs online: descartada (anti-meta de privacidade e de rodar local).

## Decisões de design

### Interface (terceira aba, "Converter documentos")

```
1. Escolha o que fazer
   (•) Juntar PDFs   ( ) Dividir PDF   ( ) Comprimir PDF
   ( ) PDF → Word    ( ) PDF → JPG     ( ) Imagens → PDF

2. Adicione os arquivos                    [Escolher arquivos...]
   [ lista de arquivos ]
   [Subir] [Descer] [Remover selecionados] [Limpar lista]   N arquivo(s) na lista

   (só aparece em Dividir)  (•) Cada página vira um PDF
                            ( ) Só as páginas: [______]

                                                 [ Converter ]
```

- Usa o rodapé existente (barra de progresso, status, Cancelar, Abrir pasta).
- Reaproveita `ListaDeItens`, acrescentando **Subir/Descer** (a ordem importa em Juntar e Imagens→PDF).
  Os botões novos só precisam existir nessa aba.
- O filtro do "Escolher arquivos..." muda conforme a ferramenta: PDFs, ou imagens (`*.jpg *.jpeg *.png`)
  para Imagens→PDF.
- **Trocar de ferramenta com arquivos incompatíveis na lista** (ex.: PDFs na lista e o usuário escolhe
  Imagens→PDF): a lista é esvaziada após confirmação ("Trocar de ferramenta vai limpar a lista. Continuar?").
  Se todos os arquivos forem compatíveis, a lista é mantida.
- Validações antes de começar (aviso em messagebox, nada roda):
  - lista vazia;
  - Juntar com menos de 2 PDFs;
  - Dividir no modo "Só as páginas" com texto vazio ou inválido.
- Ao terminar: messagebox com resumo (sucessos, falhas com motivo), igual às outras abas, e abre a pasta
  de saída. Itens com sucesso saem da lista; falhas ficam para tentar de novo.

### Comportamento de cada ferramenta

- **Saída:** `config.PASTA_CONVERTIDOS = <PASTA_BASE>/Convertidos`. Nada é sobrescrito
  (`caminho_sem_conflito` para arquivos; para pastas do PDF→JPG, mesmo esquema " (2)").
- **Nomes de saída:**
  - Juntar: `PDFs juntados_<AAAA-MM-DD_HH-MM-SS>.pdf`.
  - Dividir modo A: `<nome> - pagina 01.pdf` … (número com zeros à esquerda conforme o total de páginas).
  - Dividir modo B: `<nome> - paginas 1-3, 5.pdf`.
  - Comprimir: `<nome> (comprimido).pdf`.
  - PDF→Word: `<nome>.docx`.
  - PDF→JPG: pasta `<nome>/` com `pagina 01.jpg` …
  - Imagens→PDF: `Imagens_<AAAA-MM-DD_HH-MM-SS>.pdf`.
- **Intervalo de páginas (Dividir modo B):** aceita números e faixas separados por vírgula/espaço
  (`1-3, 5`, `2,4,6`, `7-7`), 1-based, na ordem digitada, sem repetir página. Página fora do total do
  arquivo → erro daquele arquivo ("O arquivo tem 4 páginas; a página 9 não existe."). A regra vale para
  cada PDF da lista independentemente.
- **Comprimir:** salvar com limpeza de objetos não usados + compressão de streams e recompressão das
  imagens internas (JPEG de qualidade ~75, reduzindo imagens acima de ~150 DPI). Se o resultado não
  for menor que o original, o arquivo novo é apagado e o item conta como sucesso com aviso
  "já estava otimizado, nenhuma cópia gerada".
- **PDF→JPG:** renderiza a 150 DPI, qualidade JPEG ~85.
- **Imagens→PDF:** cada imagem vira uma página do tamanho da própria imagem (sem margens), mantendo
  a orientação. PNG com transparência recebe fundo branco.
- **PDF→Word:** pdf2docx. Se o PDF não tiver texto extraível em nenhuma página, o item conta como
  sucesso com aviso "parece ser um PDF escaneado; o Word terá só imagens".
- **PDF protegido por senha:** erro do item, mensagem "Este PDF é protegido por senha." (não pede senha).
- **Arquivo corrompido / não é PDF:** erro do item, mensagem "Não foi possível abrir este arquivo como PDF."

### Lote, progresso e cancelamento

- Juntar e Imagens→PDF são **uma operação só** sobre a lista inteira (falha em qualquer arquivo
  aborta a operação, informando qual arquivo deu problema; nada é salvo pela metade).
- As outras quatro processam **um arquivo por vez**; um arquivo com erro não para os outros.
- Progresso por página quando possível (Dividir, Comprimir, PDF→JPG, Juntar). PDF→Word: pdf2docx não
  dá callback granular; o progresso avança por arquivo.
- Cancelar: checado entre páginas/arquivos. Arquivos parciais nunca ficam na pasta do usuário: gerar
  em pasta temporária (`pasta_temporaria`) e mover só quando completo, como o downloader já faz.

### Código

- Novo módulo `analisador/conversor.py`, sem Tkinter: uma função/método por ferramenta, um
  orquestrador de lote com `cancelar()` (mesma interface usada por `_iniciar_tarefa`), e o parser de
  intervalo de páginas como função pura.
- `gui.py`: nova aba montada no mesmo padrão das existentes. Se o arquivo crescer demais, a aba
  pode ir para módulo próprio (decisão do implementador).
- `utils.mensagem_de_erro_amigavel`: estender para os erros de PDF listados acima.
- `requirements.txt`: `pymupdf>=1.26.7,<2` e `pdf2docx>=0.5.13`. **O teto `<2` é obrigatório:** o PyMuPDF
  2.x exige Python ≥ 3.11 (o `instalar.sh` aceita 3.10) e não publica wheel (pacote pronto) para macOS
  Intel. Sem o teto, o pip escolheria a 2.x e tentaria compilar do código-fonte, quebrando o instalador.
  A série 1.28.x tem wheels para Windows x64/ARM, Linux x86_64/ARM e macOS Intel/ARM, Python ≥ 3.10.
- `main.spec`: conferir se PyMuPDF/pdf2docx precisam de `collect_data_files`/hiddenimports no .exe portátil.
- Testes em `tests/test_conversor.py`: geram PDFs e imagens na hora com PyMuPDF (sem arquivos binários
  no repositório). Cobrir: casos normais de cada ferramenta, parser de intervalos (válidos, inválidos,
  extremos), PDF com senha, arquivo não-PDF, cancelamento no meio, não sobrescrever saída existente,
  comprimir sem ganho.
- README: seção curta da nova aba e da pasta `Convertidos`.

## Decisões tomadas após a revisão (calls do designer, não do dono)

1. **PDF→Word com falha ou saída vazia:** qualquer exceção do pdf2docx vira erro do item com a mensagem
   "Não foi possível converter este PDF para Word." (detalhe técnico só no log). Depois de converter,
   reabrir o `.docx`; se estiver ilegível, é erro (e o arquivo não é entregue). O aviso de "PDF escaneado"
   continua valendo como sucesso com aviso.
2. **Juntar / Imagens→PDF com erro:** a lista fica intacta, nada é salvo, e a mensagem nomeia o arquivo
   culpado e o motivo (inclusive PDF com senha). Com sucesso, a lista inteira é limpa. O orquestrador
   devolve um resultado único para essas duas ferramentas e resultados por item para as outras quatro.
3. **Imagens→PDF:** respeitar a rotação EXIF (a foto sai como o usuário a vê no celular). Converter CMYK/
   paleta/transparência para RGB com fundo branco. Página com as **proporções** da imagem, mas escalada
   para o lado maior ter o tamanho do lado maior de uma A4 (842 pt), para fotos de 12 MP não virarem
   páginas de 1,4 m. A imagem é inserida na resolução original (sem perda).
4. **Comprimir:** só conta como "comprimido" se ficar pelo menos **5% menor**; abaixo disso, apagar a cópia
   e avisar "já estava otimizado".
5. **Intervalo de páginas:** espaços em volta do hífen são aceitos (`1 - 3`); faixa invertida (`3-1`), zero,
   negativo ou texto é inválido. O nome do arquivo usa a forma normalizada (`paginas 1-3,5`).
6. **Trocar de ferramenta:** as cinco ferramentas de PDF são compatíveis entre si (lista e ordem mantidas);
   só a troca de/para Imagens→PDF com itens incompatíveis pede confirmação e limpa a lista.

## Deixado para o implementador

- Estender `ListaDeItens` com parâmetro opcional (ex.: `com_ordenacao=False`) ou subclasse.

- Estrutura interna do `conversor.py` (classes vs funções) dentro dos padrões acima.
- Parâmetros finos de compressão/qualidade, desde que respeitem as faixas descritas.
- Layout exato (paddings, posição dos botões), seguindo o visual das abas existentes.
