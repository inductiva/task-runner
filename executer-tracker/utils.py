def make_task_key(task_id: str, attribute: str) -> str:
    """
    Auxiliary function to generate Redis key to acess a task attribute.
    Args:
        task_id: task id
        attribute: name of the task attribute we want to get
    """
    return f"task:{task_id}:{attribute}"
