from fastapi import APIRouter, HTTPException, Depends
from configs.logfire_config import setup_logger
from db.crud import get_analysis_results, get_runs, get_running_run_for_username, get_unique_analyses_for_username, get_limit_entry, can_perform_evaluation, check_if_auto_topup_enabled, auto_topup,get_token_risk_assessments
from source.services.evaluation import analysis as old_analysis
from source.services.eval import analysis_new as new_analysis
from source.utils.auth import get_user_id
from source.utils.results import format_results
from source.utils.task_manager import AsyncTaskManager, get_task_status
from schemas import EvaluationRequest

running_tasks = {}
evaluation_task_manager = AsyncTaskManager()
logger = setup_logger(__name__)
evaluate_router = APIRouter(prefix="/evaluate", tags=["Evaluate"])

@evaluate_router.post("/")
async def evaluate(request: EvaluationRequest, user_id: str = Depends(get_user_id)):
    """
    Evaluate the profile
    
    Args:
    - request: EvaluationRequest
    
    Returns:
    - Dictionary with task_id and message"""
    try:
        if can_perform_evaluation(user_id):
            logger.info("Evaluation request received")
        else:
            if check_if_auto_topup_enabled(user_id):
                logger.info("Auto Topup is enabled")
                success, auto_topup_transaction = auto_topup(user_id)
                if success:
                    logger.info("Auto Topup successful")
                else:
                    return {
                        "task_id" : None,
                        "message" : auto_topup_transaction
                    }
            else:
                return {
                    "task_id" : None,
                    "message" : "Wallet balance is insufficient to perform Evaluation, Topup Wallet or Redeem Coupon to perform Evaluation, or enable Auto Topup"
                }
        x_profile = request.x_profile.lower()
        running_run = get_running_run_for_username(x_profile, user_id)
        if running_run:
            if x_profile in running_tasks:
                task_id = running_tasks[x_profile]
                task_status = await get_task_status(evaluation_task_manager, task_id)
                if task_status['status'] == "running":
                    logger.info("An Evaluation is already running")
                    return {
                        "task_id" : task_id,
                        "message" : "An Evaluation is already running"
                    }
        # limit = get_limit_entry(session.get_user_id())
        # if limit<=0:
        #     return {
        #         "task_id" : None,
        #         "message" : "Evaluation limit exceeded"
        #     }
        task_id = evaluation_task_manager.add_task(
            new_analysis,
            x_profile,
            user_id,
            request.evaluation_type,
            request.project_name,
            request.project_description,
            request.token_name,
            request.token_address,
            request.token_chain,
            request.token_risk,
        )
        running_tasks[x_profile] = task_id
        return {
                "task_id" : task_id,
                "message" : "Task submitted successfully"
            }
    except Exception as e:
        logger.error(f"Error in Submitting task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@evaluate_router.get("/results/{username}")
async def get_evaluation_results(username: str, user_id: str = Depends(get_user_id)):
    """
    Get the results of a task.

    Args:
        username (str): The username of the profile.

    Returns:
        The results of the evaluation.

    Raises:
        HTTPException: If an error occurs.
    """
    try:
        running_run = get_running_run_for_username(username, user_id)
        if running_run:
            return {"username": username, "results": "Running"}
        results = get_analysis_results(username, user_id)
        if not results:
            raise HTTPException(status_code=404, detail="Results not found for the given username")
        results = format_results(results)
        results["results"]["ip_conflict_analysis"] = get_unique_analyses_for_username(username)
        
        # Get all token risk assessments for historical view
        token_risks = get_token_risk_assessments(username, user_id)
        
        # Remove duplicate: if token_risk exists and has an id, filter it out from token_risk_assessments array
        # This ensures token_risk (primary) and token_risk_assessments (historical) don't duplicate
        current_token_risk = results["results"].get("token_risk")
        if current_token_risk and isinstance(current_token_risk, dict):
            token_risk_id = current_token_risk.get("id")
            if token_risk_id:  # Only filter if id exists
                token_risks = [tr for tr in token_risks if tr.get("id") != token_risk_id]
        
        results["results"]["token_risk_assessments"] = token_risks
        return results
        
    except Exception as e:
        logger.error(f"Error getting results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@evaluate_router.get("/runs")
async def get_evaluation_runs(user_id: str = Depends(get_user_id)):
    """
    Get the runs of a ScamAnalysis by the user.

    Args:
        session (SessionContainer): The session container.

    Returns:
        All the runs of the user.

    Raises:
        HTTPException: If an error occurs.
    """
    try:
        return get_runs(user_id)
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@evaluate_router.get("/status")
async def get_evaluation_status(task_id, user_id: str = Depends(get_user_id)):
    """
    Get the status of a task.

    Args:
        task_id (str): The ID of the task.

    Returns:
        The status of the task.

    Raises:
        HTTPException: If an error occurs.
    """
    try:
        return await get_task_status(evaluation_task_manager, task_id)
    # If an error occurs
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@evaluate_router.get("/limits")
async def get_evaluation_limits(user_id: str = Depends(get_user_id)):
    try:
        return get_limit_entry(user_id)
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))