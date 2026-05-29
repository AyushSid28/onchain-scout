import asyncio, uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Union
from configs.logfire_config import setup_logger

logger = setup_logger(__name__)
executor = ThreadPoolExecutor()

class TaskManager:
    def __init__(self):
        self.tasks = {}

    def add_task(self, func, *args, **kwargs):
        task_id = str(uuid.uuid4())
        future = executor.submit(func, *args, **kwargs)
        self.tasks[task_id] = future
        logger.info(f"Added task {task_id}")
        return task_id
    
    def get_task(self, task_id):
        logger.info(f"Getting task {task_id}")
        return self.tasks.get(task_id, None)

class AsyncTaskManager():
    def __init__(self):
        self.tasks = {}

    def add_task(self, func, *args, **kwargs):
        task_id = str(uuid.uuid4())
        # Create a wrapper function to run async function in executor
        def run_async_function():
            logger.info(f"Added task {task_id}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(func(*args, **kwargs))
            loop.close()
            return result
            
        future = executor.submit(run_async_function)
        self.tasks[task_id] = future
        return task_id
    
    def get_task(self, task_id):
        logger.info(f"Getting task {task_id}")
        return self.tasks.get(task_id, None)


async def get_task_status(task_manager: Union[TaskManager, AsyncTaskManager], task_id):
    """
    Get the status of a task.

    Args:
        task_manager (Union[TaskManager, AsyncTaskManager]): The task manager.
        task_id (str): The ID of the task.

    Returns:
        The status of the task.

    Raises:
        HTTPException: If an error occurs.
    """
    # Get the task
    task = task_manager.get_task(task_id)

    # If the task is not found
    if task is None:
        logger.error(f"Task : {task_id} not found")
        return {"status": "not found"}

    # If the task is still running
    elif task.running():
        logger.info(f"Task : {task_id} is still running")
        return {"status": "running"}

    # If the task is done
    elif task.done():
        # If the task failed
        if task.exception() is not None:
            logger.error(f"Task : {task_id} failed")
            return {"status": "failed", "error": str(task.exception())}
        # If the task succeeded
        else:
            logger.info(f"Task : {task_id} succeeded")
            return {"status": "done", "result": task.result()}