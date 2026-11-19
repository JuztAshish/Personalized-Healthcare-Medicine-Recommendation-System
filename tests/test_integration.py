"""
Cross-Module Integration Test Suite
===================================
Author: Module 3 Lead (Medicine Recommendation Engine)
Project: Personalized Healthcare & Medicine Recommendation System (Zidio Internship)
Test Framework: pytest

Validates:
- Module 1 Data and Vectorizer loading and compatibility.
- Module 2 ML disease prediction model (best_model.pkl) inference.
- Hand-off from Module 2 (Predicted Disease) -> Module 3 (Medicine Recommender).
- Module 3 Flask Adapter (MedicineWebAdapter) with web-style inputs.
- JSON-serializability of responses for Flask jsonify().
- Module 4 Flask application endpoints and route stability.
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from healthcare_webapp.services.flask_adapter import (
    MedicineWebAdapter,
    get_recommendations_for_flask,
    predict_and_recommend,
)
from healthcare_webapp.services.medicine_recommender import (
    CLINICAL_DISCLAIMER,
    MedicineRecommender,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(scope="session")
def web_adapter() -> MedicineWebAdapter:
    """Session-scoped web integration adapter."""
    return MedicineWebAdapter()


# =====================================================================
# Module 1 -> Module 3 Integration
# =====================================================================

class TestModule1ToModule3Integration:
    def test_module1_artifacts_loading(self, web_adapter: MedicineWebAdapter):
        """Verifies Module 1 artifacts are loadable and properly formatted."""
        recommender = web_adapter.recommender
        assert recommender._is_ready is True
        assert len(recommender.df) == 11741
        assert recommender.matrix.shape == (11741, 22284)
        assert len(recommender.vectorizer.vocabulary_) == 22284

    def test_module1_vectorizer_transform_compatibility(self, web_adapter: MedicineWebAdapter):
        """Verifies query transformed by Module 1 vectorizer matches matrix column count."""
        recommender = web_adapter.recommender
        query_vec = recommender.vectorizer.transform(["asthma and shortness of breath"])
        assert query_vec.shape[1] == recommender.matrix.shape[1]
        assert query_vec.nnz > 0


# =====================================================================
# Module 2 -> Module 3 Integration
# =====================================================================

class TestModule2ToModule3Integration:
    def test_module2_model_loading(self, web_adapter: MedicineWebAdapter):
        """Verifies Module 2 best_model.pkl and disease_encoder.pkl load successfully."""
        loaded = web_adapter._ensure_module2_loaded()
        assert loaded is True
        assert web_adapter._disease_model is not None
        assert web_adapter._disease_encoder is not None
        assert web_adapter._symptom_columns is not None
        assert len(web_adapter._symptom_columns) == 377

    def test_module2_actual_disease_inference(self, web_adapter: MedicineWebAdapter):
        """Executes actual Module 2 inference on real symptom combinations."""
        # Test mental health symptoms
        disease_pred, conf = web_adapter.predict_disease(["anxiety_and_nervousness", "depression"])
        assert disease_pred is not None
        assert isinstance(disease_pred, str)
        assert len(disease_pred) > 0
        assert conf > 0.0
        assert disease_pred == "somatization disorder"

        # Test joint pain symptoms
        disease_pred_2, conf_2 = web_adapter.predict_disease(["joint_pain", "knee_pain"])
        assert disease_pred_2 is not None
        assert disease_pred_2 == "chronic knee pain"

    def test_module2_to_module3_hand_off(self, web_adapter: MedicineWebAdapter):
        """Tests end-to-end hand-off: Predicted Disease String -> Module 3 Recommendations."""
        # 1. Predict disease
        disease_pred, _ = web_adapter.predict_disease(["anxiety_and_nervousness", "depression"])
        assert disease_pred == "somatization disorder"

        # 2. Hand off to Module 3
        recs = web_adapter.recommender.get_recommendations(disease=disease_pred, top_k=3)
        assert len(recs) == 3
        assert recs[0]["medicine_name"] != ""
        assert recs[0]["similarity_score"] > 0.0
        assert "disorder" in recs[0]["match_explanation"]


# =====================================================================
# Module 3 -> Module 4 (Flask Adapter) Integration
# =====================================================================

class TestModule3ToModule4FlaskAdapter:
    def test_flask_adapter_string_parsing_for_forms(self, web_adapter: MedicineWebAdapter):
        """Verifies adapter accepts comma-separated string inputs from HTML form POST."""
        result = web_adapter.get_recommendations_for_flask(
            disease="Bacterial infections",
            allergies="Amoxycillin, Penicillin",
            conditions="Vomiting, Dizziness",
            top_k="3",
            filter_allergies=True,
        )
        assert result["status"] == "success"
        assert result["query"]["allergies"] == ["Amoxycillin", "Penicillin"]
        assert result["query"]["conditions"] == ["Vomiting", "Dizziness"]
        assert result["query"]["top_k"] == 3
        assert len(result["recommendations"]) <= 3

        # Verify no allergen leakage
        for rec in result["recommendations"]:
            assert rec["safety_assessment"]["allergy_detected"] is False

    def test_flask_adapter_predict_and_recommend(self, web_adapter: MedicineWebAdapter):
        """Verifies full end-to-end pipeline via adapter."""
        result = web_adapter.predict_and_recommend(
            symptoms=["anxiety_and_nervousness", "depression"],
            allergies=["Aspirin"],
            conditions=["Nausea"],
            top_k=3,
        )
        assert result["status"] == "success"
        assert result["predicted_disease"] == "somatization disorder"
        assert result["prediction_confidence"] > 0.0
        assert len(result["recommendations"]) == 3
        assert "clinical_disclaimer" in result

    def test_flask_adapter_json_serializability(self, web_adapter: MedicineWebAdapter):
        """Critical for Flask: Confirms response payload can be serialized by json.dumps / jsonify."""
        result = web_adapter.predict_and_recommend(
            symptoms=["anxiety_and_nervousness", "depression"],
            allergies=["Aspirin"],
            top_k=2,
        )
        # Must not raise TypeError: Object of type float32/int64 is not JSON serializable
        serialized = json.dumps(result)
        assert len(serialized) > 0
        deserialized = json.loads(serialized)
        assert deserialized["status"] == "success"
        assert deserialized["count"] == 2

    def test_flask_adapter_empty_symptoms_error(self, web_adapter: MedicineWebAdapter):
        """Verifies graceful error dictionary when symptom input is empty."""
        result = web_adapter.predict_and_recommend(symptoms=[])
        assert result["status"] == "error"
        assert result["predicted_disease"] is None
        assert result["count"] == 0
        assert result["recommendations"] == []

    def test_module4_existing_flask_routes_stability(self):
        """Verifies Flask application routes execute cleanly without modifying Module 4."""
        from healthcare_webapp.app import app
        app.testing = True
        client = app.test_client()

        for route in ["/", "/about", "/login", "/register"]:
            res = client.get(route)
            assert res.status_code == 200, f"Route {route} failed with status {res.status_code}"
