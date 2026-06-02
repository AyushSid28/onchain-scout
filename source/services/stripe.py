import stripe
from typing import Dict, Any
from configs.config import get_settings
from configs.logfire_config import setup_logger
from datetime import datetime, timedelta

logger = setup_logger(__name__)
settings = get_settings()

class StripeService:
    def __init__(self):
        self.api_key = settings.stripe.api_key.get_secret_value()
        stripe.api_key = self.api_key
        self.subscription_price_id = settings.stripe.subscription_price_id.get_secret_value()
        self.webhook_secret = settings.stripe.webhook_secret.get_secret_value()
    
    def create_customer(self, email: str, name: str) -> str:
        """Create a new customer in Stripe"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name
            )
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Error creating Stripe customer: {str(e)}")
            raise
    
    def create_checkout_session(self, customer_id: str, amount: float, success_url: str, cancel_url: str, payment_type: str = "topup", metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a checkout session for a one-time payment"""
        try:
            # Set product name based on payment type
            product_name = "Scam Detector Subscription" if payment_type == "subscription" else "Wallet Top-up"
            description = "Access to Scam Detector platform" if payment_type == "subscription" else f"Add ${amount} to your wallet"
            
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': product_name,
                            'description': description
                        },
                        'unit_amount': int(amount * 100),  # Convert to cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                expires_at=int((datetime.now() + timedelta(minutes=30)).timestamp()),  # Session expires in 30 minutes
                payment_intent_data={
                    'metadata': metadata,  # Add metadata to the payment intent
                # 'setup_future_usage': 'off_session',  # Save card for future auto-topups
                },
                # Add this parameter to display saved payment methods
                saved_payment_method_options={
                    "payment_method_save": "enabled"
                }
            )
            return checkout_session
        except stripe.error.StripeError as e:
            logger.error(f"Error creating checkout session: {str(e)}")
            raise
    
    def create_payment_intent(self, amount: float, customer_id: str, metadata: Dict[str, Any], payment_method_id: str) -> Dict[str, Any]:
        """Create a payment intent for auto top-up"""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency="usd",
                customer=customer_id,
                metadata=metadata,
                off_session=True,
                confirm=True,
                payment_method=payment_method_id,
            )
            return payment_intent
        except stripe.error.StripeError as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            raise
    
    def confirm_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """Confirm a payment intent for auto top-up"""
        try:
            payment_intent = stripe.PaymentIntent.confirm(payment_intent_id)
            logger.info(f"Payment intent confirmed: {payment_intent}")
            return payment_intent
        except stripe.error.StripeError as e:
            logger.error(f"Error confirming payment intent: {str(e)}")
            raise
    
    def verify_webhook_signature(self, payload: bytes, sig_header: str) -> stripe.Event:
        """Verify webhook signature and return the event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except (stripe.error.SignatureVerificationError, ValueError) as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            raise
    
    def get_payment_methods(self, customer_id: str):
        """Get a list of payment methods for a customer"""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type='card',
            )
             # Check if the customer has any payment methods
            if not payment_methods.data:
                logger.error(f"No payment method available for auto top-up for user {customer_id}")
                return None
            return payment_methods.data
        except stripe.error.StripeError as e:
            logger.error(f"Error getting payment methods: {str(e)}")
            raise
    
    def add_payment_method(self, customer_id: str, success_url: str, cancel_url: str) -> str:
        """Add a payment method to a customer"""
        try:
            # Create a Checkout session for setting up a payment method
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                mode='setup',  # This is key - it creates a setup session instead of a payment
                success_url=success_url,
                cancel_url=cancel_url,
            )
            
            return checkout_session.url
        except stripe.error.StripeError as e:
            logger.error(f"Error adding payment method: {str(e)}")
            raise
    
    def delete_payment_method(self, payment_method_id: str):
        """Delete a payment method from a customer"""
        try:
            response = stripe.PaymentMethod.detach(
                payment_method_id)
            return response
        except stripe.error.StripeError as e:
            logger.error(f"Error deleting payment method: {str(e)}")
            raise
    
    def retrieve_payment_method(self, payment_method_id: str):
        """Retrieve a payment method"""
        try:
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            return payment_method
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving payment method: {str(e)}")
            raise
    
    def retrieve_default_payment_method(self, customer_id: str):
        """Retrieve the default payment method for a customer"""
        try:
            payment_method = stripe.Customer.retrieve(customer_id).invoice_settings.default_payment_method
            if not payment_method:
                # If no default is set, get the most recent payment method
                payment_methods = stripe.PaymentMethod.list(
                    customer=customer_id,
                    type="card"
                )
                if payment_methods.data:
                    return payment_methods.data[0].id
                return None
            return payment_method
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving default payment method: {str(e)}")
            raise
    
    def modify_default_payment_method(self, customer_id: str, payment_method_id: str):
        """Modify the default payment method for a customer"""
        try:
            customer = stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_id
                }
            )
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Error modifying default payment method: {str(e)}")
            raise
    
    def create_billing_portal_session(self, customer_id: str, return_url: str) -> Dict[str, Any]:
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url  # Where users return after managing
            )
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Error creating portal session: {str(e)}")
            raise