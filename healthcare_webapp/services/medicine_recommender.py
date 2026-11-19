"""
Module 3: Personalized Medicine Recommendation Engine
======================================================
Author: Module 3 Lead (Medicine Recommendation Engine)
Project: Personalized Healthcare & Medicine Recommendation System (Zidio Internship)

This module provides a standalone, production-grade recommendation engine that:
1. Reuses cleaned medicine datasets and precomputed Module 1 TF-IDF artifacts with 100% row alignment.
2. Normalizes text without stemming during production inference to maintain strict feature compatibility
   with Module 1's fitted TfidfVectorizer.
3. Provides PorterStemmer tokenization for dedicated comparative benchmarking (TF-IDF vs CountVectorizer).
4. Computes Cosine Similarity between disease indications/queries and medicine profiles.
5. Performs preliminary, conservative allergy checks against active compositions without claiming safety.
6. Flags preliminary condition-keyword overlaps in documented side-effects (not confirmed contraindications).
7. Incorporates community feedback (reviews) purely as an experimental tie-breaking ranking signal,
   never as a measure of pharmacological or clinical effectiveness.
8. Attaches prominent clinical disclaimers to every recommendation output.
9. Operates completely independently of Flask, web frameworks, or databases.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from nltk.stem import PorterStemmer
from scipy.sparse import issparse, load_npz, spmatrix
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Standard academic clinical disclaimer
CLINICAL_DISCLAIMER = (
    "Academic research & educational prototype only. Recommendations and similarity "
    "scores do not establish clinical equivalence, pharmacological suitability, or a "
    "prescription. Absence of an allergen match does not guarantee clinical safety or "
    "absence of cross-reactivity. Always consult a qualified healthcare professional."
)


class MedicineRecommender:
    """
    Personalized Medicine Recommendation Engine (Module 3).
    
    Provides text-similarity candidate retrieval, preliminary conservative allergy checks,
    preliminary condition warnings, experimental review-weighted ranking, and match explanations.
    """

    def __init__(
        self,
        dataset_path: Optional[Union[str, Path]] = None,
        tfidf_matrix_path: Optional[Union[str, Path]] = None,
        vectorizer_path: Optional[Union[str, Path]] = None,
        pipeline_mode: str = "tfidf_precomputed",
    ) -> None:
        """
        Initialize the recommendation engine.
        
        Args:
            dataset_path: Path to cleaned_medicine_prepared.csv. If None, auto-resolved.
            tfidf_matrix_path: Path to medicine_tfidf_matrix.npz. If None, auto-resolved.
            vectorizer_path: Path to medicine_tfidf_vectorizer.joblib. If None, auto-resolved.
            pipeline_mode: 'tfidf_precomputed' (default production mode reusing Module 1),
                           'tfidf_stemmed' (builds fresh stemmed TF-IDF index for experiments),
                           or 'count_stemmed' (builds CountVectorizer index for experiments).
        """
        self.repo_root = self._resolve_repo_root()
        self.stemmer = PorterStemmer()
        
        # Resolve dataset and artifact paths
        self.dataset_path = Path(
            dataset_path
            or self.repo_root / "datasets" / "processed" / "cleaned_medicine_prepared.csv"
        )
        self.tfidf_matrix_path = Path(
            tfidf_matrix_path
            or self.repo_root
            / "module1_data_collection_cleaning"
            / "medicine_outputs"
            / "medicine_tfidf_matrix.npz"
        )
        self.vectorizer_path = Path(
            vectorizer_path
            or self.repo_root
            / "module1_data_collection_cleaning"
            / "medicine_outputs"
            / "medicine_tfidf_vectorizer.joblib"
        )

        # In-memory storage
        self.df: pd.DataFrame = pd.DataFrame()
        self.vectorizer: Any = None
        self.matrix: Optional[spmatrix] = None
        self.pipeline_mode: str = pipeline_mode
        self._is_ready: bool = False

        # Load resources
        self._load_dataset()
        self._load_pipeline(mode=pipeline_mode)

    @staticmethod
    def _resolve_repo_root() -> Path:
        """Dynamically locates the project root directory."""
        current = Path(__file__).resolve().parent
        root = current.parent.parent
        if (root / "datasets").exists():
            return root
        cwd = Path.cwd()
        if (cwd / "datasets").exists():
            return cwd
        return root

    def _load_dataset(self) -> None:
        """Loads and indexes the prepared medicine dataset."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Medicine dataset not found at: {self.dataset_path}"
            )
        self.df = pd.read_csv(self.dataset_path)
        # Ensure essential columns exist and are clean strings
        for col in ["medicine_name", "composition", "uses", "side_effects", "search_document"]:
            if col not in self.df.columns:
                self.df[col] = ""
            else:
                self.df[col] = self.df[col].fillna("").astype(str)

    def _load_pipeline(self, mode: str = "tfidf_precomputed") -> None:
        """
        Loads or builds the vectorizer and matrix according to requested mode.
        Ensures strict preprocessing parity between queries and the document matrix.
        """
        self.pipeline_mode = mode
        if mode == "tfidf_precomputed":
            if not self.vectorizer_path.exists() or not self.tfidf_matrix_path.exists():
                raise FileNotFoundError(
                    "Module 1 precomputed artifacts missing. Check paths:\n"
                    f"Vectorizer: {self.vectorizer_path}\nMatrix: {self.tfidf_matrix_path}"
                )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.vectorizer = joblib.load(self.vectorizer_path)
            self.matrix = load_npz(self.tfidf_matrix_path)
            
            # Strict row-alignment assertion
            if self.matrix.shape[0] != len(self.df):
                raise ValueError(
                    f"Alignment Error: Matrix rows ({self.matrix.shape[0]}) do not match "
                    f"dataset rows ({len(self.df)}). Alignment is compromised."
                )
            self._is_ready = True

        elif mode in ("tfidf_stemmed", "count_stemmed"):
            self.build_custom_index(
                vectorizer_type="tfidf" if mode == "tfidf_stemmed" else "count",
                use_stemming=True,
            )
        else:
            raise ValueError(
                f"Unknown pipeline_mode: {mode}. Choose 'tfidf_precomputed', "
                "'tfidf_stemmed', or 'count_stemmed'."
            )

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Standardizes text: lowercases, cleans punctuation, normalizes whitespace.
        Identical to Module 1 preprocessing to ensure 100% vocabulary compatibility.
        """
        if not text or pd.isna(text):
            return ""
        text = str(text).lower()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^a-z0-9+.%/ -]", " ", text)
        return text.strip()

    def stem_text(self, text: str) -> str:
        """
        Applies PorterStemmer to individual alphanumeric tokens in a string.
        Used for custom comparative experiments (where both document matrix
        and queries are stemmed together), NEVER applied to query alone in production.
        """
        cleaned = self.normalize_text(text)
        tokens = re.findall(r"[a-z0-9]+", cleaned)
        stemmed = [self.stemmer.stem(t) for t in tokens]
        return " ".join(stemmed)

    def build_custom_index(
        self,
        vectorizer_type: str = "tfidf",
        use_stemming: bool = True,
        max_features: int = 25000,
        ngram_range: Tuple[int, int] = (1, 2),
    ) -> None:
        """
        Builds a custom in-memory vectorizer and sparse matrix index.
        Used for comparative evaluation in notebooks and research benchmarks.
        Both the document matrix and future queries will use the identical pipeline.
        
        Args:
            vectorizer_type: 'tfidf' or 'count'.
            use_stemming: Whether to apply PorterStemmer before tokenizing.
            max_features: Maximum vocabulary size.
            ngram_range: (min_n, max_n) n-gram range.
        """
        if self.df.empty:
            self._load_dataset()

        raw_documents = self.df["search_document"].fillna("").tolist()
        
        if use_stemming:
            documents = [self.stem_text(doc) for doc in raw_documents]
        else:
            documents = [self.normalize_text(doc) for doc in raw_documents]

        if vectorizer_type.lower() == "tfidf":
            vec = TfidfVectorizer(
                stop_words="english",
                max_features=max_features,
                ngram_range=ngram_range,
            )
        elif vectorizer_type.lower() == "count":
            vec = CountVectorizer(
                stop_words="english",
                max_features=max_features,
                ngram_range=ngram_range,
            )
        else:
            raise ValueError(f"Unsupported vectorizer_type: {vectorizer_type}")

        self.matrix = vec.fit_transform(documents)
        self.vectorizer = vec
        self.pipeline_mode = f"{vectorizer_type.lower()}_{'stemmed' if use_stemming else 'unstemmed'}"
        self._is_ready = True

    def _assess_allergy(
        self,
        composition: str,
        patient_allergies: List[str],
    ) -> Tuple[bool, List[str], str]:
        """
        Conservatively evaluates active medicine composition against patient-reported allergies.
        
        Returns:
            (allergy_detected, matched_allergens, safety_alert_text)
        """
        if not composition or composition.strip() == "":
            return False, [], "UNVERIFIED: Composition data is missing from record. Manual clinical verification required."

        if not patient_allergies:
            return False, [], "No known patient allergies reported."

        comp_norm = self.normalize_text(composition)
        comp_stemmed = self.stem_text(composition)
        matched = []

        for allergy in patient_allergies:
            if not allergy or not str(allergy).strip():
                continue
            alg_clean = self.normalize_text(str(allergy))
            alg_stem = self.stem_text(str(allergy))

            # Match on whole words or stemmed root in composition
            word_pattern = rf"\b{re.escape(alg_clean)}\b"
            if re.search(word_pattern, comp_norm):
                matched.append(str(allergy).strip())
            elif alg_stem and alg_stem in comp_stemmed:
                matched.append(str(allergy).strip())

        if matched:
            unique_matched = sorted(list(set(matched)))
            alert = (
                f"DANGER - ALLERGY MATCH: Patient has reported allergy to "
                f"{unique_matched}, which matches active composition '{composition}'."
            )
            return True, unique_matched, alert

        return (
            False,
            [],
            "No reported allergen matches detected in listed composition. "
            "This is an automated preliminary check and does not guarantee clinical safety.",
        )

    def _assess_conditions(
        self,
        side_effects: str,
        uses: str,
        patient_conditions: List[str],
    ) -> Tuple[bool, List[str], str]:
        """
        Flags preliminary keyword overlaps between patient conditions and documented side-effects.
        
        IMPORTANT: Documented side effects reflect possible adverse events, not confirmed
        clinical contraindications. Matches are provided as preliminary warnings only.
        
        Returns:
            (preliminary_warning_flag, matching_concerns, warning_summary_text)
        """
        if not patient_conditions:
            return False, [], "No pre-existing conditions reported."

        if not side_effects or side_effects.strip() == "":
            return False, [], "UNVERIFIED: Documented side-effect data is unavailable in record."

        se_norm = self.normalize_text(side_effects)
        se_stemmed = self.stem_text(side_effects)
        concerns = []

        for condition in patient_conditions:
            if not condition or not str(condition).strip():
                continue
            cond_clean = self.normalize_text(str(condition))
            cond_stem = self.stem_text(str(condition))

            if cond_clean and (cond_clean in se_norm or cond_stem in se_stemmed):
                concerns.append(
                    f"Preliminary warning: Patient condition '{condition}' overlaps with "
                    f"documented side effect term ('{cond_clean}'). Not a confirmed "
                    "contraindication; clinical review required."
                )

        if concerns:
            return True, concerns, "PRELIMINARY_WARNING_CONCERNS_IDENTIFIED"
        return False, [], "No preliminary condition overlaps detected in documented side effects."

    @staticmethod
    def _compute_review_score(row: pd.Series) -> float:
        """
        Calculates a normalized secondary community sentiment rating [0.0, 1.0] from patient reviews.
        
        NOTE: This represents community feedback from the dataset, never pharmacological
        or medical effectiveness.
        """
        try:
            exc = float(row.get("excellent_review", 0.0) or 0.0)
            avg = float(row.get("average_review", 0.0) or 0.0)
            poor = float(row.get("poor_review", 0.0) or 0.0)
            total = exc + avg + poor
            if total > 0.0:
                return round((exc * 1.0 + avg * 0.5) / total, 4)
        except (ValueError, TypeError):
            pass
        return 0.5  # Neutral default when review data is absent

    def _generate_explanation(
        self,
        query: str,
        uses: str,
        medicine_name: str,
        sim_score: float,
    ) -> str:
        """Generates a transparent explanation of why a candidate medicine was retrieved."""
        q_tokens = set(re.findall(r"[a-z0-9]+", self.normalize_text(query)))
        uses_tokens = set(re.findall(r"[a-z0-9]+", self.normalize_text(uses)))
        name_tokens = set(re.findall(r"[a-z0-9]+", self.normalize_text(medicine_name)))

        matched_indications = sorted(list(q_tokens.intersection(uses_tokens)))
        matched_name = sorted(list(q_tokens.intersection(name_tokens)))

        parts = []
        if matched_indications:
            parts.append(f"matched indication keywords: {matched_indications}")
        if matched_name:
            parts.append(f"matched medicine brand terms: {matched_name}")
        
        if parts:
            return f"Retrieved because query {' and '.join(parts)} with cosine similarity of {sim_score:.4f}."
        return f"Retrieved via latent TF-IDF text similarity (cosine score: {sim_score:.4f})."

    def get_recommendations(
        self,
        disease: str,
        patient_allergies: Optional[List[str]] = None,
        patient_conditions: Optional[List[str]] = None,
        top_k: int = 5,
        filter_allergies: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Recommends personalized medicines based on disease input and patient profile.
        
        Args:
            disease: Predicted disease name or health condition query (e.g., 'Asthma').
            patient_allergies: List of active ingredient allergens (e.g., ['Aspirin', 'Amoxycillin']).
            patient_conditions: List of patient conditions (e.g., ['Hypertension', 'Kidney disease']).
            top_k: Number of recommendations to return (default: 5).
            filter_allergies: If True, excludes candidate medicines with detected allergen matches.
                              Filtered candidates are merely free of identified allergen keywords
                              and must NEVER be considered clinically safe alternatives.
                              If False, retains all candidates but flags matches prominently.
                              
        Returns:
            List of dictionaries representing candidate medicines with similarity scores,
            safety assessments, review sentiment, and explanations.
        """
        if not self._is_ready:
            raise RuntimeError("Recommendation engine is not initialized properly.")

        if patient_allergies is None:
            patient_allergies = []
        if patient_conditions is None:
            patient_conditions = []

        # Validate query
        if not disease or not str(disease).strip():
            return []

        top_k = max(1, int(top_k))

        # IMPORTANT: In production ('tfidf_precomputed'), we use exact unstemmed normalization
        # to guarantee 100% vocabulary compatibility with Module 1's fitted TfidfVectorizer.
        # Queries are NEVER stemmed alone against an unstemmed matrix.
        if "stemmed" in self.pipeline_mode:
            processed_query = self.stem_text(disease)
        else:
            processed_query = self.normalize_text(disease)

        if not processed_query.strip():
            return []

        # Transform query and compute Cosine Similarity
        query_vector = self.vectorizer.transform([processed_query])
        sim_scores = cosine_similarity(query_vector, self.matrix).ravel()

        # Find candidates with positive similarity
        positive_indices = np.where(sim_scores > 0.0)[0]
        if len(positive_indices) == 0:
            return []

        # Sort candidate indices by raw similarity descending
        sorted_indices = positive_indices[np.argsort(sim_scores[positive_indices])[::-1]]

        # Buffer candidates to allow post-retrieval safety assessment and optional filtering
        buffer_size = min(len(sorted_indices), max(top_k * 4, 30))
        candidate_indices = sorted_indices[:buffer_size]

        recommendations: List[Dict[str, Any]] = []

        for idx in candidate_indices:
            row = self.df.iloc[idx]
            sim = float(sim_scores[idx])
            med_name = str(row.get("medicine_name", "")).strip()
            composition = str(row.get("composition", "")).strip()
            uses = str(row.get("uses", "")).strip()
            side_effects = str(row.get("side_effects", "")).strip()
            image_url = str(row.get("image_url", "")).strip()
            manufacturer = str(row.get("manufacturer", "")).strip()

            # Safety Assessment: Allergy
            allergy_detected, matched_allergens, allergy_alert = self._assess_allergy(
                composition=composition,
                patient_allergies=patient_allergies,
            )

            # If user requested allergy exclusion, skip this candidate
            if filter_allergies and allergy_detected:
                continue

            # Safety Assessment: Condition Precautions
            preliminary_warning_flag, condition_concerns, precaution_text = self._assess_conditions(
                side_effects=side_effects,
                uses=uses,
                patient_conditions=patient_conditions,
            )

            # Secondary feedback signal (reviews)
            review_sentiment = self._compute_review_score(row)
            sim_rounded = round(sim, 4)
            
            # Experimental Heuristic Ranking Score:
            # 85% Cosine Similarity + 15% Normalized Community Review Sentiment.
            # Documented strictly as a ranking heuristic to break ties, NOT medical effectiveness.
            experimental_score = round(0.85 * sim_rounded + 0.15 * review_sentiment, 4)

            # Explanation
            explanation = self._generate_explanation(
                query=disease,
                uses=uses,
                medicine_name=med_name,
                sim_score=sim_rounded,
            )

            # Data availability flag (clarifies whether clinical text fields exist)
            safety_data_available = bool(composition and side_effects)

            recommendations.append({
                "medicine_name": med_name,
                "composition": composition,
                "uses": uses,
                "side_effects": side_effects,
                "image_url": image_url,
                "manufacturer": manufacturer,
                "similarity_score": sim_rounded,
                "review_sentiment_score": review_sentiment,
                "experimental_ranking_score": experimental_score,
                "ranking_methodology": (
                    "85% TF-IDF Cosine Similarity + 15% Normalized Community Review Sentiment "
                    "(Experimental heuristic ranking only, does not represent clinical efficacy)"
                ),
                "match_explanation": explanation,
                "safety_assessment": {
                    "allergy_detected": allergy_detected,
                    "matched_allergens": matched_allergens,
                    "allergy_alert": allergy_alert,
                    "preliminary_condition_warning": preliminary_warning_flag,
                    "preliminary_condition_concerns": condition_concerns,
                    "safety_data_available": safety_data_available,
                },
                "clinical_disclaimer": CLINICAL_DISCLAIMER,
            })

            if len(recommendations) >= top_k:
                break

        return recommendations
