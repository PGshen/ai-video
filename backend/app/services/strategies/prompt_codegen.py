import logging

from app.engines.ai.factory import get_ai_provider
from app.engines.render.base import SceneInput
from app.engines.render.factory import get_render_engine
from app.services.strategies.base import CodegenOutcome

_MAX_VALIDATION_ROUNDS = 2

logger = logging.getLogger(__name__)


class PromptCodegenStrategy:
    async def run(
        self,
        *,
        scenes,
        render_engine,
        style_components,
        aspect_ratio,
        rejection_context,
        previous_code_scenes,
        task_id,
    ) -> CodegenOutcome:
        provider = get_ai_provider("code_generation")
        logger.info("[PromptCodegen] calling AI provider model=%s", provider.model_name)
        codegen_scenes = [
            {
                "scene_index": scene["scene_index"],
                "narration": scene["narration"],
                "description": scene["description"],
                "duration_seconds": scene.get("duration_seconds"),
                "beats": scene["beats"],
            }
            for scene in scenes
        ]
        result = await provider.generate_code(
            scenes=codegen_scenes,
            render_engine=render_engine,
            style_components=style_components,
            aspect_ratio=aspect_ratio,
            rejection_context=rejection_context,
            previous_code_scenes=previous_code_scenes,
        )
        logger.info("[PromptCodegen] AI done: codes=%d", len(result.codes))

        merged_scenes = []
        for i, scene in enumerate(scenes):
            code = result.codes[i] if i < len(result.codes) else ""
            merged_scenes.append({**scene, "code": code})

        render_engine_obj = get_render_engine(render_engine)
        repair_rounds = 0
        for round_num in range(_MAX_VALIDATION_ROUNDS):
            is_valid, errors = await render_engine_obj.validate_code(
                _scene_inputs(merged_scenes)
            )
            if is_valid:
                logger.info("[PromptCodegen] validation passed (round %d)", round_num)
                break
            logger.info(
                "[PromptCodegen] validation round %d/%d failed, repairing...",
                round_num + 1,
                _MAX_VALIDATION_ROUNDS,
            )
            repair_rounds += 1
            repair_provider = get_ai_provider("code_repair")
            repair_result = await repair_provider.repair_code(
                scenes=merged_scenes,
                render_engine=render_engine,
                error_message=errors,
                style_components=style_components,
                aspect_ratio=aspect_ratio,
            )
            for r in repair_result.repairs:
                idx = r["scene_index"]
                merged_scenes[idx] = {**merged_scenes[idx], "code": r["code"]}
                logger.info(
                    "[PromptCodegen] repaired scene %d: %s",
                    idx,
                    r.get("explanation", "")[:120],
                )
        else:
            is_valid, errors = await render_engine_obj.validate_code(
                _scene_inputs(merged_scenes)
            )
            if is_valid:
                logger.info("[PromptCodegen] validation passed after final repair")
            else:
                logger.warning(
                    "[PromptCodegen] validation still failing after %d rounds:\n%s",
                    _MAX_VALIDATION_ROUNDS,
                    errors[:500],
                )
                raise ValueError(
                    f"Code validation failed after {_MAX_VALIDATION_ROUNDS} repair rounds:\n{errors[:2000]}"
                )

        return CodegenOutcome(
            scenes=merged_scenes,
            ai_model=provider.model_name,
            trace={"execution_mode": "prompt", "repair_rounds": repair_rounds},
        )


def _scene_inputs(merged_scenes: list[dict]) -> list[SceneInput]:
    return [
        SceneInput(
            scene_index=i,
            narration=s.get("narration", ""),
            description=s.get("description", ""),
            code=s.get("code", ""),
            audio=None,
        )
        for i, s in enumerate(merged_scenes)
    ]
