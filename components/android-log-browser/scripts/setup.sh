#!/usr/bin/env bash
set -euo pipefail

COMPONENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${COMPONENT_DIR}/../.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"

detect_shell() {
  local current_shell
  current_shell="$(basename "${SHELL:-}")"
  case "${current_shell}" in
    zsh|bash|fish)
      printf "%s" "${current_shell}"
      ;;
    *)
      printf "zsh"
      ;;
  esac
}

TARGET_SHELL="${1:-$(detect_shell)}"
case "${TARGET_SHELL}" in
  zsh|bash|fish) ;;
  *)
    echo "Unsupported shell '${TARGET_SHELL}'. Use one of: zsh, bash, fish."
    exit 1
    ;;
esac

echo "==> Component dir: ${COMPONENT_DIR}"
echo "==> Repo root: ${REPO_ROOT}"
echo "==> Using shell completion target: ${TARGET_SHELL}"

if [ ! -d "${VENV_DIR}" ]; then
  echo "==> Creating virtual environment at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
else
  echo "==> Reusing existing virtual environment at ${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "==> Upgrading pip"
python -m pip install --upgrade pip

echo "==> Installing android-log-browser in editable mode"
pip install -e "${COMPONENT_DIR}"

echo "==> Installing shell completion"
android-log-browser --install-completion "${TARGET_SHELL}" || true

echo
echo "Setup complete."
echo "To use immediately in current terminal, run:"
echo "  source \"${VENV_DIR}/bin/activate\""
echo "  exec ${TARGET_SHELL}"
