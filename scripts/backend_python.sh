#!/usr/bin/env bash

backend_python_has_runtime_dependencies() {
  local candidate="$1"
  [[ -x "$candidate" ]] || return 1
  "$candidate" -c "import fastapi, langgraph, sqlalchemy, uvicorn" >/dev/null 2>&1
}

select_backend_python() {
  local backend_dir="$1"
  local candidate
  local candidates=()

  if [[ -n "${BACKEND_PYTHON:-}" ]]; then
    candidates+=("$BACKEND_PYTHON")
  fi
  candidates+=(
    "$backend_dir/.venv311/bin/python"
    "$backend_dir/.venv312/bin/python"
    "$backend_dir/.venv/bin/python"
  )

  for candidate in "${candidates[@]}"; do
    if backend_python_has_runtime_dependencies "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}
