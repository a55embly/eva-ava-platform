"""Background worker entry point for the demo ingestion run."""

from worker.jobs.ingest_local_knowledge import main as ingest_local_knowledge


def main() -> None:
    """Run the idempotent demo knowledge ingestion job once."""
    ingest_local_knowledge()


if __name__ == "__main__":
    main()
