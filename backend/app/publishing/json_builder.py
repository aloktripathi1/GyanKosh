from app.schemas.tkp import TeacherKnowledgePackage


def build(job_id: str, version: int, stage_results: dict) -> TeacherKnowledgePackage:
    """Assemble the final TeacherKnowledgePackage from checkpointed stage_results.
    Implemented in Milestone 4."""
    raise NotImplementedError("TKP JSON builder lands in Milestone 4")
