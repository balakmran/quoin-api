# Creating a Module

Build a `product` module end to end: table, migration, schemas,
repository, service, and routes, following the `user` module. Layers
only call downward: routes call services, services call repositories.

!!! tip "Scaffold first"
    Run `just new product` before the steps below. It creates the
    module package, its `app/api.py` registration, a reference page at
    `docs/api/product.md`, and skeleton tests, all passing `just check`
    from the start. Only `models.py` is empty, because a real table needs
    a migration. Replace each stub as you go.

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
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator
from pydantic.json_schema import SkipJsonSchema


class ProductBase(BaseModel):
    """Shared product fields."""

    name: str
    price: float


class ProductCreate(ProductBase):
    """Schema for creating a product."""

    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product (all fields optional, none null)."""

    name: str | SkipJsonSchema[None] = None
    price: float | SkipJsonSchema[None] = None
    is_active: bool | SkipJsonSchema[None] = None

    @field_validator("name", "price", "is_active")
    @classmethod
    def _reject_null(cls, value: object) -> object:
        """Reject an explicit null; omit the field to leave it unchanged."""
        if value is None:
            raise ValueError("must not be null; omit the field instead")
        return value


class ProductRead(ProductBase):
    """Schema for reading a product."""

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

!!! warning "Optional is not nullable"

    In an update schema, `None` should only ever mean "omitted". Pydantic
    accepts a literal `null` for a `T | None` field, and
    `model_dump(exclude_unset=True)` passes it through. For a `NOT NULL`
    column, the flush then fails and the client gets a 500.

    For every non-nullable column:

    - Reject `None` in a validator. Validators don't run on defaults,
      so omitting the field still works.
    - Wrap `None` in `SkipJsonSchema` so OpenAPI doesn't advertise
      `null`.

    A nullable column keeps a plain `T | None`, and there `null` clears
    the value.

### 4. Define Domain Exceptions

```python
# app/modules/product/exceptions.py
from app.core.exceptions import NotFoundError


class ProductNotFoundError(NotFoundError):
    """Raised when a product cannot be found."""

    def __init__(self, product_id: str) -> None:
        """Initialize ProductNotFoundError."""
        super().__init__(message=f"Product with ID '{product_id}' not found")
```

### 5. Implement the Repository

Database operations only — no business logic here. Repositories
`flush()`, never `commit()`: `get_session` wraps each request in a unit
of work that commits on success and rolls back if anything raises, so a
service that touches several repositories stays atomic.

```python
# app/modules/product/repository.py
import uuid

from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.pagination import PageParams
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
        await self.session.flush()
        await self.session.refresh(db_product)
        return db_product

    async def get(self, product_id: uuid.UUID) -> Product | None:
        """Get a product by ID."""
        return await self.session.get(Product, product_id)

    async def list(self, params: PageParams) -> tuple[list[Product], int]:
        """List products for one page, plus the total count.

        Returns a ``(rows, total)`` tuple so the route can build the
        standard `Page` envelope. See the
        [Pagination guide](pagination.md) for sort/filter conventions.
        """
        rows_stmt = (
            select(Product)
            .order_by(Product.created_at, Product.id)  # type: ignore
            .offset(params.offset)
            .limit(params.limit)
        )
        result = await self.session.exec(rows_stmt)  # type: ignore
        rows = list(result.scalars().all())

        count_stmt = select(func.count()).select_from(Product)
        total = (await self.session.exec(count_stmt)).scalars().one()  # type: ignore
        return rows, total

    async def update(
        self, product: Product, product_update: ProductUpdate
    ) -> Product:
        """Update a product."""
        product_data = product_update.model_dump(exclude_unset=True)
        for key, value in product_data.items():
            setattr(product, key, value)
        self.session.add(product)
        await self.session.flush()
        await self.session.refresh(product)
        return product

    async def delete(self, product: Product) -> None:
        """Delete a product."""
        await self.session.delete(product)
        await self.session.flush()
```

This `delete` is a hard delete to keep the example short. The `user`
module soft-deletes instead; see the [Soft Delete guide](soft-delete.md)
if rows should be recoverable.

### 6. Implement the Service

Business logic only — call the repository, raise domain exceptions:

```python
# app/modules/product/service.py
import uuid

from app.core.pagination import PageParams
from app.modules.product.exceptions import ProductNotFoundError
from app.modules.product.models import Product
from app.modules.product.repository import ProductRepository
from app.modules.product.schemas import ProductCreate, ProductUpdate


class ProductService:
    """Service for Product business logic."""

    def __init__(self, repository: ProductRepository) -> None:
        """Initialize the service."""
        self.repository = repository

    async def create_product(self, product_create: ProductCreate) -> Product:
        """Create a new product."""
        return await self.repository.create(product_create)

    async def get_product(self, product_id: uuid.UUID) -> Product:
        """Get a product by ID."""
        product = await self.repository.get(product_id)
        if not product:
            raise ProductNotFoundError(product_id=str(product_id))
        return product

    async def list_products(
        self, params: PageParams
    ) -> tuple[list[Product], int]:
        """List a page of products and the total count."""
        return await self.repository.list(params)

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

!!! warning "Auth omitted for brevity"
    The example below shows routes without `require_roles()` to keep it
    focused on structure. **A route without it is open to any caller** —
    auth here is opt-in per route, not default-deny. Add the dependency
    to every endpoint before shipping, as shown in the [user module](https://github.com/balakmran/quoin-api/tree/main/app/modules/user/routes.py)
    and documented in the [Authentication guide](authentication.md).

```python
# app/modules/product/routes.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.openapi import DEFAULT_ERROR_RESPONSES, error_responses
from app.core.pagination import Page, PageParams
from app.db.session import SessionDep
from app.modules.product.models import Product
from app.modules.product.repository import ProductRepository
from app.modules.product.schemas import (
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.modules.product.service import ProductService

router = APIRouter(
    prefix="/products",
    tags=["products"],
    responses=DEFAULT_ERROR_RESPONSES,
)


def get_product_service(session: SessionDep) -> ProductService:
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


@router.get("/", response_model=Page[ProductRead])
async def list_products(
    service: Annotated[ProductService, Depends(get_product_service)],
    page: Annotated[PageParams, Depends()],
) -> Page[Product]:
    """List products with pagination."""
    rows, total = await service.list_products(page)
    return Page.create(rows, total, page)


@router.get(
    "/{product_id}",
    response_model=ProductRead,
    responses=error_responses(404, descriptions={404: "Product not found"}),
)
async def get_product(
    product_id: uuid.UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Product:
    """Get a product by ID."""
    return await service.get_product(product_id)


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    responses=error_responses(404, descriptions={404: "Product not found"}),
)
async def update_product(
    product_id: uuid.UUID,
    product_update: ProductUpdate,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Product:
    """Update a product."""
    return await service.update_product(product_id, product_update)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404, descriptions={404: "Product not found"}),
)
async def delete_product(
    product_id: uuid.UUID,
    service: Annotated[ProductService, Depends(get_product_service)],
) -> None:
    """Delete a product."""
    await service.delete_product(product_id)
```

### 8. Review the Scaffolded Wiring

`just new product` already exports `router` from
`app/modules/product/__init__.py` and includes it in `v1_router` in
`app/api.py`. Check both, but don't add a second import or
`include_router()` call.

### 9. Import the Model for Migrations

Alembic finds tables through `app/db/base.py`, which `alembic/env.py`
imports. `just new` doesn't touch it, so add the model yourself:

```python
# app/db/base.py
from app.modules.user.models import User  # noqa
from app.modules.product.models import Product  # noqa
```

## Testing

`just new` creates `tests/modules/product/` with `test_routes.py` and
`test_service.py`. Drive the module through its routes first; they
exercise every layer against the real database:

```python
# tests/modules/product/test_routes.py
async def test_create_product(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/products/",
        json={"name": "Widget", "price": 9.99},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Widget"


async def test_get_product_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/products/{uuid.uuid4()}")
    assert response.status_code == 404
```

Once the routes call `require_roles()`, switch to `read_client` and
`admin_client`. See [Testing](testing.md) for the fixtures.

## Checklist

- [ ] `models.py` — SQLModel table defined
- [ ] Migration generated and applied (`just migrate-gen`, `just migrate-up`)
- [ ] `schemas.py` — Create, Update, Read schemas
- [ ] `exceptions.py` — Domain exceptions inherit from core ones
- [ ] `repository.py` — CRUD operations only, no business logic
- [ ] `service.py` — Business logic only, raises domain exceptions
- [ ] `routes.py` — FastAPI router, calls service via dependency
- [ ] `__init__.py` and `app/api.py` — scaffolded wiring reviewed
- [ ] `app/db/base.py` — Model imported so Alembic can detect schema changes
- [ ] Tests written in `tests/modules/<name>/`
- [ ] `just check` passes

## See Also

- [Error Handling](error-handling.md) — Exception hierarchy and patterns
- [Database Migrations](database-migrations.md) — Managing schema changes
- [Testing](testing.md) — Writing integration and unit tests
- [User Module](https://github.com/balakmran/quoin-api/tree/main/app/modules/user)
  — Reference implementation
