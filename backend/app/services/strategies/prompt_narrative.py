import logging

from app.engines.ai.factory import get_ai_provider
from app.services.strategies.base import NarrativeOutcome

logger = logging.getLogger(__name__)


class PromptNarrativeStrategy:
    async def run(
        self,
        *,
        topic_title,
        topic_description,
        render_engine,
        aspect_ratio,
        rejection_context,
        previous_scenes,
        narrative_context,
        style_components,
        task_id,
    ) -> NarrativeOutcome:
        provider = get_ai_provider("narrative_generation")
        logger.info("[PromptNarrative] calling AI provider model=%s", provider.model_name)
        result = await provider.generate_narrative(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            rejection_context=rejection_context,
            previous_scenes=previous_scenes,
            narrative_context=narrative_context,
            style_components=style_components,
            aspect_ratio=aspect_ratio,
        )
        logger.info(
            "[PromptNarrative] AI done: scenes=%d fact_checks=%d",
            len(result.scenes),
            len(result.fact_checks),
        )
        return NarrativeOutcome(
            scenes=result.scenes,
            fact_checks=result.fact_checks,
            ai_model=provider.model_name,
            trace={"execution_mode": "prompt"},
        )
