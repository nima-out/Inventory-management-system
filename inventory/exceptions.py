class InventoryMovementError(Exception):
    """Base error for inventory movement failures."""


class InvalidQuantityError(InventoryMovementError):
    pass


class InvalidTransactionTypeError(InventoryMovementError):
    pass


class InvalidInventoryUserError(InventoryMovementError):
    pass


class InventoryPermissionDeniedError(Exception):
    """Raised when an actor lacks permission for an operation."""


class InventoryItemNotFoundError(InventoryMovementError):
    pass


class InactiveItemError(InventoryMovementError):
    pass


class InsufficientStockError(InventoryMovementError):
    pass


class CatalogError(Exception):
    """Base error for category and item lifecycle failures."""


class InvalidCatalogNameError(CatalogError):
    pass


class DuplicateCategoryNameError(CatalogError):
    pass


class CategoryNotFoundError(CatalogError):
    pass


class CategoryInUseError(CatalogError):
    pass


class DuplicateItemNameError(CatalogError):
    pass


class InvalidReorderLevelError(CatalogError):
    pass
