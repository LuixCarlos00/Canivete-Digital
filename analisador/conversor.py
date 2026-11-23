"""Conversão de documentos em lote: escolhe a ferramenta, usa pasta temporária e junta os resultados.

Tudo é gerado numa pasta temporária e só vai para a pasta do usuário quando está completo,
então cancelamentos e falhas nunca deixam arquivo pela metade nem sobrescrevem outro.
"""

import os
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime

from .downloader import mover_sem_sobrescrever, pasta_temporaria
from .ferramentas_pdf import (
    ConversaoCancelada,
    ErroDocumento,
    comprimir_pdf,
    dividir_pdf,
    imagens_para_pdf,
    interpretar_intervalo,
    juntar_pdfs,
    normalizar_intervalo,
    pdf_para_jpg,
    pdf_para_word,
)
from .utils import caminho_sem_conflito, formatar_tamanho, garantir_pasta, mensagem_de_erro_amigavel

JUNTAR = "juntar"
DIVIDIR = "dividir"
COMPRIMIR = "comprimir"
PDF_WORD = "pdf_word"
PDF_JPG = "pdf_jpg"
IMAGENS_PDF = "imagens_pdf"

# Ordem = ordem dos botões na tela.
FERRAMENTAS = {
    JUNTAR: "Juntar PDFs",
    DIVIDIR: "Dividir PDF",
    COMPRIMIR: "Comprimir PDF",
    PDF_WORD: "PDF → Word",
    PDF_JPG: "PDF → JPG",
    IMAGENS_PDF: "Imagens → PDF",
}

EXTENSOES_PDF = ("*.pdf",)
EXTENSOES_IMAGEM = ("*.jpg", "*.jpeg", "*.png")

# Abaixo de 5% de redução a cópia "comprimida" seria praticamente igual ao original.
GANHO_MINIMO_COMPRESSAO = 0.05

AVISO_SEM_GANHO = "já estava otimizado, nenhuma cópia gerada"
AVISO_ESCANEADO = "parece ser um PDF escaneado; o Word terá só imagens"

_PREFIXO_TEMPORARIO = "analisador-conversao-"  # começa com "analisador-": limpar_sobras_temporarias acha


def extensoes_da_ferramenta(ferramenta):
    """Extensões aceitas pela ferramenta, no formato do diálogo de abrir arquivo.

    Args:
        ferramenta (str): uma das constantes de ``FERRAMENTAS``.

    Returns:
        tuple[str, ...]: ex.: ("*.pdf",).
    """
    return EXTENSOES_IMAGEM if ferramenta == IMAGENS_PDF else EXTENSOES_PDF


def arquivo_compativel(ferramenta, caminho):
    """Diz se o arquivo serve para a ferramenta (pela extensão, sem diferenciar maiúsculas).

    Args:
        ferramenta (str): uma das constantes de ``FERRAMENTAS``.
        caminho (str): arquivo.

    Returns:
        bool: True se a extensão é aceita.
    """
    extensao = os.path.splitext(caminho)[1].lower()
    return f"*{extensao}" in extensoes_da_ferramenta(ferramenta)


@dataclass
class ItemConvertido:
    """Resultado de uma conversão bem-sucedida.

    Attributes:
        origens (tuple[str, ...]): arquivos de entrada (vários em Juntar e Imagens→PDF).
        saidas (list[str]): arquivos/pastas gerados (vazio quando não valeu a pena gerar).
        aviso (str): algo que o usuário precisa saber, mesmo com sucesso.
        detalhe (str): informação extra (ex.: tamanho antes → depois).
    """

    origens: tuple
    saidas: list
    aviso: str = ""
    detalhe: str = ""


class ConversorEmLote:
    """Executa uma ferramenta sobre a lista de arquivos, um por vez (ou todos juntos, quando é o caso).

    Um arquivo com problema não interrompe os outros; o cancelamento interrompe tudo.
    """

    def __init__(self, pasta_saida, agora=datetime.now, comprimir=comprimir_pdf):
        """
        Args:
            pasta_saida (str): pasta onde os resultados são salvos.
            agora (Callable[[], datetime]): data/hora usada nos nomes; injetável para testes.
            comprimir (Callable[..., tuple[int, int]]): função de compressão; injetável para testes.
        """
        self.pasta_saida = pasta_saida
        self._agora = agora
        self._comprimir = comprimir
        self._cancelar = threading.Event()

    def cancelar(self):
        """Interrompe a conversão na próxima página/arquivo."""
        self._cancelar.set()

    def _verificar(self):
        if self._cancelar.is_set():
            raise ConversaoCancelada()

    def converter(self, ferramenta, arquivos, intervalo_texto="", ao_progredir=None, ao_iniciar_item=None):
        """Converte a lista de arquivos com a ferramenta escolhida.

        Args:
            ferramenta (str): uma das constantes de ``FERRAMENTAS``.
            arquivos (list[str]): arquivos de entrada, na ordem da lista.
            intervalo_texto (str): só em Dividir; vazio = cada página vira um PDF.
            ao_progredir (Callable[[float], None] | None): progresso do item atual (0-100).
            ao_iniciar_item (Callable[[int, int, str], None] | None): (índice, total, arquivo).

        Returns:
            tuple[list[ItemConvertido], list[tuple[str, str]]]: (sucessos, falhas como
            (arquivo, mensagem)); em operações únicas o arquivo da falha pode ser "".

        Raises:
            ConversaoCancelada: o usuário cancelou.
        """
        self._verificar()
        if ferramenta in (JUNTAR, IMAGENS_PDF):
            return self._operacao_unica(ferramenta, arquivos, ao_progredir)

        paginas, rotulo = None, ""
        if ferramenta == DIVIDIR and intervalo_texto.strip():
            try:
                paginas, rotulo = interpretar_intervalo(intervalo_texto), normalizar_intervalo(intervalo_texto)
            except ErroDocumento as erro:
                return [], [("", str(erro))]

        sucessos, falhas = [], []
        try:
            for indice, caminho in enumerate(arquivos, start=1):
                self._verificar()
                if ao_iniciar_item:
                    ao_iniciar_item(indice, len(arquivos), caminho)
                try:
                    sucessos.append(self._converter_um(ferramenta, caminho, paginas, rotulo, ao_progredir))
                except ConversaoCancelada:
                    raise
                except ErroDocumento as erro:
                    falhas.append((caminho, str(erro)))
                except Exception as erro:  # noqa: BLE001 - um arquivo ruim não deve parar o lote
                    if self._cancelar.is_set():
                        raise ConversaoCancelada() from erro
                    falhas.append((caminho, mensagem_de_erro_amigavel(erro)))
        except ConversaoCancelada as cancelamento:
            # Leva junto o que já foi salvo, para a tela tirar esses itens da lista e avisar o usuário.
            raise ConversaoCancelada(sucessos) from cancelamento
        return sucessos, falhas

    def _opcoes(self, ao_progredir):
        return {"ao_progredir": ao_progredir, "verificar_cancelamento": self._verificar}

    def _operacao_unica(self, ferramenta, arquivos, ao_progredir):
        if ferramenta == JUNTAR and len(arquivos) < 2:
            return [], [("", "Escolha pelo menos 2 PDFs para juntar.")]
        prefixo = "PDFs juntados" if ferramenta == JUNTAR else "Imagens"
        nome = f"{prefixo}_{self._agora():%Y-%m-%d_%H-%M-%S}.pdf"
        funcao = juntar_pdfs if ferramenta == JUNTAR else imagens_para_pdf
        try:
            with pasta_temporaria(_PREFIXO_TEMPORARIO) as temp:
                destino_temp = os.path.join(temp, nome)
                funcao(list(arquivos), destino_temp, **self._opcoes(ao_progredir))
                final = mover_sem_sobrescrever(destino_temp, self.pasta_saida, nome)
        except ConversaoCancelada:
            raise
        except ErroDocumento as erro:
            return [], [(erro.arquivo or "", str(erro))]
        except Exception as erro:  # noqa: BLE001 - erro inesperado (disco cheio, permissão...) vira falha visível
            if self._cancelar.is_set():
                raise ConversaoCancelada() from erro
            return [], [("", mensagem_de_erro_amigavel(erro))]
        return [ItemConvertido(tuple(arquivos), [final])], []

    def _converter_um(self, ferramenta, caminho, paginas, rotulo, ao_progredir):
        nome = os.path.splitext(os.path.basename(caminho))[0]
        opcoes = self._opcoes(ao_progredir)
        with pasta_temporaria(_PREFIXO_TEMPORARIO) as temp:
            if ferramenta == DIVIDIR:
                gerados = dividir_pdf(caminho, temp, paginas=paginas, rotulo=rotulo, **opcoes)
                return ItemConvertido((caminho,), self._mover_todos(gerados))

            if ferramenta == COMPRIMIR:
                destino = os.path.join(temp, f"{nome} (comprimido).pdf")
                antes, depois = self._comprimir(caminho, destino, **opcoes)
                if depois > antes * (1 - GANHO_MINIMO_COMPRESSAO):
                    return ItemConvertido((caminho,), [], aviso=AVISO_SEM_GANHO)
                detalhe = f"antes {formatar_tamanho(antes)} → depois {formatar_tamanho(depois)}"
                return ItemConvertido((caminho,), self._mover_todos([destino]), detalhe=detalhe)

            if ferramenta == PDF_WORD:
                destino = os.path.join(temp, f"{nome}.docx")
                tem_texto = pdf_para_word(caminho, destino, **opcoes)
                return ItemConvertido((caminho,), self._mover_todos([destino]),
                                      aviso="" if tem_texto else AVISO_ESCANEADO)

            if ferramenta == PDF_JPG:
                pasta_imagens = os.path.join(temp, nome)
                pdf_para_jpg(caminho, pasta_imagens, **opcoes)
                self._verificar()
                destino = caminho_sem_conflito(garantir_pasta(self.pasta_saida), nome)
                shutil.move(pasta_imagens, destino)
                return ItemConvertido((caminho,), [destino])

        raise ValueError(f"Ferramenta desconhecida: {ferramenta}")

    def _mover_todos(self, gerados):
        """Move os arquivos prontos da pasta temporária para a pasta do usuário, sem sobrescrever."""
        self._verificar()
        return [mover_sem_sobrescrever(arquivo, self.pasta_saida, os.path.basename(arquivo)) for arquivo in gerados]
