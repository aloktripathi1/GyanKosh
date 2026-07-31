from app.llm.client import ModelTier, structured_call
from app.llm.prompts.classification import SYSTEM_PROMPT, build_user_prompt
from app.schemas.classification import ClassificationOutput
from app.schemas.document_intelligence import DocumentIntelligenceOutput


def run(input: DocumentIntelligenceOutput) -> ClassificationOutput:
    return structured_call(
        tier=ModelTier.CHEAP,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(input),
        output_schema=ClassificationOutput,
    )
