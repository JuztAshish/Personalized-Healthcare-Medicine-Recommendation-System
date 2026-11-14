"""
Automated Test Suite for Module 3: MedicineRecommender Service
==============================================================
Author: Module 3 Lead (Medicine Recommendation Engine)
Project: Personalized Healthcare & Medicine Recommendation System (Zidio Internship)
Test Framework: pytest

This suite covers:
A. Initialization, Path Resolution, and Matrix-Dataset Alignment
B. Text Normalization, Preprocessing, and Vocabulary Compatibility
C. Recommendation Engine Core Retrieval, Scoring, and Edge Cases
D. Conservative Allergy Screening, Flagging, and Filtering
E. Preliminary Patient Condition Warnings vs Contraindications
F. Experimental Heuristic Ranking (85/15 Formula) and Score Separation
G. Error Handling, Parameter Validation, and Mock Unit Isolation
"""

from __future__ import annotations

import os
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest
from scipy.sparse import csr_matrix, save_npz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from healthcare_webapp.services.medicine_recommender import (
    CLINICAL_DISCLAIMER,
    MedicineRecommender,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(scope="session")
def production_recommender() -> MedicineRecommender:
    """Session-scoped real production recommender reusing Module 1 artifacts."""
    return MedicineRecommender()


@pytest.fixture
def mock_medicine_data(tmp_path: Path):
    """Creates a small isolated dataset and matrix for isolated unit tests."""
    data = {
        "medicine_name": ["MedA 100mg", "MedB Syrup", "MedC Capsule"],
        "composition": [
            "Amoxycillin (500mg) + Clavulanic Acid (125mg)",
            "Paracetamol (250mg)",
            "Ibuprofen (400mg)",
        ],
        "uses": [
            "Treatment of Bacterial infections and respiratory illness",
            "Relief of fever and mild to moderate pain",
            "Treatment of inflammation and joint pain",
        ],
        "side_effects": [
            "Vomiting, Nausea, Diarrhea",
            "Dizziness, Sleepiness",
            "Stomach upset, High blood pressure",
        ],
        "image_url": ["http://example.com/a.jpg", "", "http://example.com/c.jpg"],
        "manufacturer": ["PharmaCorp", "HealthLab", "BioMed"],
        "excellent_review": [40.0, 50.0, 20.0],
        "average_review": [40.0, 30.0, 60.0],
        "poor_review": [20.0, 20.0, 20.0],
        "search_document": [
            "meda 100mg treatment of bacterial infections and respiratory illness",
            "medb syrup relief of fever and mild to moderate pain",
            "medc capsule treatment of inflammation and joint pain",
        ],
    }
    df = pd.DataFrame(data)
    csv_file = tmp_path / "mock_medicines.csv"
    df.to_csv(csv_file, index=False)

    vec = TfidfVectorizer(stop_words="english")
    mat = vec.fit_transform(df["search_document"])

    mat_file = tmp_path / "mock_matrix.npz"
    save_npz(mat_file, mat)

    vec_file = tmp_path / "mock_vec.joblib"
    import joblib
    joblib.dump(vec, vec_file)

    return {
        "csv_path": csv_file,
        "matrix_path": mat_file,
        "vec_path": vec_file,
        "df": df,
    }


# =====================================================================
# Category A: Initialization and Data Loading
# =====================================================================

class TestInitializationAndLoading:
    def test_successful_production_initialization(self, production_recommender: MedicineRecommender):
        """Verifies successful loading of production dataset and artifacts."""
        assert production_recommender._is_ready is True
        assert len(production_recommender.df) == 11741
        assert production_recommender.matrix.shape[0] == 11741
        assert production_recommender.matrix.shape[1] == 22284

    def test_dataset_column_schema(self, production_recommender: MedicineRecommender):
        """Verifies essential clinical columns exist and are non-null string objects."""
        required_cols = ["medicine_name", "composition", "uses", "side_effects", "search_document"]
        for col in required_cols:
            assert col in production_recommender.df.columns
            assert not production_recommender.df[col].isna().any()

    def test_csv_to_matrix_exact_row_alignment(self, production_recommender: MedicineRecommender):
        """Validates that matrix row i matches dataset row i with >=0.99 self-similarity."""
        sample_indices = [0, 1, 7, 50, 500, 2500, 5000, 8000, 10000, 11740]
        for idx in sample_indices:
            row = production_recommender.df.iloc[idx]
            doc = str(row["search_document"])
            doc_vec = production_recommender.vectorizer.transform([
                production_recommender.normalize_text(doc)
            ])
            mat_row = production_recommender.matrix.getrow(idx)
            sim = cosine_similarity(doc_vec, mat_row)[0, 0]
            assert sim >= 0.99, f"Row alignment compromised at index {idx} (similarity: {sim})!"

    def test_missing_dataset_path_raises_file_not_found(self, tmp_path: Path):
        """Verifies FileNotFoundError when dataset path does not exist."""
        non_existent = tmp_path / "non_existent.csv"
        with pytest.raises(FileNotFoundError, match="Medicine dataset not found"):
            MedicineRecommender(dataset_path=non_existent)

    def test_missing_matrix_path_raises_file_not_found(self, tmp_path: Path, mock_medicine_data):
        """Verifies FileNotFoundError when TF-IDF matrix path does not exist."""
        non_existent = tmp_path / "non_existent.npz"
        with pytest.raises(FileNotFoundError, match="Module 1 precomputed artifacts missing"):
            MedicineRecommender(
                dataset_path=mock_medicine_data["csv_path"],
                tfidf_matrix_path=non_existent,
                vectorizer_path=mock_medicine_data["vec_path"],
            )

    def test_invalid_pipeline_mode_raises_value_error(self, mock_medicine_data):
        """Verifies ValueError when an unsupported pipeline mode is specified."""
        with pytest.raises(ValueError, match="Unknown pipeline_mode"):
            MedicineRecommender(
                dataset_path=mock_medicine_data["csv_path"],
                tfidf_matrix_path=mock_medicine_data["matrix_path"],
                vectorizer_path=mock_medicine_data["vec_path"],
                pipeline_mode="unsupported_quantum_mode",
            )

    def test_matrix_row_mismatch_raises_value_error(self, tmp_path: Path, mock_medicine_data):
        """Verifies ValueError when matrix row count does not equal DataFrame row count."""
        # Create a matrix with 2 rows while CSV has 3 rows
        vec = TfidfVectorizer()
        mat_mismatched = vec.fit_transform(["doc one", "doc two"])
        bad_mat_path = tmp_path / "bad_mat.npz"
        save_npz(bad_mat_path, mat_mismatched)

        with pytest.raises(ValueError, match="Alignment Error: Matrix rows"):
            MedicineRecommender(
                dataset_path=mock_medicine_data["csv_path"],
                tfidf_matrix_path=bad_mat_path,
                vectorizer_path=mock_medicine_data["vec_path"],
            )


# =====================================================================
# Category B: Query Preprocessing
# =====================================================================

class TestQueryPreprocessing:
    def test_lowercase_normalization(self):
        """Verifies text is normalized to lowercase."""
        assert MedicineRecommender.normalize_text("ASTHMA") == "asthma"
        assert MedicineRecommender.normalize_text("DiAbEtEs") == "diabetes"

    def test_whitespace_normalization(self):
        """Verifies multiple consecutive spaces and whitespace characters are collapsed."""
        raw = "   severe    headache \t\n and   fever   "
        expected = "severe headache and fever"
        assert MedicineRecommender.normalize_text(raw) == expected

    def test_alphanumeric_and_medical_symbol_retention(self):
        """Verifies special characters are stripped while preserving medical notations (+, %, ., -)."""
        raw = "Amoxycillin (500mg) + Clavulanic Acid @ 10%!"
        cleaned = MedicineRecommender.normalize_text(raw)
        assert "@" not in cleaned
        assert "!" not in cleaned
        assert "+" in cleaned
        assert "%" in cleaned

    def test_none_and_empty_normalization(self):
        """Verifies None, empty string, and whitespace-only return empty strings."""
        assert MedicineRecommender.normalize_text("") == ""
        assert MedicineRecommender.normalize_text("   ") == ""
        assert MedicineRecommender.normalize_text(None) == ""

    def test_stem_text_porter_stemmer(self, production_recommender: MedicineRecommender):
        """Verifies PorterStemmer token-by-token transformation."""
        input_text = "Treatment of Bacterial Infections Relieving"
        expected = "treatment of bacteri infect reliev"
        assert production_recommender.stem_text(input_text) == expected

    def test_production_vocabulary_compatibility(self, production_recommender: MedicineRecommender):
        """Verifies normalized query features map directly into production vocabulary."""
        query_norm = production_recommender.normalize_text("Asthma")
        q_vec = production_recommender.vectorizer.transform([query_norm])
        assert q_vec.nnz > 0, "Production vectorizer failed to encode 'asthma' feature!"


# =====================================================================
# Category C: Recommendation Engine
# =====================================================================

class TestRecommendationEngine:
    def test_valid_disease_query(self, production_recommender: MedicineRecommender):
        """Verifies query returns top candidates with required dictionary fields."""
        results = production_recommender.get_recommendations(disease="Asthma", top_k=5)
        assert len(results) == 5
        for r in results:
            assert "medicine_name" in r
            assert "composition" in r
            assert "uses" in r
            assert "similarity_score" in r
            assert "review_sentiment_score" in r
            assert "experimental_ranking_score" in r
            assert "match_explanation" in r
            assert "safety_assessment" in r
            assert "clinical_disclaimer" in r

    def test_empty_and_whitespace_query(self, production_recommender: MedicineRecommender):
        """Verifies empty or whitespace queries return empty lists."""
        assert production_recommender.get_recommendations(disease="") == []
        assert production_recommender.get_recommendations(disease="   ") == []

    def test_none_query(self, production_recommender: MedicineRecommender):
        """Verifies None query returns empty list without error."""
        assert production_recommender.get_recommendations(disease=None) == []

    def test_unknown_disease_query(self, production_recommender: MedicineRecommender):
        """Verifies non-matching query returns empty list gracefully."""
        assert production_recommender.get_recommendations(disease="ZzzNonexistentCondition99999") == []

    def test_top_k_limits(self, production_recommender: MedicineRecommender):
        """Verifies engine respects configurable top_k."""
        for k in [1, 3, 7]:
            res = production_recommender.get_recommendations(disease="Asthma", top_k=k)
            assert len(res) == k

    def test_top_k_zero_or_negative(self, production_recommender: MedicineRecommender):
        """Verifies top_k <= 0 clamps safely to at least 1."""
        res_zero = production_recommender.get_recommendations(disease="Asthma", top_k=0)
        assert len(res_zero) == 1
        res_neg = production_recommender.get_recommendations(disease="Asthma", top_k=-5)
        assert len(res_neg) == 1

    def test_similarity_score_validity_and_bounds(self, production_recommender: MedicineRecommender):
        """Verifies all similarity scores are bounded in [0.0, 1.0]."""
        results = production_recommender.get_recommendations(disease="Diabetes", top_k=10)
        for r in results:
            sim = r["similarity_score"]
            assert isinstance(sim, float)
            assert 0.0 <= sim <= 1.0

    def test_descending_similarity_ranking_order(self, production_recommender: MedicineRecommender):
        """Verifies retrieved candidate similarity scores are in non-ascending order."""
        results = production_recommender.get_recommendations(disease="Asthma", top_k=10)
        sims = [r["similarity_score"] for r in results]
        assert sims == sorted(sims, reverse=True)

    def test_match_explanation_content(self, production_recommender: MedicineRecommender):
        """Verifies match explanation explicitly references matched terms or cosine similarity."""
        results = production_recommender.get_recommendations(disease="Asthma", top_k=3)
        for r in results:
            exp = r["match_explanation"]
            assert isinstance(exp, str)
            assert "Retrieved" in exp
            assert "cosine similarity" in exp


# =====================================================================
# Category D: Allergy Screening
# =====================================================================

class TestAllergyScreening:
    def test_allergy_keyword_detection(self, production_recommender: MedicineRecommender):
        """Verifies detection of allergen in composition."""
        comp = "Amoxycillin (500mg) + Clavulanic Acid (125mg)"
        flag, matched, alert = production_recommender._assess_allergy(comp, ["Amoxycillin"])
        assert flag is True
        assert "Amoxycillin" in matched
        assert "DANGER - ALLERGY MATCH" in alert

    def test_danger_flag_generation(self, production_recommender: MedicineRecommender):
        """Verifies DANGER flag generated when allergy matches in get_recommendations."""
        results = production_recommender.get_recommendations(
            disease="Bacterial infections",
            patient_allergies=["Amoxycillin"],
            filter_allergies=False,
            top_k=5,
        )
        allergy_items = [r for r in results if r["safety_assessment"]["allergy_detected"]]
        assert len(allergy_items) > 0
        for item in allergy_items:
            assert "DANGER - ALLERGY MATCH" in item["safety_assessment"]["allergy_alert"]

    def test_allergy_filtering_and_no_leakage(self, production_recommender: MedicineRecommender):
        """Verifies filter_allergies=True excludes all matching allergen candidates."""
        filtered_results = production_recommender.get_recommendations(
            disease="Bacterial infections",
            patient_allergies=["Amoxycillin"],
            filter_allergies=True,
            top_k=5,
        )
        assert len(filtered_results) > 0
        for r in filtered_results:
            sa = r["safety_assessment"]
            assert sa["allergy_detected"] is False
            assert "No reported allergen matches detected" in sa["allergy_alert"]

    def test_missing_composition_handling(self, production_recommender: MedicineRecommender):
        """Verifies missing composition is conservatively marked UNVERIFIED."""
        flag, matched, alert = production_recommender._assess_allergy("", ["Aspirin"])
        assert flag is False
        assert "UNVERIFIED" in alert

    def test_clinical_disclaimer_presence_and_caution(self, production_recommender: MedicineRecommender):
        """Verifies disclaimer presence and caution that absence of allergy is not safety."""
        results = production_recommender.get_recommendations(disease="Asthma", top_k=2)
        for r in results:
            disclaimer = r["clinical_disclaimer"]
            assert "Academic research & educational prototype only" in disclaimer
            assert "Absence of an allergen match does not guarantee clinical safety" in disclaimer

    def test_no_false_clinical_safety_claims(self, production_recommender: MedicineRecommender):
        """Verifies output never claims candidate is clinically safe."""
        results = production_recommender.get_recommendations(
            disease="Asthma",
            patient_allergies=["Penicillin"],
            filter_allergies=True,
            top_k=3,
        )
        for r in results:
            alert = r["safety_assessment"]["allergy_alert"]
            assert "clinically safe" not in alert.lower()
            assert "safe alternative" not in alert.lower()


# =====================================================================
# Category E: Patient Condition Warnings
# =====================================================================

class TestPatientConditionWarnings:
    def test_condition_side_effect_overlap(self, production_recommender: MedicineRecommender):
        """Verifies condition overlapping with side effects is flagged."""
        side_effects = "Nausea, Vomiting, Headache, Drowsiness"
        flag, concerns, text = production_recommender._assess_conditions(
            side_effects=side_effects,
            uses="Infection treatment",
            patient_conditions=["Vomiting"],
        )
        assert flag is True
        assert len(concerns) > 0
        assert "vomiting" in concerns[0].lower()

    def test_preliminary_warning_label_not_contraindication(self, production_recommender: MedicineRecommender):
        """Verifies warnings are explicitly labeled preliminary, not confirmed contraindications."""
        results = production_recommender.get_recommendations(
            disease="Bacterial infections",
            patient_conditions=["Vomiting"],
            top_k=5,
        )
        warned_items = [r for r in results if r["safety_assessment"]["preliminary_condition_warning"]]
        assert len(warned_items) > 0
        for item in warned_items:
            concerns = item["safety_assessment"]["preliminary_condition_concerns"]
            for c in concerns:
                assert "Preliminary warning" in c
                assert "Not a confirmed contraindication" in c

    def test_missing_side_effects_handling(self, production_recommender: MedicineRecommender):
        """Verifies empty side-effects text is labeled UNVERIFIED."""
        flag, concerns, text = production_recommender._assess_conditions(
            side_effects="",
            uses="Treatment",
            patient_conditions=["Hypertension"],
        )
        assert flag is False
        assert "UNVERIFIED" in text

    def test_multiple_patient_conditions(self, production_recommender: MedicineRecommender):
        """Verifies multiple reported conditions are evaluated simultaneously."""
        flag, concerns, text = production_recommender._assess_conditions(
            side_effects="High blood pressure, Dizziness, Headache",
            uses="Treatment",
            patient_conditions=["High blood pressure", "Dizziness", "Diabetes"],
        )
        assert flag is True
        assert len(concerns) == 2  # High blood pressure and Dizziness match, Diabetes does not


# =====================================================================
# Category F: Experimental Ranking
# =====================================================================

class TestExperimentalRanking:
    def test_review_sentiment_normalization(self):
        """Verifies review sentiment score calculation in [0.0, 1.0]."""
        row = pd.Series({"excellent_review": 60, "average_review": 30, "poor_review": 10})
        # (60*1.0 + 30*0.5 + 10*0.0) / 100 = 75 / 100 = 0.75
        assert MedicineRecommender._compute_review_score(row) == 0.75

    def test_review_sentiment_missing_defaults_to_neutral(self):
        """Verifies missing or zero review data defaults to neutral 0.5."""
        row_none = pd.Series({"excellent_review": None, "average_review": None, "poor_review": None})
        assert MedicineRecommender._compute_review_score(row_none) == 0.5
        row_zero = pd.Series({"excellent_review": 0, "average_review": 0, "poor_review": 0})
        assert MedicineRecommender._compute_review_score(row_zero) == 0.5

    def test_exact_85_15_formula(self, production_recommender: MedicineRecommender):
        """Verifies exact 85% similarity + 15% sentiment calculation across multiple diseases."""
        for disease in ["Asthma", "Diabetes", "Migraine"]:
            results = production_recommender.get_recommendations(disease=disease, top_k=5)
            for r in results:
                sim = r["similarity_score"]
                sent = r["review_sentiment_score"]
                exp = r["experimental_ranking_score"]
                expected_calc = round(0.85 * sim + 0.15 * sent, 4)
                assert exp == expected_calc, (
                    f"Formula mismatch for {r['medicine_name']}: {exp} != {expected_calc}"
                )

    def test_four_decimal_rounding_consistency(self, production_recommender: MedicineRecommender):
        """Verifies scores are consistently rounded to at most 4 decimal places."""
        results = production_recommender.get_recommendations(disease="Hypertension", top_k=5)
        for r in results:
            for score_key in ["similarity_score", "review_sentiment_score", "experimental_ranking_score"]:
                val = r[score_key]
                val_str = str(val).split(".")[-1] if "." in str(val) else ""
                assert len(val_str) <= 4, f"{score_key} has more than 4 decimals: {val}"

    def test_separation_of_scores(self, production_recommender: MedicineRecommender):
        """Verifies distinct separation of similarity, sentiment, and experimental ranking scores."""
        results = production_recommender.get_recommendations(disease="Asthma", top_k=3)
        for r in results:
            assert "similarity_score" in r
            assert "review_sentiment_score" in r
            assert "experimental_ranking_score" in r
            assert "ranking_methodology" in r
            assert "does not represent clinical efficacy" in r["ranking_methodology"]


# =====================================================================
# Category G: Error Handling & Mock Isolation
# =====================================================================

class TestErrorHandlingAndRobustness:
    def test_uninitialized_engine_raises_runtime_error(self, mock_medicine_data):
        """Verifies RuntimeError when get_recommendations is called on uninitialized engine."""
        recommender = MedicineRecommender.__new__(MedicineRecommender)
        recommender._is_ready = False
        with pytest.raises(RuntimeError, match="not initialized properly"):
            recommender.get_recommendations(disease="Asthma")

    def test_malformed_patient_allergies_handled_gracefully(self, production_recommender: MedicineRecommender):
        """Verifies non-string or blank elements in patient_allergies do not crash engine."""
        results = production_recommender.get_recommendations(
            disease="Asthma",
            patient_allergies=["", None, "   ", 12345],  # type: ignore
            top_k=3,
        )
        assert len(results) == 3

    def test_malformed_patient_conditions_handled_gracefully(self, production_recommender: MedicineRecommender):
        """Verifies non-string or blank elements in patient_conditions do not crash engine."""
        results = production_recommender.get_recommendations(
            disease="Asthma",
            patient_conditions=["", None, "   ", 67890],  # type: ignore
            top_k=3,
        )
        assert len(results) == 3

    def test_isolated_mock_dataset_execution(self, mock_medicine_data):
        """Unit test using temporary mock fixtures completely isolated from production artifacts."""
        mock_rec = MedicineRecommender(
            dataset_path=mock_medicine_data["csv_path"],
            tfidf_matrix_path=mock_medicine_data["matrix_path"],
            vectorizer_path=mock_medicine_data["vec_path"],
        )
        assert mock_rec._is_ready is True
        assert len(mock_rec.df) == 3

        recs = mock_rec.get_recommendations(disease="Bacterial", top_k=1)
        assert len(recs) == 1
        assert recs[0]["medicine_name"] == "MedA 100mg"

    def test_custom_index_tfidf_and_count_vectorizer(self, mock_medicine_data):
        """Verifies custom index builder for comparative benchmarking (TF-IDF and CountVectorizer)."""
        mock_rec = MedicineRecommender(
            dataset_path=mock_medicine_data["csv_path"],
            tfidf_matrix_path=mock_medicine_data["matrix_path"],
            vectorizer_path=mock_medicine_data["vec_path"],
        )
        # Test building CountVectorizer index with stemming
        mock_rec.build_custom_index(vectorizer_type="count", use_stemming=True, max_features=100)
        assert mock_rec.pipeline_mode == "count_stemmed"
        count_recs = mock_rec.get_recommendations(disease="Bacterial", top_k=1)
        assert len(count_recs) == 1

        # Test building TF-IDF index with stemming
        mock_rec.build_custom_index(vectorizer_type="tfidf", use_stemming=True, max_features=100)
        assert mock_rec.pipeline_mode == "tfidf_stemmed"
        tfidf_recs = mock_rec.get_recommendations(disease="Bacterial", top_k=1)
        assert len(tfidf_recs) == 1

