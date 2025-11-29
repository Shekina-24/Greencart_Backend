# GreenCart â€” Backend (FastAPI)

## DÃ©marrage rapide (Windows + VS Code)

1. Ouvre ce dossier dans VS Code.
2. CrÃ©e un environnement virtuel :
   ```
   py -m venv .venv
   .venv\Scripts\activate
   ```
3. Installe les dÃ©pendances :
   ```
   pip install -r requirements.txt
   ```
4. Copie `.env.example` vers `.env` (optionnel pour commencer) :
   ```
   copy .env.example .env
   ```
5. Lance le serveur :
   ```
   uvicorn app.main:app --reload
   ```
6. Va sur la doc interactive :
   - http://127.0.0.1:8000/docs

## Endpoints clÃ©s
- `GET /api/health` â€” statut
- `POST /api/auth/register` â€” crÃ©er un compte
- `POST /api/auth/login` â€” obtenir un token (OAuth2 password)
- `GET /api/auth/me` â€” profil (token requis)
- `GET /api/products` â€” lister les produits
- `POST /api/products` â€” crÃ©er un produit (token requis)
- `GET /api/cart` â€” voir mon panier (token requis)
- `POST /api/cart` â€” ajouter au panier (token requis)
- `DELETE /api/cart/{item_id}` â€” retirer du panier (token requis)

## IntÃ©gration front (exemple JS)
```js
// Liste produits
fetch('http://127.0.0.1:8000/api/products')
  .then(r => r.json())
  .then(data => console.log(data))
```

## Indices / Performance Analytics

- Index sur orders.created_at (Alembic): ix_orders_created_at
- Migration: \lembic upgrade head\`n
## CI (minimal)

Un workflow GitHub Actions exécute un build front et des tests backend (permissifs) : .github/workflows/ci.yml.
