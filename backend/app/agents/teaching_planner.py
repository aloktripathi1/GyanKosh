from app.llm.client import ModelTier, structured_call
from app.llm.prompts.teaching_planner import SYSTEM_PROMPT, build_user_prompt
from app.schemas.classification import ClassificationOutput
from app.schemas.knowledge_extraction import KnowledgeExtractionOutput
from app.schemas.teaching_planner import TeachingPlanOutput

# The system prompt already asks for <= 12, but nothing stops a model from
# ignoring that under a dense enough document — this is the hard backstop
# Section 15 calls for ("cap it, don't let the LLM output 40 periods
# unchecked"). Truncating (rather than merging/re-planning) is a deliberate
# choice: it's deterministic and cheap, and a plan that's merely capped is a
# far better failure mode than either an unbounded plan or a second paid LLM
# call to "fix" it.
MAX_PERIODS = 12


class TeachingPlannerInput:
    def __init__(
        self,
        classification: ClassificationOutput,
        extracted_knowledge: KnowledgeExtractionOutput,
        teaching_context: str | None = None,
    ):
        self.classification = classification
        self.extracted_knowledge = extracted_knowledge
        self.teaching_context = teaching_context


def run(input: TeachingPlannerInput) -> TeachingPlanOutput:
    result = structured_call(
        tier=ModelTier.STRONG,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(input.classification, input.extracted_knowledge, input.teaching_context),
        output_schema=TeachingPlanOutput,
    )
    if not result.periods:
        raise ValueError("Teaching planner returned zero periods — every document must yield at least one period")
    if len(result.periods) > MAX_PERIODS:
        result = result.model_copy(update={"periods": result.periods[:MAX_PERIODS], "total_periods": MAX_PERIODS})
    return result
