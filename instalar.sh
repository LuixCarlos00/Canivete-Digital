#!/usr/bin/env bash
# Instalador "um comando so" do Canivete Digital para Linux e macOS.
#
# Um comando so (sem baixar nada antes):
#   curl -fsSL https://raw.githubusercontent.com/LuixCarlos00/Canivete-Digital/main/instalar.sh | bash
# Com o projeto ja baixado:
#   bash instalar.sh
# Opcoes:
#   --desinstalar   remove o app (mantem seus downloads e transcricoes)
#   --sem-sistema   nao instala pacotes do sistema (python3-tk, ffmpeg...), so o app
#
# O que ele faz:
#   1. Instala o que faltar no sistema: Python 3 (com venv e tkinter) e ffmpeg (pede sua senha via sudo).
#   2. Copia o app para ~/.local/share/canivete-digital e cria um ambiente Python isolado nele.
#   3. Cria o comando "canivete-digital" e o atalho no menu de aplicativos / Area de Trabalho.
set -euo pipefail

REPOSITORIO="LuixCarlos00/Canivete-Digital"
NOME_ATALHO="Canivete Digital"
PASTA_APP="${CANIVETE_DIR:-$HOME/.local/share/canivete-digital}"
PASTA_BIN="$HOME/.local/bin"
LANCADOR="$PASTA_BIN/canivete-digital"
ARQUIVO_DESKTOP="$HOME/.local/share/applications/canivete-digital.desktop"

etapa() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
ok()    { printf '    \033[32m%s\033[0m\n' "$1"; }
erro()  { printf '\n\033[1;31mERRO: %s\033[0m\n' "$1" >&2; exit 1; }

pasta_desktop() {
    if command -v xdg-user-dir >/dev/null 2>&1; then xdg-user-dir DESKTOP; else echo "$HOME/Desktop"; fi
}

# Nome usado ate 2026-11 ("Analisador YouTube"): removido para nao ficar atalho duplicado.
remover_versao_antiga() {
    local antiga="$HOME/.local/share/analisador-youtube"
    rm -f "$PASTA_BIN/analisador-youtube" "$HOME/.local/share/applications/analisador-youtube.desktop" \
          "$(pasta_desktop)/analisador-youtube.desktop" "$HOME/Desktop/Analisador YouTube.command"
    if [[ -d "$antiga" ]]; then
        rm -rf "$antiga"
        ok "Versao antiga (Analisador YouTube) removida. Seus arquivos em Downloads foram mantidos."
    fi
}

desinstalar() {
    etapa "Desinstalando $NOME_ATALHO"
    rm -rf "$PASTA_APP" "$LANCADOR" "$ARQUIVO_DESKTOP" \
           "$(pasta_desktop)/canivete-digital.desktop" "$HOME/Desktop/$NOME_ATALHO.command"
    remover_versao_antiga
    ok "Removido. Seus videos, audios, transcricoes e documentos foram mantidos."
}

SEM_SISTEMA=0
for arg in "$@"; do
    case "$arg" in
        --desinstalar) desinstalar; exit 0 ;;
        --sem-sistema) SEM_SISTEMA=1 ;;
        *) erro "Opcao desconhecida: $arg" ;;
    esac
done

# ------------------------------------------------------------ codigo-fonte
# Rodando via "curl | bash" nao existe arquivo do script: baixa o projeto do GitHub.
ORIGEM=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "$(dirname "${BASH_SOURCE[0]}")/main.py" ]]; then
    ORIGEM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    etapa "Baixando o codigo do GitHub"
    TEMP_FONTE="$(mktemp -d)"
    trap 'rm -rf "$TEMP_FONTE"' EXIT
    curl -fsSL "https://github.com/$REPOSITORIO/archive/refs/heads/main.tar.gz" | tar -xz -C "$TEMP_FONTE"
    ORIGEM="$(find "$TEMP_FONTE" -mindepth 1 -maxdepth 1 -type d | head -n1)"
    ok "Codigo em $ORIGEM"
fi

# --------------------------------------------------------- pacotes do sistema
python_ok() {
    command -v python3 >/dev/null 2>&1 &&
    python3 -c 'import sys, tkinter, venv, ensurepip; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1
}

# Instala so o que falta: pedir "ffmpeg" quando ja existe outro ffmpeg instalado
# (ex.: Fedora com RPM Fusion) gera conflito de pacotes e aborta a instalacao.
instalar_pacotes_sistema() {
    local sudo_cmd="" precisa_python=0 precisa_ffmpeg=0
    [[ "$(id -u)" -ne 0 ]] && sudo_cmd="sudo"
    python_ok || precisa_python=1
    command -v ffmpeg >/dev/null 2>&1 || precisa_ffmpeg=1

    local pkgs_python=() pkg_ffmpeg="" instalar=()
    if [[ "$(uname)" == "Darwin" ]]; then
        command -v brew >/dev/null 2>&1 || erro "Instale o Homebrew (https://brew.sh) e rode de novo."
        pkgs_python=(python python-tk); pkg_ffmpeg=ffmpeg
    elif command -v apt-get >/dev/null 2>&1; then
        pkgs_python=(python3 python3-venv python3-pip python3-tk); pkg_ffmpeg=ffmpeg
    elif command -v dnf >/dev/null 2>&1; then
        pkgs_python=(python3 python3-tkinter); pkg_ffmpeg=ffmpeg-free
    elif command -v pacman >/dev/null 2>&1; then
        pkgs_python=(python tk); pkg_ffmpeg=ffmpeg
    elif command -v zypper >/dev/null 2>&1; then
        pkgs_python=(python3 python3-tk); pkg_ffmpeg=ffmpeg
    else
        erro "Gerenciador de pacotes nao reconhecido. Instale Python 3 (com tkinter e venv) e ffmpeg manualmente."
    fi
    [[ "$precisa_python" -eq 1 ]] && instalar+=("${pkgs_python[@]}")
    [[ "$precisa_ffmpeg" -eq 1 ]] && instalar+=("$pkg_ffmpeg")
    [[ "${#instalar[@]}" -eq 0 ]] && return 0
    ok "Pacotes: ${instalar[*]}"

    if [[ "$(uname)" == "Darwin" ]]; then
        brew install "${instalar[@]}"
    elif command -v apt-get >/dev/null 2>&1; then
        $sudo_cmd apt-get update
        $sudo_cmd apt-get install -y "${instalar[@]}"
    elif command -v dnf >/dev/null 2>&1; then
        $sudo_cmd dnf install -y "${instalar[@]}"
    elif command -v pacman >/dev/null 2>&1; then
        $sudo_cmd pacman -S --needed --noconfirm "${instalar[@]}"
    else
        $sudo_cmd zypper install -y "${instalar[@]}"
    fi
}

etapa "Verificando Python, tkinter e ffmpeg"
if python_ok && command -v ffmpeg >/dev/null 2>&1; then
    ok "Tudo presente"
elif [[ "$SEM_SISTEMA" -eq 1 ]]; then
    python_ok || erro "Falta Python 3.10+ com tkinter/venv (rode sem --sem-sistema para instalar)."
    ok "ffmpeg ausente: a transcricao nao vai funcionar ate instala-lo (--sem-sistema ativo)."
else
    ok "Instalando o que falta (pode pedir sua senha)"
    instalar_pacotes_sistema
    python_ok || erro "Python 3.10+ com tkinter/venv continua indisponivel (sua distribuicao pode ter um Python antigo demais)."
fi

# ------------------------------------------------------------------- app
etapa "Instalando o app em $PASTA_APP"
mkdir -p "$PASTA_APP"
rm -rf "$PASTA_APP/analisador"
cp -R "$ORIGEM/analisador" "$ORIGEM/main.py" "$ORIGEM/requirements.txt" "$PASTA_APP/"
[[ -x "$PASTA_APP/.venv/bin/python" ]] || python3 -m venv "$PASTA_APP/.venv"
"$PASTA_APP/.venv/bin/python" -m pip install --upgrade pip --quiet --disable-pip-version-check
"$PASTA_APP/.venv/bin/python" -m pip install -r "$PASTA_APP/requirements.txt" --quiet --disable-pip-version-check
ok "Dependencias instaladas"

# O app compara esse commit com o da branch main no GitHub para saber se ha versao nova.
commit=""
if [[ -d "$ORIGEM/.git" ]] && command -v git >/dev/null 2>&1; then
    commit="$(git -C "$ORIGEM" rev-parse HEAD 2>/dev/null || true)"
fi
if [[ -z "$commit" ]]; then
    commit="$(curl -fsSL -H 'Accept: application/vnd.github+json' -H 'User-Agent: Canivete Digital' \
        "https://api.github.com/repos/$REPOSITORIO/commits/main" | python3 -c \
        'import sys, json; print(json.load(sys.stdin).get("sha", ""))' 2>/dev/null || true)"
fi
if [[ -n "$commit" ]]; then
    printf '{"commit":"%s","repositorio":"%s","atualizado_em":"%s"}\n' \
        "$commit" "$REPOSITORIO" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$PASTA_APP/versao.json"
fi

# So agora, com o app novo funcionando, a versao antiga sai: se algo falhar antes, ela continua usavel.
remover_versao_antiga

etapa "Criando atalhos"
mkdir -p "$PASTA_BIN"
cat > "$LANCADOR" <<EOF
#!/usr/bin/env bash
exec "$PASTA_APP/.venv/bin/python" "$PASTA_APP/main.py" "\$@"
EOF
chmod +x "$LANCADOR"
ok "Comando: $LANCADOR"

if [[ "$(uname)" == "Darwin" ]]; then
    mkdir -p "$HOME/Desktop"
    printf '#!/bin/bash\n"%s"\n' "$LANCADOR" > "$HOME/Desktop/$NOME_ATALHO.command"
    chmod +x "$HOME/Desktop/$NOME_ATALHO.command"
    ok "Atalho na Mesa: $NOME_ATALHO.command"
else
    mkdir -p "$(dirname "$ARQUIVO_DESKTOP")"
    cat > "$ARQUIVO_DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=$NOME_ATALHO
Comment=Baixar videos e audios do YouTube, transcrever falas e converter PDFs
Exec="$LANCADOR"
Icon=applications-utilities
Terminal=false
Categories=AudioVideo;Office;Utility;
EOF
    chmod +x "$ARQUIVO_DESKTOP"
    ok "Atalho no menu de aplicativos"

    DESKTOP_DIR="$(pasta_desktop)"
    if [[ -d "$DESKTOP_DIR" ]]; then
        cp "$ARQUIVO_DESKTOP" "$DESKTOP_DIR/"
        # GNOME so permite abrir atalhos da Area de Trabalho marcados como confiaveis.
        gio set "$DESKTOP_DIR/canivete-digital.desktop" metadata::trusted true 2>/dev/null || true
        ok "Atalho na Area de Trabalho"
    fi
fi

case ":$PATH:" in
    *":$PASTA_BIN:"*) ;;
    *) ok "Dica: adicione $PASTA_BIN ao PATH para usar o comando 'canivete-digital' no terminal." ;;
esac

printf '\n\033[1;32mPronto! Abra "%s" pelo menu de aplicativos ou pela Area de Trabalho.\033[0m\n' "$NOME_ATALHO"
