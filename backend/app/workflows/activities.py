from temporalio import activity


@activity.defn
async def submit_script_generation_task(project_id: str) -> None:
    raise NotImplementedError("Sprint 2")


@activity.defn
async def submit_video_generation_task(project_id: str) -> None:
    raise NotImplementedError("Sprint 3")


@activity.defn
async def update_project_status(project_id: str, new_status: str) -> None:
    raise NotImplementedError("Sprint 2")


@activity.defn
async def check_and_increment_retry(
    project_id: str, stage: str, error: str
) -> bool:
    raise NotImplementedError("Sprint 2")
