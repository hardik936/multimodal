"""
Quick script to create evaluation tables in the database.
Run this once to set up the evaluation harness tables.
"""
from app.database import engine
from app.eval.store import Base

# Create all tables defined in the eval module
Base.metadata.create_all(bind=engine)

print("✅ Evaluation tables created successfully!")
