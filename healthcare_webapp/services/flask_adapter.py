"""
Module 3: Flask Integration Adapter & Controller Helper
========================================================
Author: Module 3 Lead (Medicine Recommendation Engine)
Project: Personalized Healthcare & Medicine Recommendation System (Zidio Internship)

This module provides a production-grade adapter specifically designed for Member 4 (Web Application)
to easily connect the Flask application to Module 3 (Medicine Recommendation) and Module 2 (Disease Prediction)
without needing to manage machine learning, sparse matrix, or vectorizer internals.

Ownership: Module 3 (Services Package)
Usage in Flask (Member 4):
    from healthcare_webapp.services.flask_adapter import (
        get_recommendations_for_flask,
        predict_and_recommend,
        format_for_jinja_template
    )
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd

from .medicine_recommender import CLINICAL_DISCLAIMER, MedicineRecommender


class MedicineWebAdapter:
    """
    Adapter providing web-friendly interfaces and data transformations for Flask controllers.
    """

    def __init__(self, recommender: Optional[MedicineRecommender] = None) -> None:
        """Initialize adapter with an existing or new MedicineRecommender instance."""
        self.recommender = recommender or MedicineRecommender()
        self.repo_root = self.recommender.repo_root
        
        # Module 2 disease prediction model references (lazily loaded)
        self._disease_model = None
        self._disease_encoder = None
        self._symptom_columns = None

    def _ensure_module2_loaded(self) -> bool:
        """Safely loads Module 2 disease prediction model and encoder if available."""
        if self._disease_model is not None and self._disease_encoder is not None:
            return True

        model_path = self.repo_root / "models" / "best_model.pkl"
        encoder_path = self.repo_root / "models" / "disease_encoder.pkl"
        dataset_path = self.repo_root / "datasets" / "processed" / "Cleaned_Dataset_validated.csv"

        if not model_path.exists() or not encoder_path.exists():
            return False

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._disease_model = joblib.load(model_path)
            self._disease_encoder = joblib.load(encoder_path)

        if dataset_path.exists():
            df_cols = pd.read_csv(dataset_path, nrows=1)
            self._symptom_columns = [c for c in df_cols.columns if c != "diseases"]

        return True

    def predict_disease(self, symptoms_list: List[str]) -> Tuple[Optional[str], float]:
        """
        Executes actual Module 2 machine learning inference on input symptoms.
        
        Args:
            symptoms_list: List of symptom column names (e.g. ['shortness_of_breath', 'cough']).
            
        Returns:
            (predicted_disease_name, confidence_estimate)
        """
        if not self._ensure_module2_loaded() or not self._symptom_columns:
            return None, 0.0

        if not symptoms_list:
            return None, 0.0

        input_data = [1 if col in symptoms_list else 0 for col in self._symptom_columns]
        input_array = np.array(input_data).reshape(1, -1)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pred_idx = self._disease_model.predict(input_array)[0]
            predicted_disease = self._disease_encoder.inverse_transform([pred_idx])[0]

            # If model supports predict_proba, extract probability of predicted class
            confidence = 1.0
            if hasattr(self._disease_model, "predict_proba"):
                try:
                    probs = self._disease_model.predict_proba(input_array)[0]
                    confidence = round(float(np.max(probs)), 4)
                except Exception:
                    confidence = 1.0

        return str(predicted_disease), confidence

    def get_recommendations_for_flask(
        self,
        disease: Optional[str] = None,
        allergies: Optional[Union[str, List[str]]] = None,
        conditions: Optional[Union[str, List[str]]] = None,
        top_k: int = 5,
        filter_allergies: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Primary controller function for Flask routes (form post or query params).
        
        Handles string parsing (e.g. comma-separated form fields), validation,
        and returns a standardized dictionary ready for Jinja2 template rendering or JSON response.
        Supports both standard argument names and aliases (disease_name, allergies_input, conditions_input).
        """
        # Resolve argument aliases for maximum developer convenience
        target_disease = disease if disease is not None else kwargs.get("disease_name", "")
        raw_allergies = allergies if allergies is not None else kwargs.get("allergies_input")
        raw_conditions = conditions if conditions is not None else kwargs.get("conditions_input")

        # Parse comma-separated allergy strings if received from HTML form input
        parsed_allergies: List[str] = []
        if isinstance(raw_allergies, str):
            parsed_allergies = [a.strip() for a in raw_allergies.split(",") if a.strip()]
        elif isinstance(raw_allergies, list):
            parsed_allergies = [str(a).strip() for a in raw_allergies if a and str(a).strip()]

        # Parse comma-separated condition strings if received from HTML form input
        parsed_conditions: List[str] = []
        if isinstance(raw_conditions, str):
            parsed_conditions = [c.strip() for c in raw_conditions.split(",") if c.strip()]
        elif isinstance(raw_conditions, list):
            parsed_conditions = [str(c).strip() for c in raw_conditions if c and str(c).strip()]

        # Sanitize top_k
        try:
            k = max(1, min(int(top_k), 50))
        except (ValueError, TypeError):
            k = 5

        # Execute recommendation engine
        recommendations = self.recommender.get_recommendations(
            disease=target_disease,
            patient_allergies=parsed_allergies,
            patient_conditions=parsed_conditions,
            top_k=k,
            filter_allergies=filter_allergies,
        )

        return {
            "status": "success",
            "query": {
                "disease": target_disease,
                "allergies": parsed_allergies,
                "conditions": parsed_conditions,
                "top_k": k,
                "filter_allergies": filter_allergies,
            },
            "count": len(recommendations),
            "recommendations": recommendations,
            "clinical_disclaimer": CLINICAL_DISCLAIMER,
        }

    def predict_and_recommend(
        self,
        symptoms: Optional[List[str]] = None,
        allergies: Optional[Union[str, List[str]]] = None,
        conditions: Optional[Union[str, List[str]]] = None,
        top_k: int = 5,
        filter_allergies: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Full end-to-end pipeline:
        Symptoms -> Module 2 Disease Prediction -> Module 3 Medicine Recommendation.
        Supports both positional/keyword arguments and aliases (symptoms_list, allergies_input, conditions_input).
        """
        target_symptoms = symptoms if symptoms is not None else kwargs.get("symptoms_list", [])
        if isinstance(target_symptoms, str):
            target_symptoms = [s.strip() for s in target_symptoms.split(",") if s.strip()]

        predicted_disease, confidence = self.predict_disease(target_symptoms)

        if not predicted_disease:
            return {
                "status": "error",
                "message": "Unable to predict disease. Verify symptom inputs.",
                "predicted_disease": None,
                "confidence": 0.0,
                "count": 0,
                "recommendations": [],
                "clinical_disclaimer": CLINICAL_DISCLAIMER,
            }

        rec_result = self.get_recommendations_for_flask(
            disease=predicted_disease,
            allergies=allergies,
            conditions=conditions,
            top_k=top_k,
            filter_allergies=filter_allergies,
            **kwargs,
        )

        rec_result["predicted_disease"] = predicted_disease
        rec_result["prediction_confidence"] = confidence
        return rec_result


# Singleton instance for quick zero-boilerplate import in Flask routes
_default_adapter: Optional[MedicineWebAdapter] = None

def get_web_adapter() -> MedicineWebAdapter:
    """Returns a shared MedicineWebAdapter instance."""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = MedicineWebAdapter()
    return _default_adapter


def get_recommendations_for_flask(
    disease: Optional[str] = None,
    allergies: Optional[Union[str, List[str]]] = None,
    conditions: Optional[Union[str, List[str]]] = None,
    top_k: int = 5,
    filter_allergies: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Convenience functional wrapper for Flask view controllers."""
    return get_web_adapter().get_recommendations_for_flask(
        disease=disease,
        allergies=allergies,
        conditions=conditions,
        top_k=top_k,
        filter_allergies=filter_allergies,
        **kwargs,
    )


def predict_and_recommend(
    symptoms: Optional[List[str]] = None,
    allergies: Optional[Union[str, List[str]]] = None,
    conditions: Optional[Union[str, List[str]]] = None,
    top_k: int = 5,
    filter_allergies: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Convenience functional wrapper for end-to-end symptom-to-recommendation pipeline."""
    return get_web_adapter().predict_and_recommend(
        symptoms=symptoms,
        allergies=allergies,
        conditions=conditions,
        top_k=top_k,
        filter_allergies=filter_allergies,
        **kwargs,
    )
