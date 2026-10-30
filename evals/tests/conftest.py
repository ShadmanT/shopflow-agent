"""Shared pytest setup: make the eval package importable from the test files."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
