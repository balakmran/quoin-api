# Creating a Module

This guide walks through adding a new feature module end-to-end,
following the same patterns used by the existing `user` module.

> All feature modules live in `app/modules/<name>/` and follow a
> strict layered structure. Never skip layers — services call
> repositories, routes call services, never the reverse.

---

## Module Structure

Every module is a self-contained package:

```
app/modules/<name>/
├── __init__.py       # Export router
├── models.py         # SQLModel database table
├── schemas.py        # Pydantic request/response shapes
├── exceptions.py     # Domain-specific exceptions
├── repository.py     # Database CRUD operations
├── service.py        # Business logic
└── routes.py         # FastAPI endpoints
```

---

## Step-by-Step: Adding a `product` Module

### 1. Define the Model

Create the SQLModel table in `app/modules/product/models.py`:

```python
# app/modules/product/models.py
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    """Product model."""

    __tablename__ = "products"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255)
    price: float = Field(ge=0)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(UTC),
        ),
    )
```

### 2. Generate the Migration

```bash
just migrate-gen "add products table"
```

Review the generated file in `alembic/versions/` before applying:

```bash
just migrate-up
```

### 3. Define Schemas

Keep request/response shapes separate from the database model:

```python
# app/modules/product/schemas.py
from pydantic import BaseModel


class ProductBase(BaseModel):
    """Shared product fields."""

    name: str
    price: float


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product (all fields optional)."""

    name: str | None = None
    price: float | None = None
    is_active: bool | None = None


class ProductRead(ProductBase):
    """Schema for reading a product."""

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

### 4. Define Domain Exceptions

```python
# app/modules/product/exceptions.py
from app.core.exceptions import ConflictError, NotFoundError


class ProductNotFoundError(NotFoundError):
    """Raised when a product cannot be found."""

    def __init__(self, product_id: str) -> None:
        """Initialize ProductNotFoundError."""
        super().__init__(
            message=f"Product with ID '{product_id}' not found"
        )


class DuplicateProductNameError(ConflictError):
    """Raised when a product name already exists."""

    def __init__(self, name: str) -> None:
        """Initialize DuplicateProductNameError."""
        super().__init__(
            message=f"Product '{name}' already exists"
        )
```

### 5. Implement the Repository

Database operations only — no business logic here:

```python
# app/modules/product/repository.py
import uuid

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.product.models import Product
from app.modules.product.schemas import ProductCreate, ProductUpdate


class ProductRepository:
    """Repository for Product database operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository."""
        self.session = session

    async def create(self, product_create: ProductCreate) -> Product:
        """Create a new product."""
        db_product = Product.model_validate(product_create)
        self.session.add(db_product)
        await self.session.commit()
        await self.session.refresh(db_product)
        return db_product

    async def get(self, product_id: uuid.UUID) -> Product | None:
        """Get a product by ID."""
        return await self.session.get(Product, product_id)

    async def get_by_name(self, name: str) -> Product | None:
        """Get a product by name."""
        statement = select(Product).where(Product.name == name)
        result = await self.session.exec(statement)  # type: ignore
        return result.scalars().first()

    async def list(
        self, skip: int = 0, limit: int = 100
    ) -> list[Product]:
        """List products with pagination."""
        statement = select(Product).offset(skip).limit(limit)
        result = await self.session.exec(statement)  # type: ignore
        return list(result.scalars().all())

    async def update(
        self, product: Product, product_update: ProductUpdate
    ) -> Product:
        """Update a product."""
        product_data = product_update.model_dump(exclude_unset=True)
        for key, value in product_data.items():
            setattr(product, key, value)
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        """Delete a product."""
        await self.session.delete(product)
        await self.session.commit()
```

### 6. Implement the Service

Business logic only — call the repository, raise domain exceptions:

```python
# app/modules/product/service.py
import uuid

from app.modules.product.exceptions import ProductNotFoundError
from app.modules.product.models import Product
from app.modules.product.repository import ProductRepository
from app.modules.product.schemas import ProductCreate, ProductUpdate


class ProductService:
    """Service for Product business logic."""

    def __init__(self, repository: ProductRepository) -> None:
        """Initialize the service."""
        self.repository = repository

    async def create_product(
        self, product_create: ProductCreate
    ) -> Product:
        """Create a new product."""
        return await self.repository.create(product_create)

    async def get_product(self, product_id: uuid.UUID) -> Product:
        """Get a product by ID."""
        product = await self.repository.get(product_id)
        if not product:
            raise ProductNotFoundError(product_id=str(product_id))
        return product

    async def list_products(
        self, skip: int = 0, limit: int = 100
    ) -> list[Product]:
        """List all products."""
        return await self.repository.list(skip, limit)

    async def update_product(
        self, product_id: uuid.UUID, product_update: ProductUpdate
    ) -> Product:
        """Update a product."""
        product = await self.get_product(product_id)
        return await self.repository.update(product, product_update)

    async def delete_product(self, product_id: uuid.UUID) -> None:
        """Delete a product."""
        product = await self.get_product(product_id)
        await self.repository.delete(product)
```

### 7. Create the Router

```python
# app/modules/product/routes.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_session
from app.modules.product.repository import ProductRepository
from app.modules.product.schemas import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.modules.product.service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


def get_product_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductService:
    """Instantiate ProductService with its dependencies."""
    repository = ProductRepository(session)
    return ProductService(repository)


@router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    product_create: ProductCreate,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Product:
    """Create a new product."""
    return await service.create_product(product_create)


@router.get("/", response_model=list[ProductRead])
async def list_products(
    service: Annotated[ProductService, Depends(get_product_service)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[Product]:
    """List all products."""
    return await service.list_products(skip, limit)


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: uuid.UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Product:
    """Get a product by ID."""
    return await service.get_product(product_id)


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    product_update: ProductUpdate,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Product:
    """Update a product."""
    return await service.update_product(product_id, product_update)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> None:
    """Delete a product."""
    await service.delete_product(product_id)
```

### 8. Export the Router

```python
# app/modules/product/__init__.py
from app.modules.product.routes import router

__all__ = ["router"]
```

### 9. Register with the API

Add the module router to `app/api.py`:

```python
# app/api.py
from app.modules.product import router as product_router
from app.modules.user import router as user_router

v1_router = APIRouter()
v1_router.include_router(user_router)
v1_router.include_router(product_router)  # Add this line
```

### 10. Import the Model for Migrations

Ensure Alembic can discover the model by importing it in
`alembic/env.py`:

```python
# alembic/env.py
from app.modules.user.models import User
from app.modules.product.models import Product  # Add this line
```

---

## Testing

Add tests mirroring the module structure:

```
tests/modules/product/
├── conftest.py          # Fixtures (product_create, sample_product)
├── test_models.py       # Pydantic validation
├── test_repository.py   # Database operations (uses db_session)
├── test_service.py      # Business logic
└── test_routes.py       # API integration tests (uses client)
```

Minimal route test to get started:

```python
# tests/modules/product/test_routes.py
async def test_create_product(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/products/",
        json={"name": "Widget", "price": 9.99},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Widget"
    assert "id" in data

async def test_get_product_not_found(client: AsyncClient) -> None:
    response = await client.get(
        f"/api/v1/products/{uuid.uuid4()}"
    )
    assert response.status_code == 404
```

---

## Checklist

- [ ] `models.py` — SQLModel table defined
- [ ] Migration generated and applied (`just migrate-gen`, `just migrate-up`)
- [ ] `schemas.py` — Create, Update, Read schemas
- [ ] `exceptions.py` — Domain exceptions inherit from `QuoinError`
- [ ] `repository.py` — CRUD operations only, no business logic
- [ ] `service.py` — Business logic only, raises domain exceptions
- [ ] `routes.py` — FastAPI router, calls service via dependency
- [ ] `__init__.py` — Exports `router`
- [ ] `app/api.py` — Router registered under `v1_router`
- [ ] `alembic/env.py` — Model imported for migration detection
- [ ] Tests written in `tests/modules/<name>/`
- [ ] `just check` passes

---

## See Also

- [Error Handling](error-handling.md) — Exception hierarchy and patterns
- [Database Migrations](database-migrations.md) — Managing schema changes
- [Testing](testing.md) — Writing integration and unit tests
- [User Module](https://github.com/balakmran/quoin-api/tree/main/app/modules/user)
  — Reference implementation
