"""Pipeline package: ETL between staging tables and into transactions."""

from .routes import router

__all__ = ["router"]
