from typing import TypedDict


class TaskStep(TypedDict):
    id: int
    task: str
    type: str


class TaskPlan(TypedDict):
    original_request: str
    steps: list[TaskStep]


class TaskPlanner:

    def create_plan(
        self,
        message: str,
        task_type: str,
    ) -> TaskPlan:

        text = message.strip()

        # ==========================================
        # IMPORTANT:
        # معظم الأسئلة لا تحتاج Planner.
        # ننفذها مباشرة في خطوة واحدة.
        # ==========================================

        return {
            "original_request": text,

            "steps": [
                {
                    "id": 1,
                    "task": text,
                    "type": task_type,
                }
            ],
        }