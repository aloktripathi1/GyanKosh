import pytest

from app.agents.grounding import UnresolvedGroundingRefError, resolve_grounding_refs
from app.schemas.common import SourceSpan
from app.schemas.knowledge_extraction import Concept, KnowledgeExtractionOutput

SPAN = SourceSpan(section_id="s1", start_char=0, end_char=10, quote="x")

LONG_CONCEPT_TEXT = (
    "We have learnt in Class IX that during a chemical reaction atoms of one element do not "
    "change into those of another element. Nor do atoms disappear from the mixture or appear "
    "from elsewhere. Actually, chemical reactions involve the breaking and making of bonds "
    "between atoms to produce new substances. You will study about types of bonds formed "
    "between atoms in Chapters 3 and 4."
)


def _extraction_with(text: str):
    return KnowledgeExtractionOutput(
        objectives=[], prerequisites=[],
        concepts=[Concept(text=text, name="Chemical reactions", source_span=SPAN)],
        definitions=[], formulae=[], keywords=[], examples=[], applications=[], misconceptions=[],
    )


def test_exact_match_resolves():
    ek = _extraction_with("Photosynthesis converts light energy into chemical energy.")
    spans = resolve_grounding_refs(ek, ["Photosynthesis converts light energy into chemical energy."])
    assert spans == [SPAN]


def test_whitespace_only_difference_resolves():
    ek = _extraction_with("Photosynthesis converts\nlight energy into chemical energy.")
    spans = resolve_grounding_refs(ek, ["Photosynthesis converts light energy into chemical energy."])
    assert spans == [SPAN]


def test_light_compression_of_a_long_item_resolves():
    """Real case found on a live document: the model compressed a long
    extracted concept (dropping a clause, reordering slightly) when citing
    it, rather than reproducing it character-for-character."""
    ek = _extraction_with(LONG_CONCEPT_TEXT)
    ref = (
        "During a chemical reaction, atoms of one element do not change into those of "
        "another element. Chemical reactions involve breaking and making of bonds between "
        "atoms to produce new substances."
    )
    spans = resolve_grounding_refs(ek, [ref])
    assert spans == [SPAN]


def test_unrelated_fabricated_ref_is_rejected():
    ek = _extraction_with(LONG_CONCEPT_TEXT)
    with pytest.raises(UnresolvedGroundingRefError):
        resolve_grounding_refs(ek, ["The mitochondria is the powerhouse of the cell."])


def test_ref_with_no_matching_words_at_all_is_rejected():
    ek = _extraction_with("Newton's second law: F = m * a.")
    with pytest.raises(UnresolvedGroundingRefError):
        resolve_grounding_refs(ek, ["completely different unrelated fabricated sentence here"])
