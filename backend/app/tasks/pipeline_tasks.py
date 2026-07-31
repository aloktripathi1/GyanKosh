from app.tasks.celery_app import celery_app


@celery_app.task(name="tasks.run_job")
def run_job(job_id: str) -> None:
    """Celery entrypoint: loads the job, hands it to the orchestrator. Wired to
    orchestrator.pipeline.run_pipeline in Milestone 4."""
    raise NotImplementedError("Pipeline task wiring lands in Milestone 4")
