# ---------------------------------------------------------------------------------------------------------------------
# Private vars

_red := '\033[1;31m'
_cyan := '\033[1;36m'
_green := '\033[1;32m'
_yellow := '\033[1;33m'
_nc := '\033[0m'

# ---------------------------------------------------------------------------------------------------------------------
# Aliases

alias ca := client-alice
alias cb := client-bob
alias ss := syftbox-server
alias jup := jupyter
alias c := clean

# ---------------------------------------------------------------------------------------------------------------------
# Commands

# Default recipe
default:
    @just --list

jupyter jupyter_args="":
    uv sync

    uv run --frozen --with "jupyterlab" \
        jupyter lab {{ jupyter_args }}

# rpc-server config="":
#     uv sync
#     if [ -n "{{ config }}" ]; then \
#         uv run service.py --server-only --config "{{ config }}"; \
#     else \
#         echo "{{ _yellow }}No config specified. Using default config.{{ _nc }}"; \
#         uv run service.py --server-only; \
#     fi

# rpc-client datasite="" config="":
#     uv sync
#     if [ -n "{{ config }}" ]; then \
#         if [ -n "{{ datasite }}" ]; then \
#             uv run service.py --ping "{{ datasite }}" --config "{{ config }}"; \
#         else \
#             echo "{{ _yellow }}No datasite specified. Running in interactive mode.{{ _nc }}"; \
#             uv run service.py --client-only --config "{{ config }}"; \
#         fi \
#     else \
#         if [ -n "{{ datasite }}" ]; then \
#             uv run service.py --ping "{{ datasite }}"; \
#         else \
#             echo "{{ _yellow }}No datasite specified. Running in interactive mode.{{ _nc }}"; \
#             uv run service.py --client-only; \
#         fi \
#     fi

# Run the Syft server
syftbox-server:
    (cd /Users/swag/Documents/Coding/syft && just run-server)

# Run Alice's SyftBox client
client-alice:
    syftbox client \
        --server http://127.0.0.1:5001 \
        --email alice@openmined.org \
        --sync_folder ~/Desktop/SyftBoxAlice \
        --port 8081 \
        --config ~/.syft_alice_config.json

# Run Bob's SyftBox client
client-bob:
    syftbox client \
        --server http://127.0.0.1:5001 \
        --email bob@openmined.org \
        --sync_folder ~/Desktop/SyftBoxBob \
        --port 8082 \
        --config ~/.syft_bob_config.json

# Clean up environment and config files
clean:
    #!/usr/bin/env bash
    rm -rf .venv
    rm -f ~/.syft_alice_config.json
    rm -f ~/.syft_bob_config.json
    rm -rf ~/Desktop/SyftBoxAlice
    rm -rf ~/Desktop/SyftBoxBob
    (cd /Users/swag/Documents/Coding/syft && rm -rf ./.clients ./.server ./dist ./.e2e)
    echo -e "{{ _green }}Cleaned up environment successfully{{ _nc }}"
