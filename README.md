# Canivete Digital

Aplicativo com interface gráfica para **baixar vídeos e áudios do YouTube** (um ou vários de uma vez) e **transcrever arquivos de áudio em texto**. Também **junta, divide, comprime e converte PDFs** (PDF → Word, PDF → JPG, imagens → PDF), tudo no próprio computador.

[![My Skills](https://skillicons.dev/icons?i=py,vscode)](https://skillicons.dev)

---

## Instalação (para quem não é desenvolvedor)

Um comando só: ele instala tudo o que falta (Python, ffmpeg, bibliotecas), cria o atalho na Área de Trabalho e já abre o programa.

### Windows (10 ou 11)

**Requisitos:** internet e uns 15 minutos na primeira vez. **Não** precisa ser administrador nem ter nada instalado antes.

#### Opção 1 — Um comando só (recomendado)

1. Aperte a tecla **Windows**, digite **`PowerShell`** e abra o **Windows PowerShell** (a janela azul).
2. Copie o comando abaixo, cole na janela (clique com o botão direito do mouse) e aperte **Enter**:

   ```powershell
   irm https://raw.githubusercontent.com/LuixCarlos00/Canivete-Digital/main/instalar.ps1 | iex
   ```

3. Espere. O texto vai mostrando cada etapa (`==> ...`). **Não feche a janela** até aparecer:

   ```
   Pronto! Abra pelo atalho 'Canivete Digital' na Area de Trabalho.
   ```

   O programa abre sozinho no final.

#### Opção 2 — Baixando o projeto

1. Nesta página do GitHub, clique em **Code → Download ZIP**.
2. Clique com o botão direito no `.zip` baixado → **Extrair tudo...** → **Extrair**.
3. Dentro da pasta extraída, dê **duplo clique em `instalar.bat`**.
4. Se aparecer a tela azul **"O Windows protegeu o computador"**, clique em **Mais informações → Executar assim mesmo**. Isso acontece com qualquer script baixado da internet que não tem assinatura digital.
5. Espere até aparecer `Pronto!` e aperte qualquer tecla para fechar.

#### O que o instalador faz

| Etapa | Detalhe |
|---|---|
| Python | Instala o Python 3.12 só para o seu usuário, se ainda não tiver (via `winget` ou pelo site oficial python.org) |
| Programa | Copia o programa para `%LOCALAPPDATA%\Programs\CaniveteDigital` |
| Bibliotecas | Cria lá dentro um ambiente Python isolado com `pytubefix`, `SpeechRecognition`, `pydub`, `PyMuPDF`, `pdf2docx` e `Pillow` |
| ffmpeg | Baixa o ffmpeg (necessário para a transcrição) para dentro da pasta do programa |
| Atalhos | Cria **"Canivete Digital"** na Área de Trabalho e no Menu Iniciar |
| Desinstalação | Registra em **Configurações → Aplicativos → Aplicativos instalados** |

O atalho abre o programa pelo `pythonw.exe` (o Python oficial, que tem assinatura digital) em vez de um `.exe` gerado na hora. Assim ele não é barrado pelo **Controle Inteligente de Aplicativos** do Windows 11, que bloqueia programas sem assinatura.

Para **atualizar** para uma versão nova, é só rodar o instalador de novo. Ele substitui o programa, atualiza as bibliotecas (importante para acompanhar as mudanças do YouTube) e mantém o ffmpeg já baixado.

#### Versão portátil (.exe) para distribuir — só para o desenvolvedor

Na pasta do projeto, rode `instalar.bat -GerarPortatil`. Além de instalar, ele gera `dist\CaniveteDigital-windows.zip`, com um `CaniveteDigital.exe` que roda sem instalar nada.

> Esse `.exe` não tem assinatura digital, então computadores com Controle Inteligente de Aplicativos ou com regras de segurança da empresa **vão bloqueá-lo**. Para esses casos, use o instalador normal.

#### Problemas comuns no Windows

| Mensagem | Solução |
|---|---|
| `a execução de scripts foi desabilitada neste sistema` | Use a **Opção 2** (`instalar.bat`), que já libera a execução só para o instalador. |
| `Nao foi possivel instalar o Python` | Instale o Python manualmente em [python.org/downloads](https://www.python.org/downloads/) marcando **"Add python.exe to PATH"** e rode o instalador de novo. |
| `uma política de controle de aplicativo bloqueou esse arquivo` | É o Windows barrando um programa sem assinatura digital. Se apareceu numa versão antiga do instalador (a que gerava `.exe`), **rode o instalador de novo**: a versão atual não usa mais `.exe`. Se aparecer **dentro do programa** ao transcrever, quem foi bloqueado é o ffmpeg; veja a linha abaixo. |
| Transcrição falha com "O Windows bloqueou um programa auxiliar" | O **Controle Inteligente de Aplicativos** bloqueou o ffmpeg. Abra **Segurança do Windows → Controle de aplicativos e navegador → Configurações do Controle Inteligente de Aplicativos** e veja se está **Ativado**. Desligar é opção sua: depois de desligado, ele não pode ser religado sem reinstalar o Windows. Em computador de empresa, peça à TI para liberar o `ffmpeg.exe`. Baixar vídeos e áudios continua funcionando normalmente. |
| Antivírus bloqueou o `CaniveteDigital.exe` (versão portátil) | Executáveis gerados pelo PyInstaller às vezes são confundidos com vírus (falso positivo). Libere o arquivo no antivírus ou use o instalador normal. |
| Erro ao baixar (`HTTP 403`, `bot`, etc.) | O YouTube muda com frequência. Rode o instalador de novo para atualizar a biblioteca `pytubefix`. |
| Qualquer outro `ERRO:` em vermelho | Tire um print da janela e envie para o desenvolvedor. |

### Linux (e macOS)

**Requisitos:** internet e a senha do seu usuário (para instalar o Python e o ffmpeg, se faltarem). Funciona no Ubuntu, Linux Mint, Debian, Fedora, Arch, openSUSE e derivados. No macOS é preciso ter o [Homebrew](https://brew.sh).

#### Um comando só (recomendado)

1. Abra o **Terminal** (no Ubuntu e no Mint: aperte **`Ctrl` + `Alt` + `T`**).
2. Copie o comando abaixo, cole no terminal (**`Ctrl` + `Shift` + `V`**) e aperte **Enter**:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/LuixCarlos00/Canivete-Digital/main/instalar.sh | bash
   ```

   Se aparecer `curl: comando não encontrado`, use este no lugar:

   ```bash
   wget -qO- https://raw.githubusercontent.com/LuixCarlos00/Canivete-Digital/main/instalar.sh | bash
   ```

3. Se pedir a **senha**, digite a do seu usuário e aperte **Enter**. Nada aparece na tela enquanto você digita; é normal.
4. Espere as etapas (`==> ...`) terminarem e abra **"Canivete Digital"** pelo menu de aplicativos ou pela Área de Trabalho. Pelo terminal, o comando é `canivete-digital`.

#### Opção 2: com o projeto já baixado

Na pasta do projeto (baixada pelo **Code → Download ZIP** ou com `git clone`):

```bash
bash instalar.sh
```

Assim ele instala o código **dessa pasta**, em vez de baixar do GitHub.

#### O que o instalador faz

| Etapa | Detalhe |
|---|---|
| Sistema | Instala só o que faltar: Python 3 com `tkinter` e `venv`, e o `ffmpeg` (pelo `apt`, `dnf`, `pacman`, `zypper` ou `brew`) |
| Programa | Copia o programa para `~/.local/share/canivete-digital` |
| Bibliotecas | Cria lá dentro um ambiente Python isolado com as bibliotecas do `requirements.txt` |
| Atalhos | Cria **"Canivete Digital"** no menu de aplicativos e na Área de Trabalho, e o comando `canivete-digital` |

Para **atualizar**, rode o mesmo comando de novo: ele substitui o programa e atualiza as bibliotecas (importante para acompanhar as mudanças do YouTube).

#### Problemas comuns no Linux

| Mensagem | Solução |
|---|---|
| `curl: comando não encontrado` | Use o comando com `wget` acima, ou instale o curl: `sudo apt install curl` |
| `Gerenciador de pacotes nao reconhecido` | Instale manualmente Python 3 (com `tkinter` e `venv`) e o `ffmpeg`, depois rode o instalador com `--sem-sistema` (veja abaixo) |
| Atalho não aparece no menu | Saia e entre de novo na sessão, ou abra pelo terminal com `canivete-digital` |
| `canivete-digital: comando não encontrado` | A pasta `~/.local/bin` não está no `PATH`. Abra um terminal novo; se continuar, rode `~/.local/bin/canivete-digital` |

Para passar opções no modo "um comando só", use `bash -s --` antes delas:

```bash
curl -fsSL https://raw.githubusercontent.com/LuixCarlos00/Canivete-Digital/main/instalar.sh | bash -s -- --sem-sistema
```

### Desinstalar

- **Windows:** Configurações → Aplicativos instalados → *Canivete Digital* → Desinstalar
- **Linux/macOS:**

  ```bash
  curl -fsSL https://raw.githubusercontent.com/LuixCarlos00/Canivete-Digital/main/instalar.sh | bash -s -- --desinstalar
  ```

  Com o projeto baixado, também funciona `bash instalar.sh --desinstalar`.

Seus downloads e transcrições **não** são apagados.

---

## Funcionalidades

O programa tem três abas.

### Baixar vídeos e áudios
- Cole **um ou vários links de uma vez** (um por linha, ou separados por espaço/vírgula) e clique em **Adicionar**, ou use o botão **Colar**, que cola e adiciona direto.
- Os links vão para uma **lista**. Dá para remover os selecionados (tecla `Delete`) ou limpar tudo.
- Escolha **Vídeo** (MP4 em até 1080p, H.264, que abre em qualquer player) ou **Só o áudio** (M4A) e clique em **Baixar tudo**.

### Transcrever para texto
- Adicione **links do YouTube** e/ou **vários arquivos de áudio do computador de uma vez** (`mp3`, `mp4`, `m4a`, `wav`, `ogg`, `webm`; segure `Ctrl` para selecionar vários).
- O áudio é dividido em trechos **cortados nas pausas da fala**, para nenhuma palavra ser partida ao meio, e é lido já em qualidade de voz (mono, 16 kHz), o que permite transcrever aulas de horas sem pesar na memória.
- Para links, **não é preciso baixar o áudio antes**. Se o vídeo tiver **legenda em português**, o texto sai na hora. Se não tiver, o programa baixa o áudio em segundo plano, transcreve e apaga o áudio.
- Cada transcrição vira um `.txt` com o título do vídeo (ou o nome do arquivo) e também aparece na tela, com o botão **Copiar texto**.

### Converter documentos
Escolha a ferramenta, clique em **Escolher arquivos...** e depois em **Converter**. Nada sai do seu computador.

| Ferramenta | O que faz |
|---|---|
| **Juntar PDFs** | Um PDF só com todos os arquivos, **na ordem da lista** (use **Subir**/**Descer** para arrumar) |
| **Dividir PDF** | Cada página vira um PDF, ou só as páginas que você digitar (ex.: `1-3, 5`) |
| **Comprimir PDF** | Cópia menor do PDF, mostrando o tamanho antes e depois. Ajuda muito em PDF escaneado ou com fotos; se não der para diminuir pelo menos 5%, avisa e não gera cópia |
| **PDF → Word** | Gera um `.docx` editável. PDF escaneado (foto de papel) sai só com imagens, sem texto editável |
| **PDF → JPG** | Uma pasta com uma imagem por página |
| **Imagens → PDF** | Um PDF com as fotos (`jpg`, `png`) na ordem da lista, já giradas como aparecem no celular |

O arquivo original nunca é alterado. Para **Word → PDF**, use o próprio Word: **Arquivo → Salvar como → PDF**.

### Onde os arquivos ficam

Tudo fica na pasta **Downloads** do usuário:

```
Downloads/
└── Canivete Digital/
    ├── Videos/
    ├── Audios/
    ├── Transcricoes/
    └── Convertidos/
```

O botão **Abrir pasta dos arquivos** abre essa pasta.

> O programa se chamava **Analisador YouTube**. Quem já usava não perde nada: na primeira vez que o Canivete Digital abre, a pasta `Downloads/Analisador YouTube` é renomeada para `Downloads/Canivete Digital` com tudo dentro, e o instalador novo remove os atalhos antigos.

### Em todas as operações
- Botão **Cancelar** interrompe de verdade e apaga o arquivo incompleto.
- Em listas, um item com problema não interrompe os outros. No final aparece um resumo, e **os itens que falharam continuam na lista** para tentar de novo.
- Mensagens de erro em português (vídeo privado, removido, com restrição de idade etc.).
- A janela não trava durante o trabalho. Tem modo claro e modo escuro.

> Transcrever áudio (arquivos e vídeos sem legenda) usa o serviço gratuito de reconhecimento de fala do Google: precisa de internet, é mais lento e trechos com muito ruído podem se perder (o programa avisa quantos). Legendas automáticas do YouTube costumam vir sem pontuação.

---

## Para desenvolvedores

### Estrutura

```
main.py                  # ponto de entrada
analisador/
  config.py              # pastas de saída (dentro de Downloads), idioma, ffmpeg embutido
  utils.py               # validação de URL, parsing de listas, nomes de arquivo
  downloader.py          # download com progresso e cancelamento (pytubefix); vídeo = imagem + áudio juntados no ffmpeg
  transcriber.py         # transcrição de arquivo de áudio em trechos (SpeechRecognition + pydub)
  transcricao_youtube.py # transcrição a partir do link: legenda do YouTube ou áudio temporário
  lote_transcricao.py    # fila de transcrição (links e arquivos misturados), salva cada .txt
  ferramentas_pdf.py     # juntar, dividir, comprimir, PDF→Word/JPG, imagens→PDF (PyMuPDF, pdf2docx, Pillow)
  conversor.py           # fila de conversão: pasta temporária, cancelamento, nomes sem sobrescrever
  gui.py                 # interface Tkinter (threads se comunicam com a UI por fila)
tests/                   # testes unitários (pytest), sem acesso à rede
instalar.ps1 / .bat      # instalador Windows (gera .exe com PyInstaller)
instalar.sh              # instalador Linux/macOS
main.spec                # configuração do PyInstaller
```

### Rodando a partir do código

Requer Python 3.10+ com tkinter e o [ffmpeg](https://ffmpeg.org/download.html) no PATH.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python main.py
```

### Testes

```bash
python -m pytest
```

### Gerar o executável manualmente

```bash
pyinstaller main.spec --noconfirm
```

O resultado fica em `dist/CaniveteDigital/`. No Windows, o `instalar.ps1` faz isso e ainda instala.

---

## Ideias para o futuro

- Download de playlists inteiras
- Escolha de qualidade do vídeo (hoje é sempre a melhor até 1080p)
- Conversão do áudio para MP3
- Escolha do idioma da transcrição na interface
- Histórico de downloads

### Veja mais

- [Portfólio](https://luizcarlos-cv.netlify.app/)
