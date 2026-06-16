#!/usr/bin/env python
"""Quick test to verify analyze_multi endpoint exists"""
import sys
import os

# Add the project to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "imdb_project.settings")
import django
django.setup()

from rest_framework.routers import DefaultRouter
from apps.products.views import IMDBRecordViewSet

# Create router and register viewset
router = DefaultRouter()
router.register(r"products", IMDBRecordViewSet, basename="products")

# Print all registered routes
print("\n=== Registered Routes ===")
for pattern in router.urls:
    print(f"{pattern.pattern} -> {pattern.name}")

print("\n=== ViewSet Actions ===")
viewset = IMDBRecordViewSet()
for action_name in dir(viewset):
    attr = getattr(viewset, action_name)
    if hasattr(attr, 'mapping'):
        print(f"Action: {action_name} -> {attr.mapping}")
