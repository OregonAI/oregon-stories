"""Tests import the story modules the way build.py does — from the repo root, which is
not on sys.path when pytest is invoked from anywhere else."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
