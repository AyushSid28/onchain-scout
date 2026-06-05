from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from db.crud import create_subscription_checkout, create_topup_checkout, get_transactions, get_user_details, create_get_user_wallet, evaluation_cost, handle_payment_canceled, handle_payment_expired, handle_payment_failed, handle_payment_success, has_made_initial_payment, redeem_coupon, subscription_amount, toggle_auto_topup
from supertokens_python.recipe.session.framework.fastapi import verify_session
from supertokens_python.recipe.session import SessionContainer
from source.services.stripe import StripeService
from configs.config import get_settings
from configs.logfire_config import setup_logger

# Initialize logger
logger = setup_logger(__name__)
# Get settings
settings = get_settings()
api_url = f"{settings.supertokens.website_domain.rstrip('/')}/"
payments_router = APIRouter(tags=["Payments"])

# Initialize Stripe service
stripe_service = StripeService()

@payments_router.get("/wallet", response_model=Dict[str, Any])
async def get_wallet(session: SessionContainer = Depends(verify_session())):
    """Get current user's wallet information"""
    try:
        wallet = create_get_user_wallet(session.user_id)
        
        # Check if user has made initial payment
        # has_subscription = has_made_initial_payment(session.user_id)

        # Get current user
        current_user = get_user_details(session.user_id)
        
        return {
            "balance": wallet.balance,
            "evaluation_cost": evaluation_cost,
            "evaluations_available": int(wallet.balance / evaluation_cost),
            "auto_topup": current_user.auto_topup,
            "auto_topup_amount": current_user.auto_topup_amount
            # "has_subscription": has_subscription,
            # "subscription_amount": subscription_amount
        }
    except Exception as e:
        logger.error(f"Error getting wallet info: {e}")
        raise HTTPException(status_code=400, detail="Error getting wallet info")

# @payments_router.post("/subscription", response_model=Dict[str, Any])
# async def create_subscription__checkout(session: SessionContainer = Depends(verify_session())):
#     """Create a checkout session for subscription"""
#     try:
#         # Check if user already has a subscription
#         if has_made_initial_payment(session.user_id):
#             logger.info(f"User {session.user_id} already has a subscription")
#             raise HTTPException(
#                 status_code=400,
#                 detail="You already have a subscription"
#             )

#         # Create success and cancel URLs
#         success_url = f"{api_url}subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
#         cancel_url = f"{api_url}subscription/cancel"

#         # Create checkout session
#         try:
#             checkout_data = create_subscription_checkout(
#                 user_id=session.user_id,
#                 success_url=success_url,
#                 cancel_url=cancel_url
#             )
#         except Exception as e:
#             logger.error(f"Error creating subscription checkout for user {session.user_id}: {e}")
#             raise HTTPException(status_code=500, detail="Error creating subscription checkout")

#         return checkout_data

#     except HTTPException as e:
#         logger.error(f"HTTPException for user {session.user_id}: {e.detail}")
#         raise
#     except Exception as e:
#         logger.error(f"Unexpected error for user {session.user_id}: {e}")
#         raise HTTPException(status_code=500, detail="Unexpected error during subscription checkout")

@payments_router.post("/topup", response_model=Dict[str, Any])
async def create__topup_checkout(amount: float = 100.0, session: SessionContainer = Depends(verify_session())):
    """Create a checkout session for manual wallet top-up"""
    try:
        # Create success and cancel URLs
        success_url = f"{api_url}topup/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{api_url}topup/failed"

        # Create checkout session
        checkout_data = create_topup_checkout(
            user_id=session.user_id,
            amount=amount,
            success_url=success_url,
            cancel_url=cancel_url
        )
        return checkout_data
    except HTTPException as e:
        logger.error(f"HTTPException for user {session.user_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error for user {session.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Unexpected error during top-up checkout")

@payments_router.post("/auto-topup", response_model=Dict[str, Any])
async def toggle_auto__topup(enabled: bool, amount: Optional[float] = None, session: SessionContainer = Depends(verify_session())):
    """Toggle auto-topup setting for a user"""
    try:
        
        # Validate amount if provided
        if amount is not None:
            if amount < 10.0:
                logger.info(f"User {session.user_id} attempted to set auto-topup amount below minimum")
                raise HTTPException(
                    status_code=400,
                    detail="Minimum auto-topup amount is $10"
                )
        
        user = toggle_auto_topup(session.user_id, enabled, amount)
        
        return {
            "auto_topup": user.auto_topup,
            "auto_topup_amount": user.auto_topup_amount
        }
    except HTTPException as e:
        logger.error(f"HTTPException for user {session.user_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error for user {session.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Unexpected error during auto-topup toggle")

@payments_router.get("/transactions", response_model=Dict[str, Any])
async def get__transactions(session: SessionContainer = Depends(verify_session())):
    """Get user's transaction history"""
    try:
        transactions = get_transactions(session.user_id)
        return transactions
    except HTTPException as e:
        logger.error(f"HTTPException for user {session.user_id}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error for user {session.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Unexpected error during transaction retrieval")

@payments_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    # Get the webhook signature from headers
    signature = request.headers.get("stripe-signature")
    
    # Get the request body
    payload = await request.body()
    
    try:
        # Verify the webhook signature
        event = stripe_service.verify_webhook_signature(payload, signature)
    except Exception as e:
        logger.error(f"Unexpected error during webhook verification: {str(e)}")
        raise HTTPException(status_code=500, detail="Unexpected error during webhook verification")
    
    # Handle different event types
    event_type = event.type
    event_data = event.data.object
    logger.info(event_type)
    if event_type == "payment_intent.succeeded":
        try:
            handle_payment_success(event_data)
        except Exception as e:
            logger.error(f"Error handling payment success for customer {event_data.customer}, error: {str(e)}")
            raise HTTPException(status_code=500, detail="Error handling payment success")
    elif event_type == "payment_intent.payment_failed":
        try:
            handle_payment_failed(event_data)
        except Exception as e:
            logger.error(f"Error handling payment failed for customer {event_data.customer}, error: {str(e)}")
            raise HTTPException(status_code=500, detail="Error handling payment failed")
    elif event_type == "payment_intent.canceled":
        try:
            handle_payment_canceled(event_data)
        except Exception as e:
            logger.error(f"Error handling payment canceled for customer {event_data.customer}, error: {str(e)}")
            raise HTTPException(status_code=500, detail="Error handling payment canceled")
    elif event_type in ["payment_method.attached", "payment_method.detached"]:
        logger.info(f"Payment method updated: {event_data.id}")
    elif event_type == "customer.updated":
        logger.info(f"Customer updated: {event_data.id}")
    elif event_type == "payment_intent.created":
        logger.info(f"Payment intent created: {event_data.id}")
    elif event_type == "checkout.session.expired":
        logger.info(f"Checkout session expired: {event_data.id}")
        handle_payment_expired(event_data)
    elif event_type == "checkout.session.canceled":
        logger.info(f"Checkout session canceled: {event_data.id}")
        handle_payment_canceled(event_data)
    else:
        # Handle other event types as needed
        pass
    # Always return a 200 response to acknowledge receipt
    return {"status": "success"}

@payments_router.post("/redeem-coupon", response_model=Dict[str, Any])
async def redeem_coupon_code(coupon_code: str, session: SessionContainer = Depends(verify_session())):
    """Redeem a coupon code"""
    result = redeem_coupon(session.user_id, coupon_code)
    
    if not result:
        raise HTTPException(status_code=404, detail="Coupon not found")
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@payments_router.post("/update-payment-details")
async def update_payment_details(session: SessionContainer = Depends(verify_session())):
    """Create Stripe Customer Portal session for payment management"""
    # Get current user
    current_user = get_user_details(session.user_id)
    
    # Ensure user has a Stripe customer ID
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="You need to make a payment first"
        )
    
    try:
        return_url=f"{api_url}billing"

        portal_session = stripe_service.create_billing_portal_session(
            current_user.stripe_customer_id,
            return_url
        )
        return {
            "portal_url": portal_session.url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @payments_router.post('/payment-methods/add')
# async def add_payment_method(session: SessionContainer = Depends(verify_session())):
#     """Create a setup intent for adding a new payment method"""
#     current_user = get_user_details(session.user_id)
#     # Ensure user has a Stripe customer ID
#     if not current_user.stripe_customer_id:
#         raise HTTPException(status_code=400, detail="You need to make a payment first")
    
#     # Create success and cancel URLs
#     success_url = f"{api_url}subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
#     cancel_url = f"{api_url}subscription/cancel"
    
#     # Create a SetupIntent
#     try:
#         checkout_url = stripe_service.add_payment_method(current_user.stripe_customer_id, success_url, cancel_url)
#         return checkout_url
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @payments_router.get('/payment-methods/get')
# async def get_payment_methods(session: SessionContainer = Depends(verify_session())):
#     """Get user's saved payment methods"""
#     # Get current user
#     current_user = get_user_details(session.user_id)
#     # Ensure user has a Stripe customer ID
#     if not current_user.stripe_customer_id:
#         return []
    
#     try:
#         payment_methods = stripe_service.get_payment_methods(current_user.stripe_customer_id)
#         return [
#                 {
#                     "id": pm.id,
#                     "brand": pm.card.brand,
#                     "last4": pm.card.last4,
#                     "exp_month": pm.card.exp_month,
#                     "exp_year": pm.card.exp_year
#                 }
#                 for pm in payment_methods
#             ]
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@payments_router.get('/default-payment-method')
async def get_default_payment_method(session: SessionContainer = Depends(verify_session())):
    """Get user's default payment method"""
    # Get current user
    current_user = get_user_details(session.user_id)
    # Ensure user has a Stripe customer ID
    if not current_user.stripe_customer_id:
        return {"message": "No payment methods available"}
    try:
        default_payment_method_id = stripe_service.retrieve_default_payment_method(current_user.stripe_customer_id)
        # Check if a default payment method exists
        if not default_payment_method_id:
            return {"message": "No default payment method set"}
        default_payment_method = stripe_service.retrieve_payment_method(default_payment_method_id)
        return {
            "brand": default_payment_method.card.brand,
            "last4": default_payment_method.card.last4,
            "exp_month": default_payment_method.card.exp_month,
            "exp_year": default_payment_method.card.exp_year
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @payments_router.delete('/payment-methods/{payment_method_id}')
# async def delete_payment_method(payment_method_id: str, session: SessionContainer = Depends(verify_session())):
#     """Delete a payment method"""
#     # Get current user
#     current_user = get_user_details(session.user_id)

#     # Ensure user has a Stripe customer
#     if not current_user.stripe_customer_id:
#         raise HTTPException(status_code=400, detail="No payment methods available")
    
#     try:
#         # First, verify this payment method belongs to the customer
#         payment_method = stripe_service.retrieve_payment_method(payment_method_id)
        
#         if payment_method.customer != current_user.stripe_customer_id:
#             raise HTTPException(status_code=403, detail="Payment method does not belong to this user")
        
#         # Detach the payment method from the customer
#         delete_response = stripe_service.delete_payment_method(payment_method_id)
        
#         return {"success": True, "message": "Payment method deleted successfully"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @payments_router.put('/payment-methods/set-default/{payment_method_id}')
# async def set_default_payment_method(payment_method_id: str, session: SessionContainer = Depends(verify_session())):
#     """Set a payment method as default for the customer"""
#     # Get current user
#     current_user = get_user_details(session.user_id)
#     if not current_user.stripe_customer_id:
#         raise HTTPException(status_code=400, detail="No customer profile available")
    
#     try:
#         # First, verify this payment method belongs to the customer
#         payment_method = stripe_service.retrieve_payment_method(payment_method_id)
        
#         if payment_method.customer != current_user.stripe_customer_id:
#             raise HTTPException(status_code=403, detail="Payment method does not belong to this user")
        
#         # Update the customer's default payment method
#         customer = stripe_service.modify_default_payment_method(current_user.stripe_customer_id, payment_method_id)
        
#         return {"success": True, "message": "Default payment method updated successfully"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
