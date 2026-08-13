class InventoryMovementError(Exception):
    """Base error for inventory movement failures."""


class InvalidQuantityError(InventoryMovementError):
    pass


class InvalidTransactionTypeError(InventoryMovementError):
    pass


class InvalidInventoryUserError(InventoryMovementError):
    pass


class InventoryItemNotFoundError(InventoryMovementError):
    pass


class InactiveItemError(InventoryMovementError):
    pass


class InsufficientStockError(InventoryMovementError):
    pass
