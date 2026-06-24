from temporalio import workflow


@workflow.defn
class VideoProductionWorkflow:

    @workflow.run
    async def run(self, project_id: str) -> None:
        raise NotImplementedError("Sprint 2")
