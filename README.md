# Orderflow Service

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
