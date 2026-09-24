"""Report available memory and exit non-zero below the heavy-run gate.

Run before any heavy command that is not a funnel module (for example, dbt build):
python -m funnel.ramcheck
"""

from funnel.common import require_available_ram

if __name__ == "__main__":
    require_available_ram()
