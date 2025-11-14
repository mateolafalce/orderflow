import os
from typing import Optional, Dict, Any
from decimal import Decimal
import mercadopago
from dotenv import load_dotenv

load_dotenv()


class MercadoPagoPayment:
    
    def __init__(self):
        self.access_token = os.getenv('MP_ACCESS_TOKEN')
        self.cbu = os.getenv('CBU')
        
        # Validate required credentials
        if not self.access_token:
            raise ValueError(
                "Missing Mercado Pago credentials. Please check your .env file for "
                "MP_ACCESS_TOKEN"
            )
        
        if not self.cbu:
            raise ValueError(
                "Missing CBU. Please check your .env file for CBU"
            )
        
        # Initialize Mercado Pago SDK
        self.sdk = mercadopago.SDK(self.access_token)
    
    def create_payment_link(
        self,
        title: str,
        amount: float,
        description: Optional[str] = None,
        quantity: int = 1,
        external_reference: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            # Create preference data
            preference_data = {
                "items": [
                    {
                        "title": title,
                        "description": description or title,
                        "quantity": quantity,
                        "unit_price": float(amount),
                        "currency_id": "ARS"  # Argentine Peso
                    }
                ],
                "back_urls": {
                    "success": "https://www.tu-sitio.com/success",
                    "failure": "https://www.tu-sitio.com/failure",
                    "pending": "https://www.tu-sitio.com/pending"
                },
                "auto_return": "approved",
                "payment_methods": {
                    "excluded_payment_types": [],
                    "installments": 1  # Number of installments allowed
                },
                "statement_descriptor": os.getenv('BUSINESS_NAME', 'Mi Negocio'),
            }
            
            # Add external reference if provided
            if external_reference:
                preference_data["external_reference"] = str(external_reference)
            
            # preference_data["notification_url"] = "https://your-domain.com/webhook/mercadopago"
            
            # Create preference
            preference_response = self.sdk.preference().create(preference_data)
            
            # Debug: Print full response
            print("\nDEBUG - Full API Response:")
            print(f"Status: {preference_response.get('status')}")
            print(f"Response keys: {preference_response.keys()}")
            print(f"Response content: {preference_response.get('response')}")
            
            # Check if request was successful
            if preference_response["status"] not in [200, 201]:
                error_details = preference_response.get('response', {})
                error_msg = error_details.get('message', 'Unknown error')
                error_cause = error_details.get('cause', [])
                
                print(f"\nError details:")
                print(f"  Message: {error_msg}")
                print(f"  Cause: {error_cause}")
                
                return {
                    'success': False,
                    'error': f"API returned status {preference_response['status']}: {error_msg}",
                    'details': error_details,
                    'status_code': preference_response['status']
                }
            
            preference = preference_response["response"]
            print(f"Preference keys: {preference.keys()}")
            print(f"Init point: {preference.get('init_point')}")
            print(f"ID: {preference.get('id')}")
            
            return {
                'success': True,
                'payment_link': preference.get('init_point'),  # Link for web
                'payment_link_mobile': preference.get('sandbox_init_point'),  # Link for mobile/sandbox
                'preference_id': preference.get('id'),
                'external_reference': external_reference,
                'amount': amount,
                'quantity': quantity,
                'total': amount * quantity,
                'cbu': self.cbu,  # Include CBU for reference
                'raw_response': preference  # Include full response for debugging
            }
            
        except Exception as e:
            import traceback
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    def create_order_payment(
        self,
        order_id: int,
        items: list[Dict[str, Any]],
        customer_name: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            # Calculate total
            total = sum(item['price'] * item.get('quantity', 1) for item in items)
            
            # Build title
            if len(items) == 1:
                title = f"Orden #{order_id} - {items[0]['name']}"
            else:
                title = f"Orden #{order_id} - {len(items)} productos"
            
            # Build description
            items_desc = "\n".join([
                f"- {item['name']} x{item.get('quantity', 1)} (${item['price']})"
                for item in items
            ])
            description = f"Orden para {customer_name or 'Cliente'}\n{items_desc}"
            
            # Create preference data with all items
            preference_data = {
                "items": [
                    {
                        "title": item['name'],
                        "description": item.get('description', item['name']),
                        "quantity": item.get('quantity', 1),
                        "unit_price": float(item['price']),
                        "currency_id": "ARS"
                    }
                    for item in items
                ],
                "external_reference": f"order_{order_id}",
                "back_urls": {
                    "success": f"https://www.tu-sitio.com/order/{order_id}/success",
                    "failure": f"https://www.tu-sitio.com/order/{order_id}/failure",
                    "pending": f"https://www.tu-sitio.com/order/{order_id}/pending"
                },
                "auto_return": "approved",
                "payment_methods": {
                    "excluded_payment_types": [],
                    "installments": 1
                },
                "statement_descriptor": os.getenv('BUSINESS_NAME', 'Mi Negocio'),
            }
            
            # Create preference
            preference_response = self.sdk.preference().create(preference_data)
            preference = preference_response["response"]
            
            return {
                'success': True,
                'payment_link': preference.get('init_point'),
                'payment_link_mobile': preference.get('sandbox_init_point'),
                'preference_id': preference.get('id'),
                'order_id': order_id,
                'total': float(total),
                'items_count': len(items),
                'cbu': self.cbu
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'order_id': order_id
            }
    
    def get_payment_info(self, payment_id: str) -> Dict[str, Any]:
        try:
            payment_response = self.sdk.payment().get(payment_id)
            payment = payment_response["response"]
            
            return {
                'success': True,
                'payment_id': payment.get('id'),
                'status': payment.get('status'),
                'status_detail': payment.get('status_detail'),
                'amount': payment.get('transaction_amount'),
                'external_reference': payment.get('external_reference'),
                'payer_email': payment.get('payer', {}).get('email'),
                'date_created': payment.get('date_created'),
                'date_approved': payment.get('date_approved')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


_payment_instance = None

def get_payment_service() -> MercadoPagoPayment:
    global _payment_instance
    if _payment_instance is None:
        _payment_instance = MercadoPagoPayment()
    return _payment_instance


# Convenience functions
def create_payment_link(
    title: str,
    amount: float,
    description: Optional[str] = None,
    quantity: int = 1,
    external_reference: Optional[str] = None
) -> Dict[str, Any]:
    payment_service = get_payment_service()
    return payment_service.create_payment_link(
        title=title,
        amount=amount,
        description=description,
        quantity=quantity,
        external_reference=external_reference
    )


def create_order_payment_link(
    order_id: int,
    items: list[Dict[str, Any]],
    customer_name: Optional[str] = None
) -> Dict[str, Any]:
    payment_service = get_payment_service()
    return payment_service.create_order_payment(
        order_id=order_id,
        items=items,
        customer_name=customer_name
    )


if __name__ == "__main__":
    # Test the integration
    print("Testing Mercado Pago Integration...")
    
    try:
        payment_service = MercadoPagoPayment()
        print(f"Payment service initialized")
        print(f"  CBU: {payment_service.cbu}")
        
        # Test creating a simple payment link
        print("\nCreating test payment link...")
        result = payment_service.create_payment_link(
            title="Empanadas x6",
            amount=2500.00,
            description="Media docena de empanadas de carne",
            quantity=1,
            external_reference="test_001"
        )
        
        if result['success']:
            print(f"Payment link created!")
            print(f"  Link: {result['payment_link']}")
            print(f"  Preference ID: {result['preference_id']}")
            print(f"  Total: ${result['total']}")
        else:
            print(f"Failed to create payment link")
            print(f"  Error: {result['error']}")
        
        # Test creating an order payment
        print("\nCreating order payment link...")
        order_result = payment_service.create_order_payment(
            order_id=123,
            items=[
                {'name': 'Empanadas de carne', 'price': 1200, 'quantity': 6},
                {'name': 'Coca Cola 1.5L', 'price': 800, 'quantity': 1}
            ],
            customer_name="Juan Pérez"
        )
        
        if order_result['success']:
            print(f"Order payment link created!")
            print(f"  Link: {order_result['payment_link']}")
            print(f"  Total: ${order_result['total']}")
        else:
            print(f"Failed to create order payment link")
            print(f"  Error: {order_result['error']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
