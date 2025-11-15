# Orderflow Service

![A pixel art anime style illustration of a cozy empanada shop storefront. The scene shows a small Argentine restaurant with warm lighting and a cheerful atmosphere. In the foreground, a cute anime-style character (shopkeeper) with big expressive eyes is holding a smartphone showing a chat interface with order messages. On the counter, there are golden empanadas displayed on plates. Behind the character, there's a wall menu board showing product names and  prices. A small Mercado Pago logo is visible on the counter. The color palette is warm and inviting with golden browns, soft yellows, and pastel colors. The art style should be 16-bit retro pixel art with anime character proportions, reminiscent of classic SNES games. Include small pixel art details like a  WhatsApp notification bubble floating above the phone, and payment success  icons. The overall mood is friendly, modern, and nostalgic.](./public/unnamed.jpg)

Lightweight web service for registering products in a MySQL database. 

## Initial setup
1. Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r src/requirements.txt
```
3. Copy `.env.example` to `.env` and adjust the values:

```bash
cp .env.example .env
```

## Run the project

```bash
python src/main.py
```
