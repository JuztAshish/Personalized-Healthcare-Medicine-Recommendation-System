🧬 Disease Dataset Outputs 

This folder contains the cleaned, validated, and encoded disease dataset files prepared by Member 1 – Data Collection, Cleaning & Preprocessing for the Personalized Healthcare Recommendation System.

📂 Available Files 1. disease_features_encoded.csv Contains encoded disease-related features. Includes numerical representations of categorical features, where applicable. Contains disease labels for machine learning development. Intended for Member 2 to inspect and prepare for model training. 2. disease_data_metadata.json Stores dataset metadata and preprocessing information. Provides information about the target column and feature mappings. Helps developers understand the encoded dataset structure. 3. disease_label_encoder.joblib Stores the fitted disease label encoder. Used to convert encoded disease labels back into their original readable names. Should be loaded using the compatible preprocessing workflow. 📁 Folder Structure disease_outputs/ │ ├── disease_features_encoded.csv ├── disease_data_metadata.json ├── disease_label_encoder.joblib └── README.md 👥 Module Responsibility 

Member 1 – Data Preparation

Dataset inspection and validation. Missing-value and duplicate handling. Feature preprocessing and encoding. Exporting structured output files. 

Member 2 – Disease Prediction

Inspecting encoded features and target labels. Preparing training and testing datasets. Training machine learning models. Evaluating model performance. Saving the trained prediction model. ⚙️ Instructions for Member 2 Read disease_data_metadata.json before using the encoded dataset. Verify the target column and feature columns. Use the fitted label encoder when decoding disease labels. Check class distribution and potential data leakage. Apply the same preprocessing steps during training and prediction. Do not fit a new encoder independently for test data. ⚠️ Important Notes Verify all column names and data types before model training. The encoded dataset is a prepared input, not a trained prediction model. disease_label_encoder.joblib is not the disease prediction model. Predictions are for academic project development and are not a medical diagnosis. Clinical validation is required before any real-world use. 

Project: Personalized Healthcare Recommendation System
Module: Disease Dataset Preparation
Prepared by: Member 1

