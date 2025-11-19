"""wsAWS package initializer.

This file makes `wsAWS` a proper Python package so Lambda can import
`wsAWS.scrap_table` when the container is built and the awslambdaric
tries to import the handler.
"""

__all__ = ["scrap_table"]
