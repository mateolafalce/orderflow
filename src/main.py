import os
import json
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from ai import chat_with_assistant
from db import (
		conversations_table,
		ensure_database_exists,
		get_engine,
		get_session,
		products_table,
)
from message import get_messenger
from payment import create_payment_link, create_order_payment_link


@asynccontextmanager
async def lifespan(app: FastAPI):
	ensure_database_exists()
	get_engine()
	yield

app = FastAPI(title="Orderflow Service", lifespan=lifespan)

class ProductPayload(BaseModel):
	name: str = Field(..., min_length=1, max_length=255)
	price_half_quantity: Decimal = Field(..., gt=0)


class ChatRequest(BaseModel):
	message: str = Field(..., min_length=1)


class PaymentLinkRequest(BaseModel):
	title: str = Field(..., min_length=1, max_length=255)
	amount: float = Field(..., gt=0)
	description: str = Field(None)
	quantity: int = Field(1, gt=0)
	external_reference: str = Field(None)


class OrderPaymentRequest(BaseModel):
	order_id: int = Field(..., gt=0)
	items: list = Field(..., min_items=1)
	customer_name: str = Field(None)


BASE_DIR = Path(__file__).resolve().parent.parent
CRUD_HTML_PATH = BASE_DIR / "public" / "crud_products.html"
CHAT_HTML_PATH = BASE_DIR / "public" / "chat.html"

try:
	CRUD_HTML = CRUD_HTML_PATH.read_text(encoding="utf-8")
except FileNotFoundError as exc:
	raise RuntimeError(
		f"CRUD interface file not found at {CRUD_HTML_PATH}"
	) from exc

try:
	CHAT_HTML = CHAT_HTML_PATH.read_text(encoding="utf-8")
except FileNotFoundError as exc:
	raise RuntimeError(
		f"Chat interface file not found at {CHAT_HTML_PATH}"
	) from exc


APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))


@app.get("/", response_class=HTMLResponse)
async def read_root() -> str:
		return CRUD_HTML

@app.get("/chat", response_class=HTMLResponse)
async def chat_page() -> str:
		return CHAT_HTML


@app.post("/products")
async def create_product(payload: ProductPayload) -> dict:
		session = get_session()
		try:
				statement = insert(products_table).values(
						name=payload.name,
						price_half_quantity=payload.price_half_quantity,
				)
				session.execute(statement)
				session.commit()
		except SQLAlchemyError as exc:
				session.rollback()
				raise HTTPException(
						status_code=500, detail="Could not save the product"
				) from exc
		finally:
				session.close()

		return {"status": "ok"}


@app.get("/products")
async def list_products() -> dict:
	session = get_session()
	try:
		statement = select(
			products_table.c.id,
			products_table.c.name,
			products_table.c.price_half_quantity,
		).order_by(products_table.c.id.desc())
		rows = session.execute(statement).mappings().all()
		products = [
			{
				"id": row["id"],
				"name": row["name"],
				"price_half_quantity": float(row["price_half_quantity"]),
			}
			for row in rows
		]
	finally:
		session.close()

	return {"items": products}


@app.put("/products/{product_id}")
async def update_product(product_id: int, payload: ProductPayload) -> dict:
	session = get_session()
	try:
		statement = (
			update(products_table)
			.where(products_table.c.id == product_id)
			.values(
				name=payload.name,
				price_half_quantity=payload.price_half_quantity,
			)
		)
		result = session.execute(statement)
		session.commit()
		
		if result.rowcount == 0:
			raise HTTPException(status_code=404, detail="Product not found")
	except SQLAlchemyError as exc:
		session.rollback()
		raise HTTPException(
			status_code=500, detail="Could not update the product"
		) from exc
	finally:
		session.close()

	return {"status": "ok"}


@app.delete("/products/{product_id}")
async def delete_product(product_id: int) -> dict:
	session = get_session()
	try:
		statement = delete(products_table).where(products_table.c.id == product_id)
		result = session.execute(statement)
		session.commit()
		
		if result.rowcount == 0:
			raise HTTPException(status_code=404, detail="Product not found")
	except SQLAlchemyError as exc:
		session.rollback()
		raise HTTPException(
			status_code=500, detail="Could not delete the product"
		) from exc
	finally:
		session.close()

	return {"status": "ok"}


@app.post("/chat")
async def chat_endpoint(request: ChatRequest) -> dict:
	user_id = "4"  # Default user ID for now
	
	session = get_session()
	try:
		# Fetch all products from the database
		products_statement = select(
			products_table.c.name,
			products_table.c.price_half_quantity,
		)
		products_rows = session.execute(products_statement).mappings().all()
		products = [
			{
				"name": row["name"],
				"price_half_quantity": float(row["price_half_quantity"]),
			}
			for row in products_rows
		]
		
		# Get last 10 messages for this user
		history_statement = (
			select(
				conversations_table.c.role,
				conversations_table.c.content,
			)
			.where(conversations_table.c.user_id == user_id)
			.order_by(conversations_table.c.created_at.desc())
			.limit(10)
		)
		history_rows = session.execute(history_statement).mappings().all()
		# Reverse to get chronological order
		conversation_history = [
			{"role": row["role"], "content": row["content"]}
			for row in reversed(list(history_rows))
		]
		
		# Save user message
		user_insert = insert(conversations_table).values(
			user_id=user_id,
			role="user",
			content=request.message,
		)
		session.execute(user_insert)
		session.commit()
		
	except SQLAlchemyError as exc:
		session.rollback()
		session.close()
		raise HTTPException(
			status_code=500, detail="Database error"
		) from exc
	
	try:
		# Get response from AI with product context and conversation history
		response = chat_with_assistant(request.message, products, conversation_history)
		
		# Check if response is JSON (order completed)
		try:
			order_data = json.loads(response)
			
			# Validate it's the expected order JSON structure
			if all(key in order_data for key in ['products', 'total_price', 'address']):
				print(f"Order detected from web chat! Creating payment link...")
				
				# Create payment link with Mercado Pago
				payment_result = create_order_payment_link(
					order_id=hash(user_id) % 1000000,
					items=[
						{
							'name': item['product'],
							'price': item['unit_price'],
							'quantity': item['quantity']
						}
						for item in order_data['products']
					],
					customer_name=f"Cliente Web {user_id}"
				)
				
				if payment_result['success']:
					# Create customer-friendly message with payment link
					products_lines = []
					for item in order_data['products']:
						item_total = item['unit_price'] * item['quantity']
						products_lines.append(f"- {item['product']} x{item['quantity']} - ${item_total:.2f}")
					
					products_list = "\n".join(products_lines)
					
					# Check if it's pickup or delivery
					store_address = os.getenv("ADDRESS", "")
					is_pickup = (store_address and order_data['address'] == store_address)
					delivery_text = "Store Pickup:" if is_pickup else "Delivery Address:"
					
					# Build message with proper line breaks (for web)
					customer_message = (
						"Order Confirmed!\n\n"
						"Order Summary:\n"
						f"{products_list}\n\n"
						f"Total: ${order_data['total_price']:.2f}\n"
						f"{delivery_text} {order_data['address']}\n\n"
						"To complete your purchase, make the payment here:\n"
						f"{payment_result['payment_link']}\n\n"
						"Once payment is completed, we will process your order immediately. Thank you for your purchase!"
					)
					
					# Save the customer message as assistant response
					assistant_insert = insert(conversations_table).values(
						user_id=user_id,
						role="assistant",
						content=customer_message,
					)
					session.execute(assistant_insert)
					session.commit()
					
					return {"response": customer_message}
				else:
					error_message = "Sorry, there was an error creating the payment link. Please try again."
					
					assistant_insert = insert(conversations_table).values(
						user_id=user_id,
						role="assistant",
						content=error_message,
					)
					session.execute(assistant_insert)
					session.commit()
					
					return {"response": error_message}
					
		except (json.JSONDecodeError, KeyError):
			# Not a JSON response, continue with normal flow
			pass
		
		# Save assistant response (normal conversation)
		assistant_insert = insert(conversations_table).values(
			user_id=user_id,
			role="assistant",
			content=response,
		)
		session.execute(assistant_insert)
		session.commit()
		
		return {"response": response}
		
	except Exception as exc:
		session.rollback()
		raise HTTPException(
			status_code=500, detail=f"AI service error: {str(exc)}"
		) from exc
	finally:
		session.close()


@app.post("/payment/create-link")
async def create_payment_link_endpoint(payload: PaymentLinkRequest) -> dict:
	try:
		result = create_payment_link(
			title=payload.title,
			amount=payload.amount,
			description=payload.description,
			quantity=payload.quantity,
			external_reference=payload.external_reference
		)
		
		if not result['success']:
			raise HTTPException(
				status_code=500,
				detail=f"Failed to create payment link: {result.get('error')}"
			)
		
		return result
		
	except Exception as exc:
		raise HTTPException(
			status_code=500,
			detail=f"Payment service error: {str(exc)}"
		) from exc


@app.post("/payment/create-order-link")
async def create_order_payment_link_endpoint(payload: OrderPaymentRequest) -> dict:
	try:
		result = create_order_payment_link(
			order_id=payload.order_id,
			items=payload.items,
			customer_name=payload.customer_name
		)
		
		if not result['success']:
			raise HTTPException(
				status_code=500,
				detail=f"Failed to create order payment link: {result.get('error')}"
			)
		
		return result
		
	except Exception as exc:
		raise HTTPException(
			status_code=500,
			detail=f"Payment service error: {str(exc)}"
		) from exc


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
	request: Request,
	From: str = Form(...),
	Body: str = Form(...),
	MessageSid: str = Form(None)
) -> Response:
	"""
	Webhook endpoint for receiving WhatsApp messages from Twilio.
	Twilio will send POST requests here when messages arrive.
	"""
	# Extract phone number (remove 'whatsapp:' prefix)
	user_phone = From.replace("whatsapp:", "")
	user_message = Body
	
	print(f"Message from {user_phone}: {user_message}")
	
	session = get_session()
	try:
		# Use phone number as user_id for tracking conversations
		user_id = user_phone
		
		# Fetch all products from the database
		products_statement = select(
			products_table.c.name,
			products_table.c.price_half_quantity,
		)
		products_rows = session.execute(products_statement).mappings().all()
		products = [
			{
				"name": row["name"],
				"price_half_quantity": float(row["price_half_quantity"]),
			}
			for row in products_rows
		]
		
		# Get last 10 messages for this user
		history_statement = (
			select(
				conversations_table.c.role,
				conversations_table.c.content,
			)
			.where(conversations_table.c.user_id == user_id)
			.order_by(conversations_table.c.created_at.desc())
			.limit(10)
		)
		history_rows = session.execute(history_statement).mappings().all()
		# Reverse to get chronological order
		conversation_history = [
			{"role": row["role"], "content": row["content"]}
			for row in reversed(list(history_rows))
		]
		
		# Save user message
		user_insert = insert(conversations_table).values(
			user_id=user_id,
			role="user",
			content=user_message,
		)
		session.execute(user_insert)
		session.commit()
		
		# Get response from AI with product context and conversation history
		ai_response = chat_with_assistant(user_message, products, conversation_history)
		
		# Check if response is JSON (order completed)
		try:
			order_data = json.loads(ai_response)
			
			# Validate it's the expected order JSON structure
			if all(key in order_data for key in ['products', 'total_price', 'address']):
				print(f"Order detected! Creating payment link...")
				
				# Create payment link with Mercado Pago
				payment_result = create_order_payment_link(
					order_id=hash(user_phone) % 1000000,  # Generate unique order ID from phone
					items=[
						{
							'name': item['product'],
							'price': item['unit_price'],
							'quantity': item['quantity']
						}
						for item in order_data['products']
					],
					customer_name=f"Cliente {user_phone[-4:]}"
				)
				
				if payment_result['success']:
					# Create customer-friendly message with payment link
					products_lines = []
					for item in order_data['products']:
						item_total = item['unit_price'] * item['quantity']
						products_lines.append(f"- {item['product']} x{item['quantity']} - ${item_total:.2f}")
					
					products_list = "\n".join(products_lines)
					
					# Check if it's pickup or delivery
					store_address = os.getenv("ADDRESS", "")
					is_pickup = (store_address and order_data['address'] == store_address)
					delivery_text = "*Store Pickup:*" if is_pickup else "*Delivery Address:*"
					
					# Build message with proper line breaks
					customer_message = (
						"*Order Confirmed!*\n\n"
						"*Order Summary:*\n"
						f"{products_list}\n\n"
						f"*Total: ${order_data['total_price']:.2f}*\n"
						f"{delivery_text} {order_data['address']}\n\n"
						"*To complete your purchase, make the payment here:*\n"
						f"{payment_result['payment_link']}\n\n"
						"Once payment is completed, we will process your order immediately. Thank you for your purchase!"
					)
					
					# Save the customer message as assistant response
					assistant_insert = insert(conversations_table).values(
						user_id=user_id,
						role="assistant",
						content=customer_message,
					)
					session.execute(assistant_insert)
					session.commit()
					
					# Send payment link to customer
					messenger = get_messenger()
					send_result = messenger.send_message(
						body=customer_message,
						to_number=user_phone
					)
					
					if send_result['success']:
						print(f"Payment link sent to {user_phone}")
					else:
						print(f"Failed to send payment link: {send_result.get('error')}")
				else:
					# Payment link creation failed
					error_message = "Sorry, there was an error creating the payment link. Please try again."
					
					assistant_insert = insert(conversations_table).values(
						user_id=user_id,
						role="assistant",
						content=error_message,
					)
					session.execute(assistant_insert)
					session.commit()
					
					messenger = get_messenger()
					messenger.send_message(
						body=error_message,
						to_number=user_phone
					)
				
				# Return TwiML response
				return Response(
					content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
					media_type="application/xml"
				)
				
		except (json.JSONDecodeError, KeyError):
			# Not a JSON response, continue with normal flow
			pass
		
		# Save assistant response (normal conversation)
		assistant_insert = insert(conversations_table).values(
			user_id=user_id,
			role="assistant",
			content=ai_response,
		)
		session.execute(assistant_insert)
		session.commit()
		
		# Send response back via WhatsApp
		messenger = get_messenger()
		send_result = messenger.send_message(
			body=ai_response,
			to_number=user_phone
		)
		
		if send_result['success']:
			print(f"Response sent to {user_phone}")
		else:
			print(f"Failed to send response: {send_result.get('error')}")
		
		# Return empty TwiML response (Twilio expects XML response)
		return Response(
			content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
			media_type="application/xml"
		)
		
	except Exception as exc:
		session.rollback()
		print(f"Error processing WhatsApp message: {str(exc)}")
		
		# Try to send error message to user
		try:
			messenger = get_messenger()
			messenger.send_message(
				body="Sorry, there was an error processing your message. Please try again.",
				to_number=user_phone
			)
		except:
			pass
		
		# Still return valid TwiML to Twilio
		return Response(
			content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
			media_type="application/xml"
		)
	finally:
		session.close()


if __name__ == "__main__":
	import uvicorn
	uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, reload=True)
