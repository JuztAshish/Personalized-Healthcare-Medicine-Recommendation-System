"""
Services package for healthcare web application.
Includes standalone recommendation and clinical decision support services.
"""

from .medicine_recommender import CLINICAL_DISCLAIMER, MedicineRecommender
from .flask_adapter import (
    MedicineWebAdapter,
    get_recommendations_for_flask,
    get_web_adapter,
    predict_and_recommend,
)

__all__ = [
    "MedicineRecommender",
    "MedicineWebAdapter",
    "CLINICAL_DISCLAIMER",
    "get_recommendations_for_flask",
    "predict_and_recommend",
    "get_web_adapter",
]
